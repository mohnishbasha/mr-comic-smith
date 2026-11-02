"""Filesystem safety: slugs for user-derived names, writes confined to a root, atomic replace."""

import os
import re
import tempfile
import unicodedata
from pathlib import Path

from comic_smith.errors import UsageError

SLUG_MAX = 64
_SLUG_BAD = re.compile(r"[^a-z0-9-]+")


def safe_slug(name: str, fallback: str = "untitled") -> str:
    """Derive a filesystem-safe slug; only [a-z0-9-] survive, so traversal cannot appear."""
    ascii_name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    slug = _SLUG_BAD.sub("-", ascii_name.lower()).strip("-")[:SLUG_MAX].strip("-")
    return slug or fallback


def ensure_inside(root: Path, candidate: Path) -> Path:
    """Resolve candidate and refuse it unless it is inside root (path traversal guard)."""
    root_r = root.resolve()
    cand_r = candidate.resolve()
    if cand_r != root_r and root_r not in cand_r.parents:
        raise UsageError(
            f"Refusing to use a path outside {root_r}: {cand_r}",
            hint="Use a path inside the data directory.",
        )
    return cand_r


def atomic_write(path: Path, data: bytes | str, *, mode: int | None = None) -> Path:
    """Write to a temp file in the same directory, fsync, then rename over the target."""
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = data.encode("utf-8") if isinstance(data, str) else data
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(payload)
            fh.flush()
            os.fsync(fh.fileno())
        if mode is not None:
            Path(tmp).chmod(mode)
        Path(tmp).replace(path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise
    return path
