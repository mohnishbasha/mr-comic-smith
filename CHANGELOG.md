# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog 1.1.0](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/spec/v2.0.0.html). Before 1.0.0, minor releases may
break compatibility and the changelog says so.

## [Unreleased]

### Added

- Project scaffold: `mr-comic-smith --version`, `doctor`, and an empty Studio shell.
- Per-project SQLite database with migrations, a content-addressed asset store, and an undoable event log.
- Story engine: a story bible written from your narrative (editable, versioned), three different ideas for the next strip (continue, twist, steer, plus an ending near the end), your own free-text ideas, and script-only strips with panel specs.
- Story branches (create, switch, rename, delete), strip approval, continuity-checked finalize, and undo and redo for every change.
- Auto mode: writes and approves a whole story draft by policy (balanced, steer, twist) up to the target length, then stops before finalize.
- CLI: `new`, `bible`, `suggest`, `strip`, `strips`, `approve`, `branch`, `finalize`, `auto`, `undo`, `redo`, and `history`, all with `--json`.

### Changed

### Deprecated

### Removed

### Fixed

### Security

[Unreleased]: https://github.com/mohnishbasha/mr-comic-smith/commits/develop
