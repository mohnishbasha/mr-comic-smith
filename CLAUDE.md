@import AGENTS.md

## Memory model
- Product behavior: docs/PRD.md
- Structure, data model, contracts: docs/ARCHITECTURE.md
- UI and lettering rules: docs/DESIGN.md
- What to build next: docs/SPRINT_PLAN.md and the current milestone
- How to test: docs/TEST_PLAN.md
- Model and quality results: docs/EVALS.md

## Key entry points
| Directory | Purpose |
|---|---|
| comic_smith/api.py | Public API |
| comic_smith/story/ | Bible, suggestions, strip writer, finalize |
| comic_smith/panels/compiler.py | Panel Spec -> image request |
| comic_smith/letter/ | Balloon placement and SVG |
| comic_smith/backends/image/ | ComfyUI, Gemini, OpenAI, mock |
| web/studio/src/views/Strips/ | The core screen |

## Before writing any code
1. Find the issue and its acceptance criteria.
2. Read the referenced PRD, ARCHITECTURE, and DESIGN sections.
3. Add TEST_PLAN scenarios.
4. Write the failing test.

## PR checklist
make lint && make typecheck && make test && make visual && make coverage && ./scripts/check-versions.sh

## Claude-specific rules
- When a backend's real API differs from ARCHITECTURE, update ARCHITECTURE in the same PR.
- Prefer changing adapters, prompts, or data files over interfaces.
- Ask before adding a runtime dependency.
- Attach screenshots for UI changes.
