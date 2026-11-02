# mr-comic-smith

Local-first comic studio: narrative or photo -> consistent cast -> co-plotted strips with AI
suggestions -> pages -> book -> PNG/PDF/CBZ/web export.

## Commands
uv sync --all-extras && (cd web/studio && npm ci)   # install
make lint                     # ruff + eslint + em dash check + import-linter
make typecheck                # mypy --strict + tsc --noEmit
make test                     # unit tests (Python + TS)
make test-int                 # integration (Chromium, Ollama tiny, stub ComfyUI)
make visual                   # visual goldens
make coverage                 # coverage + thresholds
make smoke                    # CLI end to end with fakes
make e2e                      # Playwright
make studio-dev               # backend + Vite dev server with mock backends
./scripts/check-versions.sh
uv run mr-comic-smith doctor

## Structure
comic_smith/      core (api.py is the public surface)
web/studio/       Studio UI (React + TS)
reader/           web export reader component
integrations/     pi, goose, opencode, claude-code
docs/             PRD, ARCHITECTURE, DESIGN, SPRINT_PLAN, TEST_PLAN (source of truth)
tests/            unit, integration, visual, smoke, e2e, regression, fixtures

## Code style
Python: mypy --strict, pydantic, SQLAlchemy 2 typed, typed errors, events for every mutation.
TypeScript: strict, no any, Zustand per domain, TanStack Query for server state,
generated API types.

## Rules
- ALWAYS read the relevant docs/ section before changing behavior.
- ALWAYS write a failing test first.
- ALWAYS update docs/ in the same PR when behavior changes.
- ALWAYS route mutations through services and the event log.
- NEVER let an image model render text; use the lettering engine.
- NEVER call the network or a GPU in unit tests.
- NEVER add em dashes.

## Versioning
pyproject.toml [project].version is the single source of truth. Bump with
scripts/bump-version.sh; verify with scripts/check-versions.sh.

## Boundaries
- NEVER weaken or bypass originality, people-attestation, or audience guards.
- NEVER commit real photos of people, model weights, or generated images of real people.
- NEVER add telemetry or third-party scripts to the Studio or reader.
- NEVER push to main or staging directly.
