"""Unit tests for the project database: models, pragmas, migrations, locking, sessions."""

import sqlite3
from pathlib import Path

import pytest
from sqlalchemy import Table, inspect, text
from sqlalchemy.exc import IntegrityError

from comic_smith.db.models import Base
from comic_smith.db.session import BUSY_TIMEOUT_MS, Project
from comic_smith.errors import ProjectLockedError, ProjectMigrationError, ProjectNotFoundError

ARCH_TABLES = {
    "project", "bible", "character", "style", "branch", "strip", "panel", "take", "suggestion_set",
    "story", "page", "book", "export", "event", "job", "asset", "workspace", "cache_entry",
}  # fmt: skip

NOW = "2026-11-02T00:00:00Z"


@pytest.fixture
def project(tmp_path: Path):
    with Project.open(tmp_path / "p", create=True) as proj:
        yield proj


def seed_project(project: Project, pid: str = "prj_1") -> None:
    with project.session() as s:
        s.execute(
            text(
                "INSERT INTO project (id, name, slug, created_at, updated_at, schema_version) "
                "VALUES (:id, 'n', 'n', :t, :t, 1)"
            ),
            {"id": pid, "t": NOW},
        )


def test_db_models_cover_every_architecture_table() -> None:
    assert set(Base.metadata.tables) == ARCH_TABLES


def test_db_models_match_migrated_schema(project: Project) -> None:
    """Models and the frozen DDL agree on columns, nullability, foreign keys, and index names."""
    insp = inspect(project.engine)
    for table in Base.metadata.tables.values():
        cols = {c["name"]: c["nullable"] for c in insp.get_columns(table.name) if c["name"] not in _pk(table)}
        assert cols == {c.name: c.nullable for c in table.columns if not c.primary_key}, table.name
        fks = {
            (tuple(f["constrained_columns"]), f["referred_table"]) for f in insp.get_foreign_keys(table.name)
        }
        assert fks == {((fk.parent.name,), fk.column.table.name) for fk in table.foreign_keys}, table.name
        assert {i["name"] for i in insp.get_indexes(table.name)} == {i.name for i in table.indexes}, (
            table.name
        )


def _pk(table: Table) -> set[str]:
    return {c.name for c in table.primary_key.columns}


@pytest.mark.parametrize(
    ("sql", "params"),
    [
        ("INSERT INTO asset VALUES ('a','m',NULL,NULL,1,'bogus',:t)", {"t": NOW}),
        ("INSERT INTO asset VALUES ('a','m',NULL,NULL,-1,'upload',:t)", {"t": NOW}),
        ("INSERT INTO event (project_id,ts,actor,type,payload_json) VALUES ('p',:t,'bot','x','{}')", {"t": NOW}),
        ("INSERT INTO event (project_id,ts,actor,type,payload_json) VALUES ('p',:t,'user','x','{nope')", {"t": NOW}),
        ("INSERT INTO job (id,project_id,kind,payload_json,created_at,priority) VALUES ('j','p','k','{}',:t,10)", {"t": NOW}),
    ],
)  # fmt: skip
def test_db_check_constraints_reject_bad_rows(project: Project, sql: str, params: dict[str, str]) -> None:
    with pytest.raises(IntegrityError), project.session() as s:
        s.execute(text(sql), params)


def test_db_one_active_branch_per_project(project: Project) -> None:
    seed_project(project)
    ins = "INSERT INTO branch (id, project_id, name, active) VALUES (:id, 'prj_1', :n, 1)"
    with project.session() as s:
        s.execute(text(ins), {"id": "br_1", "n": "main"})
    with pytest.raises(IntegrityError), project.session() as s:
        s.execute(text(ins), {"id": "br_2", "n": "alt"})


def test_db_pragmas_applied_on_every_connection(project: Project) -> None:
    with project.session() as s:
        assert s.execute(text("PRAGMA journal_mode")).scalar() == "wal"
        assert s.execute(text("PRAGMA foreign_keys")).scalar() == 1
        assert s.execute(text("PRAGMA busy_timeout")).scalar() == BUSY_TIMEOUT_MS
        assert s.execute(text("PRAGMA synchronous")).scalar() == 1


def test_db_readonly_session_rejects_writes(project: Project) -> None:
    with pytest.raises(Exception, match="readonly"), project.session(readonly=True) as s:
        s.execute(text("CREATE TABLE x (a)"))


def test_db_session_rolls_back_on_error(project: Project) -> None:
    with pytest.raises(RuntimeError), project.session() as s:
        s.execute(text("INSERT INTO workspace VALUES ('w','n',:t,:t)"), {"t": NOW})
        raise RuntimeError("boom")
    with project.session(readonly=True) as s:
        assert s.execute(text("SELECT count(*) FROM workspace")).scalar() == 0


def test_db_project_open_missing_raises_not_found(tmp_path: Path) -> None:
    with pytest.raises(ProjectNotFoundError):
        Project.open(tmp_path / "nope")
    assert not (tmp_path / "nope").exists()


def test_db_project_lock_blocks_second_open_until_close(tmp_path: Path) -> None:
    first = Project.open(tmp_path / "p", create=True)
    with pytest.raises(ProjectLockedError):
        Project.open(tmp_path / "p")
    first.close()
    first.close()
    Project.open(tmp_path / "p").close()


def test_db_project_open_failure_releases_lock(tmp_path: Path) -> None:
    proj = Project.open(tmp_path / "p", create=True)
    proj.close()
    with sqlite3.connect(tmp_path / "p" / "project.db") as raw:
        raw.execute("UPDATE alembic_version SET version_num = '9999'")
    with pytest.raises(ProjectMigrationError) as err:
        Project.open(tmp_path / "p")
    assert "newer" in err.value.message
    assert not list((tmp_path / "p").glob("project.db.bak-*"))
    raw = sqlite3.connect(tmp_path / "p" / "project.db")
    raw.execute("UPDATE alembic_version SET version_num = '0001'")
    raw.commit()
    raw.close()
    Project.open(tmp_path / "p").close()


def test_db_open_existing_empty_file_migrates_without_backup(tmp_path: Path) -> None:
    (tmp_path / "p").mkdir()
    (tmp_path / "p" / "project.db").touch()
    with Project.open(tmp_path / "p") as proj:
        assert proj.schema_version == 1
    assert not list((tmp_path / "p").glob("project.db.bak-*"))


def test_db_reopen_does_not_back_up_when_current(tmp_path: Path) -> None:
    Project.open(tmp_path / "p", create=True).close()
    Project.open(tmp_path / "p").close()
    assert not list((tmp_path / "p").glob("project.db.bak-*"))
