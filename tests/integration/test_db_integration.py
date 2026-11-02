"""Integration tests for migrations, project open, WAL concurrency, and the writer lock."""

import shutil
import sqlite3
import subprocess
import sys
import textwrap
import threading
from pathlib import Path

import pytest
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError

from comic_smith.db.migrate import (
    DEFAULT_SCRIPT_LOCATION,
    current_revision,
    downgrade_to_base,
    migrate_project,
)
from comic_smith.db.models import Base
from comic_smith.db.session import Project, create_project_engine
from comic_smith.errors import ProjectLockedError, ProjectMigrationError

NOW = "2026-11-02T00:00:00Z"
INSERT_PROJECT = (
    "INSERT INTO project (id,name,slug,created_at,updated_at,schema_version) "
    "VALUES ('prj_1','n','n','2026-11-02T00:00:00Z','2026-11-02T00:00:00Z',1)"
)


def make_script_dir(tmp_path: Path, body: str) -> Path:
    """Copy the packaged migrations and add a 0002 revision whose upgrade() runs `body`."""
    scripts = tmp_path / "migrations"
    shutil.copytree(DEFAULT_SCRIPT_LOCATION, scripts, ignore=shutil.ignore_patterns("__pycache__"))
    (scripts / "versions" / "0002_next.py").write_text(
        textwrap.dedent(
            f"""
            from alembic import op
            revision = "0002"
            down_revision = "0001"
            branch_labels = None
            depends_on = None

            def upgrade():
                op.execute("CREATE TABLE note (id TEXT PRIMARY KEY)")
                {body}

            def downgrade():
                op.execute("DROP TABLE note")
            """
        ),
        encoding="utf-8",
    )
    return scripts


def it_db_migrations_up_and_down_roundtrip(tmp_path: Path) -> None:
    engine = create_project_engine(tmp_path / "project.db")
    migrate_project(engine, tmp_path / "project.db")
    tables = set(inspect(engine).get_table_names())
    assert set(Base.metadata.tables) <= tables
    with engine.begin() as conn:
        conn.execute(text(INSERT_PROJECT))
        conn.execute(
            text("INSERT INTO style (id,project_id,name,preset_json) VALUES ('st_1','prj_1','s','{}')")
        )
        conn.execute(text("UPDATE project SET style_id='st_1'"))
    downgrade_to_base(engine)
    assert set(inspect(engine).get_table_names()) <= {"alembic_version"}
    assert current_revision(engine) is None
    migrate_project(engine, tmp_path / "project.db")
    assert set(Base.metadata.tables) <= set(inspect(engine).get_table_names())
    engine.dispose()


def it_db_project_open_creates_new_project(tmp_path: Path) -> None:
    path = tmp_path / "projects" / "my-comic"
    with Project.open(path, create=True) as proj:
        assert (path / "project.db").is_file()
        assert (path / "assets").is_dir()
        assert (path / "project.lock").is_file()
        assert current_revision(proj.engine) == "0001"
        assert proj.assets.root == path / "assets"
    assert not list(path.glob("project.db.bak-*"))


def it_db_project_open_migrates_old_schema(tmp_path: Path) -> None:
    path = tmp_path / "p"
    with Project.open(path, create=True) as proj, proj.session() as s:
        s.execute(text(INSERT_PROJECT))
    scripts = make_script_dir(tmp_path, "pass")
    with Project.open(path, script_location=scripts) as proj:
        assert current_revision(proj.engine) == "0002"
        with proj.session(readonly=True) as s:
            assert s.execute(text("SELECT schema_version FROM project")).scalar() == 2
            assert s.execute(text("SELECT count(*) FROM note")).scalar() == 0
    backup = path / "project.db.bak-1"
    assert backup.is_file()
    old = sqlite3.connect(backup)
    assert old.execute("SELECT count(*) FROM project").fetchone() == (1,)
    assert old.execute("SELECT name FROM sqlite_master WHERE name='note'").fetchone() is None
    old.close()


def it_db_failed_migration_restores_backup_and_unlocks(tmp_path: Path) -> None:
    path = tmp_path / "p"
    with Project.open(path, create=True) as proj, proj.session() as s:
        s.execute(text(INSERT_PROJECT))
    scripts = make_script_dir(tmp_path, 'raise RuntimeError("bad migration")')
    with pytest.raises(ProjectMigrationError) as err:
        Project.open(path, script_location=scripts)
    assert "bad migration" in (err.value.detail or "")
    assert (path / "project.db.bak-1").is_file()
    with Project.open(path) as proj, proj.session(readonly=True) as s:
        assert current_revision(proj.engine) == "0001"
        assert s.execute(text("SELECT count(*) FROM project")).scalar() == 1
        assert s.execute(text("SELECT name FROM sqlite_master WHERE name='note'")).first() is None


def it_db_wal_concurrent_reader_during_write(tmp_path: Path) -> None:
    with Project.open(tmp_path / "p", create=True) as proj:
        with proj.session() as s:
            s.execute(text(INSERT_PROJECT))
        writer_inside, reader_done = threading.Event(), threading.Event()
        seen: list[object] = []

        def reader() -> None:
            writer_inside.wait(5)
            with proj.session(readonly=True) as s:
                seen.append(s.execute(text("SELECT name FROM project")).scalar())
            reader_done.set()

        thread = threading.Thread(target=reader)
        thread.start()
        with proj.session() as s:
            s.execute(text("UPDATE project SET name='changed'"))
            writer_inside.set()
            assert reader_done.wait(5), "reader blocked behind the open write transaction"
        thread.join()
        assert seen == ["n"]
        with proj.session(readonly=True) as s:
            assert s.execute(text("SELECT name FROM project")).scalar() == "changed"


def it_db_foreign_keys_enforced(tmp_path: Path) -> None:
    with Project.open(tmp_path / "p", create=True) as proj:
        with pytest.raises(IntegrityError), proj.session() as s:
            s.execute(
                text(
                    "INSERT INTO bible (id,project_id,version,json,created_at) VALUES ('b','missing',1,'{}',:t)"
                ),
                {"t": NOW},
            )
        with proj.session() as s:
            s.execute(text(INSERT_PROJECT))
            s.execute(
                text(
                    "INSERT INTO bible (id,project_id,version,json,created_at) VALUES ('b','prj_1',1,'{}',:t)"
                ),
                {"t": NOW},
            )
        with proj.session() as s:
            s.execute(text("DELETE FROM project WHERE id='prj_1'"))
            assert s.execute(text("SELECT count(*) FROM bible")).scalar() == 0


def it_db_lock_held_by_other_process(tmp_path: Path) -> None:
    path = tmp_path / "p"
    # The child reports its own pid (on Windows the venv launcher pid differs from the interpreter's)
    # and exits when stdin closes, so no orphan keeps holding the lock.
    code = (
        "import os, sys\n"
        "from pathlib import Path\n"
        "from comic_smith.db.session import Project\n"
        "p = Project.open(Path(sys.argv[1]), create=True)\n"
        "print('ready', os.getpid(), flush=True)\n"
        "sys.stdin.read()\n"
        "p.close()\n"
    )
    child = subprocess.Popen(
        [sys.executable, "-c", code, str(path)], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True
    )
    try:
        assert child.stdout is not None
        assert child.stdin is not None
        word, pid = child.stdout.readline().split()
        assert word == "ready"
        with pytest.raises(ProjectLockedError) as err:
            Project.open(path)
        assert pid in (err.value.detail or "")
        child.stdin.close()
        child.wait(30)
        Project.open(path).close()
    finally:
        child.kill()
        child.wait(10)
