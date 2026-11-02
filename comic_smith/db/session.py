"""Engine factory, SQLite pragmas, and the `Project` handle (ADR-009, ADR-021).

A project is a folder holding `project.db`, `assets/`, and `project.lock`. `Project.open` takes the
single-writer lock, migrates the database to head (with a backup), and exposes sessions and the
asset store. Services never build engines themselves.
"""

import contextlib
import sqlite3
from collections.abc import Callable, Iterator
from pathlib import Path
from types import TracebackType
from typing import Self

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.engine import Connection
from sqlalchemy.orm import Session
from sqlalchemy.pool import ConnectionPoolEntry

from comic_smith.assets.store import AssetStore
from comic_smith.db.lock import ProjectLock
from comic_smith.db.migrate import DEFAULT_SCRIPT_LOCATION, head_revision, migrate_project, revision_number
from comic_smith.errors import ProjectNotFoundError

BUSY_TIMEOUT_MS = 5000
DB_NAME = "project.db"


def _pragma_listener(readonly: bool) -> Callable[[object, ConnectionPoolEntry], None]:
    """Build the per-connection setup hook (pragmas from ARCHITECTURE section 4)."""

    def _on_connect(dbapi_conn: object, _record: ConnectionPoolEntry) -> None:
        if not isinstance(dbapi_conn, sqlite3.Connection):
            return
        # isolation_level=None disables pysqlite's implicit BEGIN so DDL is transactional and the
        # explicit BEGIN in create_project_engine decides when a transaction starts.
        dbapi_conn.isolation_level = None
        pragmas = ["journal_mode=WAL", "synchronous=NORMAL", "foreign_keys=ON"]
        pragmas.append(f"busy_timeout={BUSY_TIMEOUT_MS}")
        if readonly:
            pragmas.append("query_only=ON")
        for pragma in pragmas:
            dbapi_conn.execute(f"PRAGMA {pragma}")

    return _on_connect


def create_project_engine(db_file: Path, *, readonly: bool = False) -> Engine:
    """Create an engine for one project database.

    Writers start with `BEGIN IMMEDIATE` so a read-then-write transaction can never fail later with
    SQLITE_BUSY_SNAPSHOT; readers use a deferred `BEGIN` and `query_only`, so under WAL they never
    block, and are never blocked by, the writer.
    """
    engine = create_engine(f"sqlite:///{db_file}", connect_args={"check_same_thread": False})
    event.listen(engine, "connect", _pragma_listener(readonly))
    begin = "BEGIN" if readonly else "BEGIN IMMEDIATE"

    @event.listens_for(engine, "begin")
    def _begin(conn: Connection) -> None:
        conn.exec_driver_sql(begin)

    return engine


class Project:
    """An open project: write engine, read engine, asset store, and the held lock."""

    def __init__(self, path: Path, engine: Engine, lock: ProjectLock) -> None:
        """Use `Project.open`; the constructor only wires already-validated parts together."""
        self.path = path
        self.db_path = path / DB_NAME
        self.engine = engine
        self._read_engine = create_project_engine(self.db_path, readonly=True)
        self._lock = lock
        self.assets = AssetStore(path / "assets", engine)

    @classmethod
    def open(
        cls, path: Path, *, create: bool = False, script_location: Path = DEFAULT_SCRIPT_LOCATION
    ) -> Self:
        """Open (and when needed create or migrate) the project folder at `path`.

        Args:
            path: The project folder (contains `project.db`).
            create: Create the folder layout when missing instead of raising.
            script_location: Alembic scripts; only tests pass anything but the packaged default.

        Raises:
            ProjectNotFoundError: Nothing at `path` and `create` is False.
            ProjectLockedError: Another live process holds the project lock.
            ProjectMigrationError: The database is newer than this release or the upgrade failed.
        """
        path = Path(path)
        if not (path / DB_NAME).exists():
            if not create:
                raise ProjectNotFoundError(
                    f"No project found at {path}", hint="Check the name, or create a new project."
                )
            path.mkdir(parents=True, exist_ok=True)
        lock = ProjectLock(path / "project.lock")
        lock.acquire()
        engine = create_project_engine(path / DB_NAME)
        try:
            migrate_project(engine, path / DB_NAME, script_location)
            project = cls(path, engine, lock)
            project.assets.clean_tmp()
        except BaseException:
            engine.dispose()
            lock.release()
            raise
        return project

    @property
    def schema_version(self) -> int:
        """Alembic head number this release migrates projects to."""
        return revision_number(head_revision())

    @contextlib.contextmanager
    def session(self, *, readonly: bool = False) -> Iterator[Session]:
        """Transactional session: commit on success, roll back on any exception.

        Args:
            readonly: Use the non-blocking reader engine (writes raise).
        """
        engine = self._read_engine if readonly else self.engine
        with Session(engine, expire_on_commit=False) as session:
            try:
                yield session
                session.commit()
            except BaseException:
                session.rollback()
                raise

    def close(self) -> None:
        """Dispose engines (checkpointing the WAL) and release the lock; idempotent."""
        self._read_engine.dispose()
        self.engine.dispose()
        self._lock.release()

    def __enter__(self) -> Self:
        """Context-manager support so tests and scripts always release the lock."""
        return self

    def __exit__(
        self, exc_type: type[BaseException] | None, exc: BaseException | None, tb: TracebackType | None
    ) -> None:
        """Close on exit."""
        self.close()
