# Sprint retrospectives

## Sprint 0: Scaffold (completed 2026-11-02, tag `sprint-0-complete`)

**Built** (PR #96, issues #1 to #12): five spec documents, uv/hatchling package with optional
extras (base install has no torch), typer CLI with `--version`, `doctor`, and `studio`, layered
configuration, typed error hierarchy mapped to exit codes and RFC 9457, per-project SQLite with
an Alembic baseline and pre-migration backups, a single-writer project lock, a content-addressed
asset store, an undoable event log, the React Studio shell served by FastAPI with a strict CSP,
ruff + mypy --strict + import-linter + em/en dash hook, coverage floors, an SSIM visual diff
helper, CI on Ubuntu, macOS, and Windows (Python 3.12 and 3.13), version scripts, and the agent
files (AGENTS, CLAUDE, SKILLS, SOUL, three skills).

**Spec sections updated:** ARCHITECTURE section 4 (event `discarded` column and undo/redo marker
events, `workspace` and `cache_entry` tables, reader and writer engines, lock file);
TEST_PLAN statuses through `scripts/sync-test-plan.py`.

**Tests added:** 141 Python (unit and SQLite-backed integration), 22 vitest, 3 Playwright.

**Coverage:** 0 to 93.3 percent overall (events 100, assets 100, server 97.5, cli 92.6).

**What worked:** writing the spec documents in parallel kept Step 1 short; reusing the
mr-audio-smith tooling (dash checker, coverage script, TEST_PLAN sync) saved most of a day; a
model-based hypothesis test caught an undo/redo ordering bug before review.

**What did not:** the project lock used `fcntl` only and failed on the Windows runners twice: first
because the module did not import, then because the test compared the pid of the venv launcher
instead of the interpreter. GitHub returned HTTP 500 during the burst of label creation. The
project board could not be created because the CLI token lacks the `project` scope.

**What to change:** run platform-specific code paths through a tiny shim with both branches covered
by CI before merging; label and issue scripts retry with backoff; the maintainer grants the
`project` scope (`gh auth refresh -s project`) and `scripts/create-issues.py --project-only`
adds every issue to the board afterwards.
