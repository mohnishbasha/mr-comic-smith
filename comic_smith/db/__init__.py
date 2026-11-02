"""Per-project SQLite database: models, migrations, locking, and the `Project` handle.

Import `Project` from `comic_smith.db.session` and models from `comic_smith.db.models`. They are
deliberately not re-exported here: `comic_smith.assets` imports the models, and `session` imports the
asset store, so eager re-exports would create an import cycle.
"""
