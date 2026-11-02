"""Unit tests for the content-addressed asset store."""

import hashlib
from collections.abc import Iterator
from datetime import timedelta
from pathlib import Path

import pytest
from sqlalchemy import select

from comic_smith.assets import AssetRef, AssetStore
from comic_smith.db.models import Asset
from comic_smith.db.session import Project
from comic_smith.errors import UsageError

PNG = b"\x89PNG fake bytes"


@pytest.fixture
def project(tmp_path: Path) -> Iterator[Project]:
    with Project.open(tmp_path / "p", create=True) as proj:
        yield proj


@pytest.fixture
def store(project: Project) -> AssetStore:
    return project.assets


def put_png(store: AssetStore, data: bytes = PNG, **kw: int) -> AssetRef:
    return store.put(data, mime="image/png", ext="png", origin="render", **kw)


def rows(project: Project) -> list[str]:
    with project.session(readonly=True) as s:
        return sorted(s.scalars(select(Asset.id)))


def drop_row(project: Project, sha: str) -> None:
    with project.session() as s:
        row = s.get(Asset, sha)
        assert row is not None
        s.delete(row)


def test_assets_store_put_returns_ref_and_layout(store: AssetStore, project: Project) -> None:
    ref = put_png(store, width=4, height=3)
    sha = hashlib.sha256(PNG).hexdigest()
    assert ref == AssetRef(sha256=sha, mime="image/png", ext="png", width=4, height=3)
    assert store.path(sha) == store.root / sha[:2] / f"{sha}.png"
    assert store.read(sha) == PNG
    with store.open(sha) as fh:
        assert fh.read() == PNG
    with project.session(readonly=True) as s:
        row = s.get(Asset, sha)
        assert row is not None
        assert (row.mime, row.bytes, row.origin, row.width) == ("image/png", len(PNG), "render", 4)


def test_assets_store_write_atomic_temp_then_rename(
    store: AssetStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[tuple[Path, Path]] = []
    real = Path.replace

    def spy(self: Path, target: str | Path) -> Path:
        calls.append((self, Path(target)))
        return real(self, target)

    monkeypatch.setattr(Path, "replace", spy)
    ref = put_png(store)
    ((src, dst),) = calls
    assert src.parent == store.root / ".tmp"
    assert dst == store.path(ref.sha256)
    assert not src.exists()


def test_assets_store_write_idempotent_same_sha(store: AssetStore, project: Project) -> None:
    first = put_png(store)
    path = store.path(first.sha256)
    mtime = path.stat().st_mtime_ns
    second = store.put(PNG, mime="image/png", ext="png", origin="upload")
    assert second == first
    assert path.stat().st_mtime_ns == mtime
    assert rows(project) == [first.sha256]
    with project.session(readonly=True) as s:
        row = s.get(Asset, first.sha256)
        assert row is not None
        assert row.origin == "render"


def test_assets_store_same_bytes_other_ext_reuses_file(store: AssetStore) -> None:
    first = put_png(store)
    again = store.put(PNG, mime="image/png", ext="bin", origin="render")
    assert again.ext == "png"
    assert list(store.root.rglob("*.bin")) == []
    assert first.sha256 == again.sha256


def test_assets_store_crash_mid_write_leaves_no_partial_file(
    store: AssetStore, project: Project, monkeypatch: pytest.MonkeyPatch
) -> None:
    def boom(self: Path, target: str | Path) -> Path:
        raise OSError("disk pulled")

    monkeypatch.setattr(Path, "replace", boom)
    with pytest.raises(OSError, match="disk pulled"):
        put_png(store)
    assert not store.exists(hashlib.sha256(PNG).hexdigest())
    assert list(store.root.rglob("*.png")) == []
    assert list((store.root / ".tmp").iterdir()) == []
    assert rows(project) == []


def test_assets_store_clean_tmp_removes_killed_write_leftovers(store: AssetStore) -> None:
    tmp = store.root / ".tmp"
    tmp.mkdir(exist_ok=True)
    (tmp / "killed.part").write_bytes(b"half")
    assert store.clean_tmp() == 1
    assert list(tmp.iterdir()) == []
    assert store.clean_tmp() == 0


def test_assets_store_put_repairs_missing_row_and_joins_session(store: AssetStore, project: Project) -> None:
    ref = put_png(store)
    drop_row(project, ref.sha256)
    assert rows(project) == []
    with project.session() as s:
        store.put(PNG, mime="image/png", ext="png", origin="render", session=s)
    assert rows(project) == [ref.sha256]


def test_assets_store_rejects_bad_ext_and_bad_sha(store: AssetStore) -> None:
    with pytest.raises(UsageError):
        store.put(b"x", mime="text/plain", ext="../x", origin="upload")
    with pytest.raises(UsageError):
        store.path("../../etc/passwd")
    with pytest.raises(FileNotFoundError):
        store.read("0" * 64)
    assert not store.exists("f" * 64)


def test_assets_store_gc_removes_only_unreferenced(store: AssetStore, project: Project) -> None:
    keep = put_png(store, b"keep")
    drop = put_png(store, b"drop")
    assert store.gc({keep.sha256}, dry_run=True) == [drop.sha256]
    assert store.exists(drop.sha256)
    assert store.gc({keep.sha256}) == [drop.sha256]
    assert not store.exists(drop.sha256)
    assert store.exists(keep.sha256)
    assert rows(project) == [keep.sha256]


def test_assets_store_gc_grace_period_protects_new_assets(store: AssetStore) -> None:
    fresh = put_png(store)
    assert store.gc(set(), grace=timedelta(hours=24)) == []
    assert store.exists(fresh.sha256)


def test_assets_store_gc_removes_orphan_file_without_row(store: AssetStore, project: Project) -> None:
    ref = put_png(store)
    drop_row(project, ref.sha256)
    assert store.gc(set(), grace=timedelta(days=1)) == []
    assert store.gc(set()) == [ref.sha256]
    assert not store.exists(ref.sha256)
