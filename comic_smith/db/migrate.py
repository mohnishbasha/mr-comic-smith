"""Programmatic Alembic upgrade with backup and restore (ARCHITECTURE section 4.3).

No `alembic.ini` is used at runtime: the Config is built in code with `script_location` pointing at
the package's `migrations/` directory, which ships inside the wheel.
"""

import shutil
import sqlite3
from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import Engine, inspect, text

from comic_smith.errors import ProjectMigrationError

DEFAULT_SCRIPT_LOCATION = Path(__file__).parent / "migrations"


def _config(script_location: Path) -> Config:
    """Build an in-memory Alembic Config; env.py reads the connection from `attributes`."""
    cfg = Config()
    cfg.set_main_option("script_location", str(script_location))
    return cfg


def revision_number(revision: str | None) -> int:
    """Alembic revision ids in this project are zero-padded integers; None means version 0."""
    return int(revision) if revision else 0


def head_revision(script_location: Path = DEFAULT_SCRIPT_LOCATION) -> str:
    """The newest revision the code knows about."""
    head = ScriptDirectory.from_config(_config(script_location)).get_current_head()
    if head is None:
        raise ProjectMigrationError("No database revisions are installed.")
    return head


def current_revision(engine: Engine) -> str | None:
    """The revision stored in `alembic_version`, or None for a database with none."""
    with engine.connect() as conn:
        return MigrationContext.configure(conn).get_current_revision()


def _has_tables(engine: Engine) -> bool:
    """True when the file already holds user tables (even without an `alembic_version` row)."""
    return bool(inspect(engine).get_table_names())


def backup_database(engine: Engine, backup: Path) -> None:
    """Consistent copy via the SQLite online backup API after a WAL checkpoint."""
    raw = engine.raw_connection()
    try:
        conn = raw.driver_connection
        if not isinstance(conn, sqlite3.Connection):
            raise ProjectMigrationError("Backups need a SQLite connection.")
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        backup.unlink(missing_ok=True)
        dest = sqlite3.connect(backup)
        try:
            conn.backup(dest)
        finally:
            dest.close()
    finally:
        raw.close()


def _restore(engine: Engine, db_file: Path, backup: Path) -> None:
    """Put the pre-migration copy back and drop WAL leftovers."""
    engine.dispose()
    shutil.copyfile(backup, db_file)
    for suffix in ("-wal", "-shm"):
        Path(f"{db_file}{suffix}").unlink(missing_ok=True)


def _check_not_newer(current: str | None, script_location: Path) -> None:
    """Refuse a database written by a newer release (downgrade is unsupported)."""
    known = {r.revision for r in ScriptDirectory.from_config(_config(script_location)).walk_revisions()}
    if current is not None and current not in known:
        raise ProjectMigrationError(
            "This project was created by a newer version of mr-comic-smith.",
            hint="Upgrade mr-comic-smith to open this project.",
            detail=f"database revision {current} is unknown to this release",
        )


def migrate_project(
    engine: Engine, db_file: Path, script_location: Path = DEFAULT_SCRIPT_LOCATION
) -> int | None:
    """Bring the database to head, backing up first when it already holds data.

    Returns:
        The pre-migration schema version when a migration ran on existing data, else None.

    Raises:
        ProjectMigrationError: The database is newer than the code, or the upgrade failed (the
            backup is restored first).
    """
    current = current_revision(engine)
    _check_not_newer(current, script_location)
    head = head_revision(script_location)
    if current == head:
        return None
    old_version = revision_number(current)
    existing = current is not None or _has_tables(engine)
    backup = db_file.with_name(f"{db_file.name}.bak-{old_version}")
    if existing:
        backup_database(engine, backup)
    try:
        _upgrade(engine, script_location, revision_number(head))
    except Exception as exc:
        if existing:
            _restore(engine, db_file, backup)
        raise ProjectMigrationError(
            "The project could not be upgraded; it was restored from the backup.",
            hint=f"Your data is unchanged. A copy is at {backup.name}.",
            detail=f"{type(exc).__name__}: {exc}",
        ) from exc
    return old_version if existing else None


def _upgrade(engine: Engine, script_location: Path, head_number: int) -> None:
    """Run `alembic upgrade head` in one transaction and stamp `project.schema_version`."""
    cfg = _config(script_location)
    with engine.begin() as conn:
        cfg.attributes["connection"] = conn
        command.upgrade(cfg, "head")
        conn.execute(text("UPDATE project SET schema_version = :v"), {"v": head_number})


def downgrade_to_base(engine: Engine, script_location: Path = DEFAULT_SCRIPT_LOCATION) -> None:
    """Drop everything (used by tests and tooling only; never offered to end users)."""
    cfg = _config(script_location)
    with engine.begin() as conn:
        cfg.attributes["connection"] = conn
        command.downgrade(cfg, "base")
