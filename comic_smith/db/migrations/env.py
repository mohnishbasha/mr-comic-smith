"""Alembic environment used programmatically (no alembic.ini at runtime).

`Project.open` hands in a live connection through `config.attributes["connection"]`, so migrations
run on the same pragmas and lock as the rest of the application. Offline mode is not supported
because a project database is always a local file.
"""

from alembic import context
from sqlalchemy.engine import Connection


def run_migrations(connection: Connection) -> None:
    """Run all pending revisions on the given connection."""
    context.configure(connection=connection, target_metadata=None, render_as_batch=True)
    with context.begin_transaction():
        context.run_migrations()


connection = context.config.attributes.get("connection")
if connection is None:
    raise RuntimeError("Migrations must be run through comic_smith.db.session (no connection given).")
run_migrations(connection)
