"""Content-addressed, immutable asset store (ARCHITECTURE section 4.3).

Files live at `assets/{sha[0:2]}/{sha}.{ext}`. A write goes to `assets/.tmp/`, is fsynced, then moved
into place with an atomic rename, so a crash at any point leaves either the complete file or nothing at
the final path. The file is written before its `asset` row, so a row never points at a missing file;
the reverse (a file with no row after a crash) is repaired by the next `put` of the same bytes or
removed by `gc`.
"""

import contextlib
import hashlib
import os
import re
import tempfile
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import BinaryIO, Literal

from pydantic import BaseModel, ConfigDict
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from comic_smith.db.base import utc_now_iso
from comic_smith.db.models import Asset
from comic_smith.errors import UsageError

Origin = Literal["upload", "render", "export", "derived"]

_SHA_RE = re.compile(r"^[0-9a-f]{64}$")
_EXT_RE = re.compile(r"^[a-z0-9]{1,8}$")
TMP_DIRNAME = ".tmp"


class AssetRef(BaseModel):
    """Immutable handle to a stored asset; `sha256` is the asset id."""

    model_config = ConfigDict(frozen=True)

    sha256: str
    mime: str
    ext: str
    width: int | None = None
    height: int | None = None


def _check_sha(sha: str) -> str:
    """Reject anything that is not a lowercase SHA-256 hex digest (path traversal guard)."""
    if not _SHA_RE.match(sha):
        raise UsageError(f"Not a valid asset id: {sha!r}", hint="Asset ids are 64 hex characters.")
    return sha


class AssetStore:
    """Write-once file store plus the `asset` table rows that describe it."""

    def __init__(self, root: Path, engine: Engine) -> None:
        """Bind the store to an `assets/` directory and the project engine.

        Args:
            root: The project's `assets/` directory.
            engine: Engine used when a caller does not pass its own session.
        """
        self.root = root
        self._engine = engine
        root.mkdir(parents=True, exist_ok=True)

    @contextlib.contextmanager
    def _scope(self, session: Session | None) -> Iterator[Session]:
        """Use the caller's session (its transaction owns the commit) or open a short one."""
        if session is not None:
            yield session
            return
        with Session(self._engine) as own:
            yield own
            own.commit()

    def _find(self, sha: str) -> Path | None:
        """Locate the stored file for a digest regardless of extension."""
        shard = self.root / _check_sha(sha)[:2]
        return next((p for p in shard.glob(f"{sha}.*") if p.is_file()), None) if shard.is_dir() else None

    def exists(self, sha: str) -> bool:
        """True when the complete file is present."""
        return self._find(sha) is not None

    def path(self, sha: str) -> Path:
        """Filesystem path of a stored asset; raises FileNotFoundError when absent."""
        found = self._find(sha)
        if found is None:
            raise FileNotFoundError(f"asset {sha} is not in the store")
        return found

    def read(self, sha: str) -> bytes:
        """Read the whole asset into memory."""
        return self.path(sha).read_bytes()

    def open(self, sha: str) -> BinaryIO:
        """Open the asset for streaming reads."""
        return self.path(sha).open("rb")

    def _write_atomic(self, dest: Path, data: bytes) -> None:
        """Temp file in `.tmp/`, fsync, then `os.replace` into the final path."""
        tmp_dir = self.root / TMP_DIRNAME
        tmp_dir.mkdir(parents=True, exist_ok=True)
        dest.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=tmp_dir, suffix=".part")
        try:
            with os.fdopen(fd, "wb") as fh:
                fh.write(data)
                fh.flush()
                os.fsync(fh.fileno())
            Path(tmp).replace(dest)
        except BaseException:
            Path(tmp).unlink(missing_ok=True)
            raise

    def put(
        self,
        data: bytes,
        *,
        mime: str,
        ext: str,
        origin: Origin,
        width: int | None = None,
        height: int | None = None,
        session: Session | None = None,
    ) -> AssetRef:
        """Store bytes by content hash; storing the same bytes again is a no-op.

        Args:
            data: Raw bytes (already re-encoded by the caller for uploads).
            mime: Media type recorded on the asset row.
            ext: File extension without a dot, for example `png`.
            origin: Where the asset came from (upload, render, export, derived).
            width: Pixel width for images.
            height: Pixel height for images.
            session: Optional open session so the row joins the caller's transaction.

        Returns:
            A reference whose `sha256` is the asset id.
        """
        if not _EXT_RE.match(ext):
            raise UsageError(f"Not a valid file extension: {ext!r}")
        sha = hashlib.sha256(data).hexdigest()
        existing = self._find(sha)
        if existing is None:
            self._write_atomic(self.root / sha[:2] / f"{sha}.{ext}", data)
        else:
            ext = existing.suffix.lstrip(".")
        with self._scope(session) as s:
            if s.get(Asset, sha) is None:
                s.add(
                    Asset(
                        id=sha,
                        mime=mime,
                        width=width,
                        height=height,
                        bytes=len(data),
                        origin=origin,
                        created_at=utc_now_iso(),
                    )
                )
                s.flush()
        return AssetRef(sha256=sha, mime=mime, ext=ext, width=width, height=height)

    def clean_tmp(self) -> int:
        """Delete leftovers from interrupted writes; safe only while holding the project lock."""
        tmp_dir = self.root / TMP_DIRNAME
        leftovers = [p for p in tmp_dir.iterdir() if p.is_file()] if tmp_dir.is_dir() else []
        for p in leftovers:
            p.unlink(missing_ok=True)
        return len(leftovers)

    def _stored_files(self) -> dict[str, Path]:
        """Map digest to path for every complete file on disk."""
        files = (
            p
            for shard in self.root.iterdir()
            if shard.is_dir() and shard.name != TMP_DIRNAME
            for p in shard.iterdir()
            if p.is_file() and _SHA_RE.match(p.stem)
        )
        return {p.stem: p for p in files}

    def gc(
        self, referenced: set[str], *, grace: timedelta = timedelta(0), dry_run: bool = False
    ) -> list[str]:
        """Remove assets (file and row) that are not referenced and older than the grace period.

        The caller computes `referenced` (ARCHITECTURE 4.3 lists the sources); the 24 hour grace
        period for in-flight jobs is passed in by the CLI so tests and callers can choose.

        Returns:
            Sorted digests that were removed (or would be, when `dry_run`).
        """
        cutoff = datetime.now(UTC) - grace
        cutoff_iso = cutoff.strftime("%Y-%m-%dT%H:%M:%SZ")
        files = self._stored_files()
        removed: list[str] = []
        with self._scope(None) as s:
            rows = {a.id: a for a in s.scalars(select(Asset))}
            for sha in sorted(rows.keys() | files.keys()):
                if sha in referenced or not self._is_old(sha, rows, files, cutoff, cutoff_iso):
                    continue
                removed.append(sha)
                if not dry_run:
                    if sha in files:
                        files[sha].unlink(missing_ok=True)
                    if sha in rows:
                        s.delete(rows[sha])
        return removed

    @staticmethod
    def _is_old(
        sha: str, rows: dict[str, Asset], files: dict[str, Path], cutoff: datetime, cutoff_iso: str
    ) -> bool:
        """Row age wins; a file with no row falls back to its mtime."""
        if sha in rows:
            return rows[sha].created_at <= cutoff_iso
        return datetime.fromtimestamp(files[sha].stat().st_mtime, UTC) <= cutoff
