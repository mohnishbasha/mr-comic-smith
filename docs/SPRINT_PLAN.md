# mr-comic-smith Sprint Plan

Version: 1.0 (spec, pre-implementation)
Date: 2026-11-02
Owner: Serverless Ventures LLC
Related documents: PRD.md (FR, NFR, and US ids), ARCHITECTURE.md (ADRs and data formats), DESIGN.md (Studio, child mode, and reader), TEST_PLAN.md (scenario ids)

This plan lists every sprint (0 to 9) and every task of the mr-comic-smith build. It is the input to a script that parses the task blocks below into GitHub issues, so the task format is fixed and must not be reformatted.

## How to read this plan

### Estimate legend

| Size | Effort |
|---|---|
| S | half a day |
| M | 1 day |
| L | 2 days |
| XL | 3 or more days; split into smaller tasks before starting |

Three tasks are XL (S2-T05, S3-T06, S3-T11). They keep one task id and one issue, and their descriptions list the sub-parts. Split each into the listed sub-issues before starting it. If any other task grows past L during implementation, stop and split it before continuing.

### Delivery process

Tasks run in dependency order. Test-driven development applies to every issue: write the failing test named in the task's **Tests** field (or add the scenario to TEST_PLAN first), then the code. Read the PRD, ARCHITECTURE, and DESIGN references on a task before coding it. Each sprint ends at a hard-stop gate: the gate checklist must be fully checked before the next sprint starts.

### Task format

Each task is a `### SN-Tnn: Title` heading followed by Labels, Estimate, Spec refs, Description, Acceptance criteria, Tests, and Depends on. Spec refs name PRD functional, non-functional, and user story ids (FR, NFR, US), ARCHITECTURE decision ids (ADR) or sections, and DESIGN sections. Tests name TEST_PLAN ids following the convention below. Labels come from the 48-label taxonomy in Step 2.4 of the build prompt.

```
Unit:        test_{module}_{function}_{scenario}_{expected_outcome}
Integration: it_{component}_{operation}_{scenario}
Smoke:       smoke_{feature}_{minimal_assertion}
E2E:         e2e_{user_story_id}_{scenario}
Regression:  regression_{gh_issue_number}_{what_was_broken}
Visual:      vis_{surface}_{template_or_state}
```

Items that the executing agent cannot complete (ComfyUI GPU integration on the self-hosted runner, nightly cloud runs that need secrets, human rating rounds, PDF viewer and CBZ reader checks, narration with mr-audio-smith, PyPI, npm, and GHCR publishing that needs trusted-publisher setup by the owner, a GPU Kubernetes cluster install, and DNS for getcomicsmith.com) are marked in the acceptance criteria or Tests as manual or deferred steps and are recorded honestly in TEST_PLAN as deferred or skipped.

## Sprint overview

| Sprint | Name | Duration | Goal | Release |
|---|---|---|---|---|
| 0 | Scaffold | 1 week | Tooling, CI, DB, events, Studio shell, agent files |  |
| 1 | Story Engine | 1 week | Bible, arc, suggestions, strip writer, branching, finalize (no images) | 0.1.0 |
| 2 | Cast, Style, Backends | 1 week | Reference ingest, vision, sheets, styles, ComfyUI/Gemini/OpenAI/mock | 0.2.0 |
| 3 | Panels, Lettering, Strips | 2 weeks | Render, QA, retakes, lettering engine, Strips view (the product) | 0.3.0 |
| 4 | Pages and Book | 1 week | Templates, pagination, book builder, cover | 0.4.0 |
| 5 | Export | 1 week | PNG/JPG/WebP, PDF, CBZ, long strip, web reader | 0.5.0 |
| 6 | Release | 1 week | Child mode, auto mode, safety review, evals, docs | **1.0.0** |
| 7 | Server and MCP | 1 week | Server hardening, LAN classroom, MCP tools | 1.1.0-rc |
| 8 | Harness Integrations | 1 week | Pi, Goose, OpenCode, Claude Code | 1.1.0-rc |
| 9 | Packaging | 1 week | Docker, Compose, Helm, cosign | **1.1.0** |

Total: 11 weeks.

## Dependency graph

```
S0 Scaffold ─> S1 Story engine ─> S2 Cast, style, backends ─> S3 Panels, lettering, strips (core)
                                                                   │
                                                  S4 Pages and book <┘
                                                         │
                                                  S5 Export ─> S6 Release v1.0.0
                                                                   │
                                        S7 Server + MCP ─> S8 Harnesses ─> S9 Packaging
```

Sprint 3 depends on Sprint 2 as a whole, Sprint 4 on Sprint 3, and so on. Tasks that depend on "Sprint N" depend on every task of that sprint; the sprint gate is the checkpoint.

## Milestones

Milestones are created by Step 2.5 of the build prompt. Adjust due dates to the actual start date; keep the relative durations (Sprint 3 is two weeks).

| Milestone | Description | Due |
|---|---|---|
| Sprint 0: Scaffold | Tooling, CI, database, event log, Studio shell, agent files, empty CLI, spec docs committed | 2026-11-09 |
| Sprint 1: Story Engine | LLM providers, schemas, bible, arc, suggestions, strip writer, moderation, branching, finalize, story CLI | 2026-11-16 |
| Sprint 2: Cast, Style, Backends | Asset ingest, vision, people and originality guards, styles, character sheets, ComfyUI, Gemini, OpenAI, mock backends | 2026-11-23 |
| Sprint 3: Panels, Lettering, Strips | Prompt compiler, jobs, render, QA, lettering engine and SVG, strips, Studio Cast, Story, Strips views, lettering editor | 2026-12-07 |
| Sprint 4: Pages and Book | Layout templates, auto-paginate, page SVG, book builder, covers, Pages and Book views | 2026-12-14 |
| Sprint 5: Export | Chromium renderer, image, PDF, CBZ, and web exports, reader component, export dialog and CLI | 2026-12-21 |
| Sprint 6: Release v1.0.0 | Child mode, auto mode, safety review, evaluations, docs site, licenses, release pipeline, v1.0.0 | 2026-12-28 |
| Sprint 7: Server and MCP | REST server hardening, LAN classroom mode, MCP server (stdio and HTTP), remote CLI | 2027-01-04 |
| Sprint 8: Harness Integrations | Pi extension, Goose toolkit, OpenCode config, Claude Code skill, harness smoke tests | 2027-01-11 |
| Sprint 9: Packaging | Docker (CPU, CUDA, ComfyUI, multi-arch), Compose, Helm, cosign signing | 2027-01-18 |

(All due at 23:59:59Z on the date shown.)

---

## Sprint 0: Scaffold

**Milestone:** Sprint 0: Scaffold
**Duration:** 1 week
**Goal:** A repository where `mr-comic-smith --version`, `doctor`, and `studio` (empty shell) run; database migrations work; CI is green on all platforms; every agent file exists.

### S0-T01: Commit the five spec documents
- **Labels:** type: spec, area: ci, priority: p0, size: L, sprint: 0
- **Estimate:** L
- **Spec refs:** PRD (all sections), ARCHITECTURE (all sections), DESIGN (all sections)
- **Description:** Generate PRD, ARCHITECTURE, DESIGN, SPRINT_PLAN, and TEST_PLAN per Step 1 of the build prompt. This task is completed before Step 2 and is recorded retroactively as an issue.
- **Acceptance criteria:**
  - [ ] All five files exist under `docs/` with every required section
  - [ ] Every FR has acceptance criteria; every US maps to at least one FR
  - [ ] First commit on `main`
  - [ ] No em dash (U+2014) or en dash (U+2013) appears in any committed file
- **Tests:** test_docs_spec_files_all_five_present, test_docs_required_sections_present_in_each_spec, test_docs_every_fr_has_acceptance_criteria, test_docs_every_us_maps_to_at_least_one_fr, test_docs_no_em_or_en_dash_in_committed_files
- **Depends on:** none

### S0-T02: Create the Python project skeleton with uv
- **Labels:** type: chore, area: cli, priority: p0, size: M, sprint: 0
- **Estimate:** M
- **Spec refs:** PRD NFR-008, NFR-001, ARCHITECTURE ADR-001
- **Description:** Create `pyproject.toml` (hatchling build backend, Python `>=3.12,<3.14`), `uv.lock`, and the `comic_smith/` package with the version read via `importlib.metadata` and a typer CLI exposing `--version`. Declare optional dependency groups: `comfyui`, `gemini`, `openai`, `anthropic`, `ocr`, `server` (included by default because Studio needs it), `mcp`, and `dev`.
- **Acceptance criteria:**
  - [ ] `uv sync --all-extras --dev` works on macOS arm64, Linux x86_64, and Linux arm64
  - [ ] `uv run mr-comic-smith --version` prints the version from `pyproject.toml`
  - [ ] Base install does not pull torch
- **Tests:** test_cli_version_prints_pyproject_version, smoke_cli_version_exits_zero, test_packaging_base_install_does_not_pull_torch, test_packaging_optional_extras_declared, test_packaging_python_range_is_312_to_313, it_packaging_uv_sync_all_extras_clean_env
- **Depends on:** S0-T01

### S0-T03: Add repository hygiene files
- **Labels:** type: chore, area: ci, priority: p0, size: S, sprint: 0
- **Estimate:** S
- **Spec refs:** PRD NFR-011, ARCHITECTURE Security and safety model
- **Description:** Create `.gitignore`, `.editorconfig`, `.gitattributes` (Git LFS for `tests/fixtures/images/*`, `tests/fixtures/goldens/*`, and `comic_smith/letter/fonts/*`), `LICENSE` (MIT, Serverless Ventures LLC, 2026), a `THIRD_PARTY_LICENSES.md` stub, `CHANGELOG.md` with `[Unreleased]`, `SECURITY.md`, `CODE_OF_CONDUCT.md`, and `CONTRIBUTING.md` (DCO sign-off). The `.gitignore` must include these groups. Python: `__pycache__/`, `*.py[cod]`, `.venv/`, `dist/`, `build/`, `*.egg-info/`, `.mypy_cache/`, `.ruff_cache/`, `.pytest_cache/`. TypeScript, Node, Bun: `node_modules/`, `*.tsbuildinfo`, `web/studio/dist/`, `reader/dist/`, `integrations/pi/dist/`, `comic_smith/server/static/`, `.bun/`. Environment: `.env`, `.env.*`, `!.env.*.example`. Test and coverage: `coverage/`, `.coverage`, `htmlcov/`, `coverage.xml`, `playwright-report/`, `test-results/`, `tests/visual/__diff__/`. Product runtime: `projects/`, `exports/`, `library/`, `*.db`, `*.db-shm`, `*.db-wal`, with the exception `!tests/fixtures/projects/**/project.db`. Models and backends: `models/`, `ComfyUI/`, `*.safetensors`, `*.ckpt`, `*.gguf`. Agent sessions: `.pi/sessions/`, `.agent/sessions/`, `CLAUDE.local.md`. OS and editor: `.DS_Store`, `Thumbs.db`, `.vscode/settings.json`, `.idea/`. Lock files ARE tracked: `uv.lock`, `bun.lockb`, `package-lock.json`.
- **Acceptance criteria:**
  - [ ] All listed files are present
  - [ ] Fixtures are not ignored (`git check-ignore tests/fixtures/projects/finalized-duck/project.db` prints nothing)
  - [ ] User projects are ignored (`git check-ignore projects/my-duck/project.db` prints the path)
  - [ ] LICENSE names Serverless Ventures LLC and year 2026
- **Tests:** test_repo_gitignore_contains_required_groups, test_repo_gitignore_fixtures_not_ignored, test_repo_gitignore_user_projects_ignored, test_repo_gitattributes_lfs_patterns_declared, test_repo_license_names_serverless_ventures_2026, test_repo_hygiene_files_all_present
- **Depends on:** S0-T02

### S0-T04: Set up lint, format, and type-check toolchain
- **Labels:** type: chore, area: ci, priority: p0, size: S, sprint: 0
- **Estimate:** S
- **Spec refs:** PRD NFR-011, ARCHITECTURE Module map
- **Description:** Configure ruff (lint and format, rules `E,F,W,I,N,UP,B,A,C4,SIM,RUF,S,PTH,TID,PL`), mypy `--strict`, ESLint (`@typescript-eslint/strict-type-checked`), Prettier, and pre-commit (ruff, mypy, eslint, codespell, check-yaml, check-json, end-of-file-fixer, plus a hook rejecting U+2014 and U+2013 in `*.md *.py *.ts *.tsx *.json *.yaml`). Add a `Makefile` with targets `lint format typecheck test test-int visual coverage smoke e2e check-versions build studio-dev`.
- **Acceptance criteria:**
  - [ ] `make lint typecheck` exits 0
  - [ ] The dash hook fails on a test file containing U+2014
  - [ ] The dash hook fails on a test file containing U+2013
- **Tests:** test_lint_ruff_rules_configured_as_specified, test_lint_mypy_strict_enabled, test_lint_em_dash_hook_rejects_u2014, test_lint_en_dash_hook_rejects_u2013, test_lint_makefile_targets_all_defined, smoke_make_lint_typecheck_exit_zero
- **Depends on:** S0-T02

### S0-T05: Build test harness, coverage thresholds, and visual diff
- **Labels:** type: test, area: ci, priority: p0, size: M, sprint: 0
- **Estimate:** M
- **Spec refs:** PRD NFR-009, ARCHITECTURE ADR-008
- **Description:** Install pytest, pytest-cov, pytest-asyncio, pytest-timeout, hypothesis, respx, and syrupy; vitest with @testing-library/react; and Playwright. Add the visual diff helper `tests/visual/compare.py` (SSIM via scikit-image plus a pixel threshold of 0.1 percent). Create `tests/{unit,integration,smoke,e2e,visual,regression,fixtures}`. Add `.coverage-thresholds.toml` and `scripts/check-coverage.py`.
- **Acceptance criteria:**
  - [ ] `make test` and `make visual` run
  - [ ] The threshold script fails when any module is under its target
  - [ ] Visual diff passes identical images and fails images that differ by more than 0.1 percent of pixels
- **Tests:** test_harness_coverage_script_fails_under_threshold, test_harness_coverage_script_passes_at_threshold, test_harness_thresholds_toml_matches_test_plan, test_visual_compare_identical_images_pass, test_visual_compare_over_threshold_fails, test_visual_compare_ssim_detects_shifted_glyph, smoke_make_test_and_visual_run
- **Depends on:** S0-T04

### S0-T06: Create database, migrations, and content-addressed asset store
- **Labels:** type: feature, area: db, priority: p0, size: M, sprint: 0
- **Estimate:** M
- **Spec refs:** PRD FR-001, NFR-006, ARCHITECTURE ADR-009, Data model
- **Description:** SQLAlchemy 2 models for every table in ARCHITECTURE, Alembic migrations, WAL mode, foreign keys on, and `Project.open(path)` that creates or migrates a project. Build the content-addressed asset store with atomic writes (temp file then rename).
- **Acceptance criteria:**
  - [ ] Migrations up and down are tested
  - [ ] Concurrent readers during a write work (WAL)
  - [ ] Asset write is atomic (temp + rename) and idempotent
  - [ ] Projects survive restarts; a kill during a write never corrupts the project (NFR-006)
- **Tests:** it_db_migrations_up_and_down_roundtrip, it_db_project_open_creates_new_project, it_db_project_open_migrates_old_schema, it_db_wal_concurrent_reader_during_write, it_db_foreign_keys_enforced, test_assets_store_write_atomic_temp_then_rename, test_assets_store_write_idempotent_same_sha, test_assets_store_crash_mid_write_leaves_no_partial_file
- **Depends on:** S0-T05

### S0-T07: Implement event log and undo framework
- **Labels:** type: feature, area: db, priority: p1, size: M, sprint: 0
- **Estimate:** M
- **Spec refs:** PRD FR-033, US-021, ARCHITECTURE ADR-010
- **Description:** `events.py` with `apply(event)`, `undo()`, `redo()`, inverse payloads, and an actor field. Every service mutation goes through it so history survives restarts and powers auto-mode audit.
- **Acceptance criteria:**
  - [ ] Property test: random sequences of apply, undo, and redo restore identical state
  - [ ] History survives a restart (FR-033)
  - [ ] Every service mutation goes through `apply`; no front door writes the database directly
- **Tests:** test_events_apply_records_actor_and_inverse, test_events_undo_redo_roundtrip_lettering_edit, test_events_property_random_apply_undo_redo_restores_state, test_events_redo_cleared_after_new_apply, test_events_history_survives_restart, test_events_service_mutations_all_go_through_apply
- **Depends on:** S0-T06

### S0-T08: Build the Studio shell
- **Labels:** type: feature, area: studio, priority: p0, size: M, sprint: 0
- **Estimate:** M
- **Spec refs:** PRD FR-029, ARCHITECTURE ADR-002, DESIGN Information architecture and navigation
- **Description:** `web/studio` with Vite, React 18, TypeScript, Zustand, TanStack Query, and React Router. Design tokens from the Design System become CSS variables. The app frame has a header, navigation tabs, and an empty Home. FastAPI serves the built assets at `/` and `/v1/healthz`. `mr-comic-smith studio` builds if needed (dev) or serves the bundled static assets (release) and opens the browser, binding to 127.0.0.1 by default.
- **Acceptance criteria:**
  - [ ] Studio loads in Chrome, Safari, and Firefox
  - [ ] Light and dark themes work
  - [ ] Playwright smoke passes
  - [ ] Server binds to 127.0.0.1 by default
- **Tests:** smoke_studio_shell_loads_in_chromium, e2e_US002_empty_home_prompts_for_story_idea, test_server_healthz_returns_ok, it_server_serves_built_studio_at_root, test_studio_tokens_light_and_dark_css_variables_defined, test_cli_studio_binds_loopback_by_default, test_studio_theme_toggle_persists_in_try_catch_storage
- **Depends on:** S0-T02

### S0-T09: Create CI workflow
- **Labels:** type: chore, area: ci, priority: p0, size: M, sprint: 0
- **Estimate:** M
- **Spec refs:** PRD NFR-008, ARCHITECTURE Deployment topologies
- **Description:** `.github/workflows/ci.yml` with jobs `lint-and-typecheck` (ubuntu, macos, windows), `unit-tests` (3 OS x py3.12 and 3.13, plus vitest), `coverage` (ubuntu, Codecov), `integration-tests` (ubuntu; Ollama tiny model; Playwright Chromium; stub ComfyUI server), `visual-regression` (ubuntu, fixed fonts, uploads diff images on failure), `e2e-tests`, `check-versions`, and `smoke`. Add `gpu-integration` on the self-hosted `gpu` runner (dispatch and PRs to staging and main). Configure Dependabot for uv, npm, github-actions, and docker.
- **Acceptance criteria:**
  - [ ] All jobs green on the skeleton
  - [ ] Concurrency cancels superseded runs
- **Tests:** test_ci_workflow_declares_all_required_jobs, test_ci_concurrency_cancels_superseded_runs, test_ci_dependabot_covers_uv_npm_actions_docker, test_ci_gpu_integration_targets_self_hosted_gpu_label, smoke_ci_skeleton_all_jobs_green
- **Depends on:** S0-T05, S0-T08

### S0-T10: Add version scripts
- **Labels:** type: chore, area: ci, priority: p1, size: S, sprint: 0
- **Estimate:** S
- **Spec refs:** PRD NFR-011, ARCHITECTURE Deployment topologies
- **Description:** `scripts/check-versions.sh`, `scripts/bump-version.sh`, and `scripts/extract-changelog.sh` per the Versioning section of the build prompt. check-versions compares `pyproject.toml`, `package.json` files, and the Helm chart.
- **Acceptance criteria:**
  - [ ] A version mismatch exits 1 and names the file
  - [ ] `extract-changelog.sh` prints only the requested section
- **Tests:** test_scripts_check_versions_mismatch_exits_one_naming_file, test_scripts_check_versions_match_exits_zero, test_scripts_bump_version_updates_all_files, test_scripts_extract_changelog_prints_only_requested_section, test_scripts_extract_changelog_missing_section_fails
- **Depends on:** S0-T08

### S0-T11: Create agent repository files
- **Labels:** type: docs, area: harness, priority: p0, size: M, sprint: 0
- **Estimate:** M
- **Spec refs:** ARCHITECTURE ADR-013, Appendix K of the build prompt
- **Description:** `AGENTS.md`, `CLAUDE.md`, `SKILLS.md`, `SOUL.md`, `.agent/skills/run-tests/`, `.agent/skills/check-types/`, and `.agent/skills/make-fixture-comic/` per Appendix K.
- **Acceptance criteria:**
  - [ ] `CLAUDE.md` starts with `@import AGENTS.md`
  - [ ] The three skills run green
  - [ ] `SOUL.md` has at least 6 hard constraints and contains no commands or paths
- **Tests:** test_agent_files_all_present, test_agent_claude_md_starts_with_import_agents_md, test_agent_soul_md_has_at_least_six_hard_constraints, test_agent_soul_md_contains_no_commands_or_paths, test_agent_skills_run_tests_check_types_make_fixture_comic_exist, smoke_agent_skills_run_green
- **Depends on:** S0-T04, S0-T05

### S0-T12: Add config and doctor skeleton
- **Labels:** type: feature, area: cli, priority: p1, size: M, sprint: 0
- **Estimate:** M
- **Spec refs:** PRD FR-031, US-022, NFR-008, ARCHITECTURE Contracts
- **Description:** pydantic-settings with env prefix `COMIC_SMITH_`, a project-level `comic-smith.toml`, and precedence flags > env > file > defaults. Doctor with a check registry covering Python version, disk space, Chromium (Playwright) present, fonts present, and a writable data dir; each failure carries a fix hint.
- **Acceptance criteria:**
  - [ ] Precedence unit tests pass for flags, env, file, and defaults
  - [ ] `doctor --json` emits parseable JSON
  - [ ] Exit code 3 on a required-check failure
- **Tests:** test_config_precedence_flags_over_env, test_config_precedence_env_over_file, test_config_precedence_file_over_defaults, test_config_env_prefix_comic_smith, test_doctor_check_registry_runs_all_checks, test_doctor_json_output_parses, test_doctor_required_failure_exits_three, test_doctor_missing_chromium_reports_fix_hint, test_doctor_unwritable_data_dir_fails
- **Depends on:** S0-T02

### Sprint 0 Gate
Hard stop. Sprint 1 does not start until every item is checked.
- [ ] Spec docs committed and current
- [ ] `make lint typecheck test visual smoke` green locally
- [ ] CI green on ubuntu, macos, windows
- [ ] `uv tool install .` then `mr-comic-smith doctor` and `studio` work
- [ ] Migrations and event log tested
- [ ] All agent files present and validated
- [ ] Retrospective written, `sprint-0-complete` tagged

---

## Sprint 1: Story Engine

**Milestone:** Sprint 1: Story Engine
**Duration:** 1 week
**Goal:** From the CLI, a user can create a project from narrative, get a story bible, receive plot suggestions, choose or write beats, get strip scripts as validated Panel Specs, branch, and finalize, all without any images.

### S1-T01: Build LLM provider interface and providers
- **Labels:** type: feature, area: backend-llm, priority: p0, size: L, sprint: 1
- **Estimate:** L
- **Spec refs:** PRD FR-013, NFR-001, ARCHITECTURE ADR-007, ADR-012, Contracts (LLMProvider)
- **Description:** `LLMProvider.complete_json` takes a JSON Schema. Providers: `OllamaProvider` (REST `/api/chat` with `format` set to the schema), `AnthropicProvider` (official SDK, tool-use or structured output for JSON), `OpenAICompatProvider` (`response_format` JSON schema), and `FakeProvider` (recorded fixtures keyed by prompt hash). Retries with backoff, a timeout, and token usage recorded per call. Provider string format: `ollama:qwen3:14b`, `anthropic:<model-id>`, `openai_compat:<base_url>#<model>`.
- **Acceptance criteria:**
  - [ ] respx unit tests exist for each provider
  - [ ] Ollama integration test passes with a tiny model
  - [ ] Schema-invalid output triggers one corrective retry that includes the validation errors
  - [ ] A second invalid output raises a typed error
- **Tests:** test_llm_ollama_chat_request_sends_schema_in_format, test_llm_anthropic_provider_uses_tool_use_for_json, test_llm_openai_compat_response_format_json_schema, test_llm_fake_provider_replays_by_prompt_hash, test_llm_fake_provider_unknown_hash_names_record_command, test_llm_provider_string_parsing_all_three_formats, test_llm_complete_json_invalid_output_one_corrective_retry, test_llm_complete_json_second_failure_raises, test_llm_retry_backoff_on_5xx, test_llm_timeout_raises_provider_timeout, test_llm_token_usage_recorded_per_call, it_ollama_tiny_model_returns_schema_valid_json
- **Depends on:** Sprint 0

### S1-T02: Define JSON Schemas and models
- **Labels:** type: feature, area: story, priority: p0, size: M, sprint: 1
- **Estimate:** M
- **Spec refs:** PRD FR-009, FR-013, ARCHITECTURE ADR-007, Data formats
- **Description:** pydantic models and exported JSON Schemas for the bible, suggestions, panel spec, beat, and continuity report. The exported files are published under `schemas/`.
- **Acceptance criteria:**
  - [ ] Round-trip tests pass for all five documents
  - [ ] Schemas validate the fixture documents
  - [ ] Exported schema files are current with the models
- **Tests:** test_schemas_models_roundtrip_all_five_documents, test_schemas_export_json_schemas_are_current, test_schemas_fixture_documents_validate, test_schemas_panel_spec_invalid_shot_rejected, test_schemas_beat_requires_arc_stage, test_schemas_continuity_report_issue_kinds_enum
- **Depends on:** S0-T06

### S1-T03: Implement story bible
- **Labels:** type: feature, area: story, priority: p0, size: L, sprint: 1
- **Estimate:** L
- **Spec refs:** PRD FR-009, US-002, US-003, ARCHITECTURE ADR-007, ADR-010, Data formats (Story Bible)
- **Description:** Generate the bible from the seed narrative (and later reference descriptions), allow editing, and version it on every change. Arc templates with stages: three-act, hero's-journey-lite, problem-try-try-succeed (kids default), gag-a-day (no arc, standalone strips), and mystery. The prompt template `story/prompts/bible.md` is versioned.
- **Acceptance criteria:**
  - [ ] Bible has title (working), logline, premise, audience (all-ages default, kids-5-8, kids-9-12, teen, adult), tone, setting, cast list, themes, arc template, and target length
  - [ ] Target length is between 1 and 40 strips; out of range is rejected
  - [ ] All five arc templates load with their stages
  - [ ] Editing creates a new bible version and an undoable event
- **Tests:** test_story_bible_target_strips_out_of_range_rejected, test_story_bible_generate_from_narrative_fake_provider_validates, test_story_bible_audience_values_enum_with_all_ages_default, test_story_bible_edit_creates_new_version, test_story_bible_edit_is_undoable_event, test_story_arc_templates_five_templates_load_with_stages, test_story_bible_default_arc_for_kids_is_problem_try_try_succeed, test_story_prompts_bible_template_version_recorded, it_story_bible_ollama_generates_valid_bible
- **Depends on:** S1-T01, S1-T02

### S1-T04: Track arc stage and open threads
- **Labels:** type: feature, area: story, priority: p0, size: M, sprint: 1
- **Estimate:** M
- **Spec refs:** PRD FR-010, ARCHITECTURE ADR-007, Pipelines (beat to strip)
- **Description:** After a strip is approved, update the arc stage and open threads via an LLM call that returns a structured diff (threads opened, threads closed, stage). Progress is computed from the stage index and the target strips.
- **Acceptance criteria:**
  - [ ] Every strip is tagged with an arc stage
  - [ ] Arc stages exist per template and the open threads list updates after each approved strip
  - [ ] Arc progress (0 to 100 percent) is computed and exposed to the UI
- **Tests:** test_story_arc_progress_updates_after_approval, test_story_arc_progress_computed_from_stage_index_and_target, test_story_arc_threads_opened_and_closed_from_diff, test_story_arc_diff_unknown_thread_close_ignored, test_story_arc_gag_a_day_has_no_stage_progress, test_story_arc_each_strip_tagged_with_stage, test_story_arc_progress_clamped_0_to_100
- **Depends on:** S1-T03

### S1-T05: Generate plot suggestions
- **Labels:** type: feature, area: story, priority: p0, size: L, sprint: 1
- **Estimate:** L
- **Spec refs:** PRD FR-011, US-004, US-009, NFR-003, ARCHITECTURE ADR-007, Data formats (Plot Suggestion)
- **Description:** Generate continue, twist, and steer options, plus end-here at the final stage or target length. A distinctness check uses sentence embeddings (Ollama embeddings endpoint with a `nomic-embed-text` class model, or the provider equivalent) and regenerates once if any pair exceeds 0.85 cosine similarity. Context passed to the LLM: bible, last three strip summaries, open threads, arc stage, and audience rules. Thumbnails are deferred to S3-T09.
- **Acceptance criteria:**
  - [ ] Exactly three options with intents continue, twist, and steer
  - [ ] Each option has a one-line beat, a two-sentence description, the arc stage it moves to, characters that appear, and a thumbnail sketch prompt
  - [ ] Pairwise similarity under 0.85, else regenerate once
  - [ ] A fourth option, end here, appears when the arc is in its final stage or the target length is reached
  - [ ] Text-only suggestions appear within 10 s on a local 14B model (NFR-003)
- **Tests:** test_story_suggest_returns_three_distinct_intents, test_story_suggest_similar_options_regenerated_once, test_story_suggest_final_stage_includes_end_here, test_story_suggest_target_length_reached_includes_end_here, test_story_suggest_option_has_required_fields, test_story_suggest_context_includes_bible_last_three_summaries_threads, test_story_suggest_still_similar_after_regen_returns_with_warning, test_story_suggest_embeddings_cosine_threshold_085, it_story_suggest_ollama_distinct_options, it_story_suggest_local_model_within_10s
- **Depends on:** S1-T04

### S1-T06: Normalize custom beats
- **Labels:** type: feature, area: story, priority: p1, size: S, sprint: 1
- **Estimate:** S
- **Spec refs:** PRD FR-012, US-005, ARCHITECTURE ADR-007
- **Description:** Normalize a free-text beat or an edited suggestion into the beat structure and return it to the user for confirmation before the strip is written.
- **Acceptance criteria:**
  - [ ] Free-text beats are normalized into the same structure as suggestions
  - [ ] The user sees the normalized beat and can accept it
  - [ ] Edits to a suggestion keep untouched fields
- **Tests:** test_story_beat_normalize_free_text_to_beat_structure, test_story_beat_normalized_returned_for_confirmation, test_story_beat_edit_suggestion_keeps_other_fields, test_story_beat_empty_text_rejected
- **Depends on:** S1-T05

### S1-T07: Write strips from beats
- **Labels:** type: feature, area: story, priority: p0, size: L, sprint: 1
- **Estimate:** L
- **Spec refs:** PRD FR-013, FR-014, US-006, ARCHITECTURE ADR-007, Data formats (Panel Spec)
- **Description:** Turn a beat into Panel Specs with audience reading rules (word limits per balloon, balloons per panel, words per strip), cast integrity, continuity notes from previous strips, a shot variety rule (no more than two consecutive panels with the same shot), and a `balloon_space` hint per panel.
- **Acceptance criteria:**
  - [ ] 1 to 6 panels per strip, default 4
  - [ ] kids-5-8: at most 10 words per balloon and 2 balloons per panel; a total-words-per-strip limit applies per audience
  - [ ] Every speaking character exists in the cast
  - [ ] Output validates against the Panel Spec JSON Schema with one corrective retry on failure
  - [ ] Shot variety is enforced by the validator
- **Tests:** test_story_writer_unknown_speaker_rejected, test_story_writer_kids_word_limit_enforced, test_story_writer_kids_max_two_balloons_per_panel, test_story_writer_total_words_per_strip_limit, test_story_writer_shot_variety_no_three_consecutive_same_shot, test_story_writer_panel_count_default_four_range_one_to_six, test_story_writer_invalid_output_one_corrective_retry, test_story_writer_balloon_space_hint_present_per_panel, test_story_writer_continuity_notes_from_previous_strips, it_story_writer_ollama_valid_panel_specs
- **Depends on:** S1-T05

### S1-T08: Add text moderation and audience guard
- **Labels:** type: security, area: safety, priority: p0, size: M, sprint: 1
- **Estimate:** M
- **Spec refs:** PRD FR-028, FR-006, NFR-012, ARCHITECTURE ADR-013, Security and safety model
- **Description:** Audience rule blocks go into every system prompt. A moderation pass (an LLM classifier with a strict JSON verdict) runs on the bible, suggestions, beats, and scripts. A denylist check covers copyrighted names (starter list in `comic_smith/cast/denylist.yaml`).
- **Acceptance criteria:**
  - [ ] Audience rules are present in every system prompt
  - [ ] A moderation pass runs on every generated beat, script, and bible
  - [ ] Blocked content returns `ComicSmithError(code="safety_blocked")` with a plain-words explanation
  - [ ] Unparseable verdicts fail closed
- **Tests:** test_safety_moderation_blocked_bible_raises_safety_blocked, test_safety_moderation_verdict_strict_json_schema, test_safety_moderation_runs_on_suggestions_beats_scripts, test_safety_audience_rules_in_every_system_prompt, test_safety_denylist_copyrighted_name_blocked_in_beat, test_safety_blocked_error_explains_in_plain_words, test_safety_denylist_loaded_from_yaml_data_file, test_safety_moderation_unparseable_verdict_fails_closed, test_safety_audience_kids_blocks_violent_beat
- **Depends on:** S1-T01

### S1-T09: Implement branching
- **Labels:** type: feature, area: story, priority: p1, size: M, sprint: 1
- **Estimate:** M
- **Spec refs:** PRD FR-021, US-020, ARCHITECTURE ADR-010, Data model
- **Description:** Create, switch, rename, and delete branches. Strip listing per branch follows the parent chain up to the fork point. Branches share earlier strips.
- **Acceptance criteria:**
  - [ ] A branch can be created from any approved strip
  - [ ] Branches share earlier strips; listing follows the parent chain to the fork point
  - [ ] Switch, rename, and delete work; finalize applies to one branch
- **Tests:** test_story_branch_create_from_approved_strip, test_story_branch_strip_listing_follows_parent_chain_to_fork, test_story_branch_switch_changes_active_branch, test_story_branch_rename, test_story_branch_delete_keeps_shared_strips, test_story_branch_delete_active_branch_rejected, test_story_branch_create_from_unapproved_strip_rejected
- **Depends on:** S1-T07

### S1-T10: Implement story finalize
- **Labels:** type: feature, area: story, priority: p0, size: M, sprint: 1
- **Estimate:** M
- **Spec refs:** PRD FR-022, US-010, ARCHITECTURE ADR-007, Pipelines
- **Description:** Continuity review producing a structured report (unresolved threads, characters who vanish, inconsistent props, tone breaks), three titles and a one-line blurb, then lock. Reopen creates a new story version.
- **Acceptance criteria:**
  - [ ] The user can jump to a flagged strip or finalize anyway
  - [ ] Finalized stories are read-only unless reopened
  - [ ] Reopen creates a new version
- **Tests:** test_story_finalize_continuity_report_structure, test_story_finalize_returns_three_titles_and_blurb, test_story_finalize_locks_story_read_only, test_story_finalize_anyway_with_open_issues_allowed, test_story_finalize_reopen_creates_new_version, test_story_finalize_edit_locked_story_rejected, test_story_finalize_report_jump_to_strip_ids
- **Depends on:** S1-T09

### S1-T11: Add story CLI
- **Labels:** type: feature, area: cli, priority: p0, size: M, sprint: 1
- **Estimate:** M
- **Spec refs:** PRD FR-030, FR-026, US-016, ARCHITECTURE Contracts (CLI)
- **Description:** `new`, `bible`, `suggest`, `strip --pick/--beat` (script only for now), `branch`, `finalize`, and `auto` (script-only auto mode using the policy), all with `--json`.
- **Acceptance criteria:**
  - [ ] Smoke: `new --narrative` + `auto --until-target` + `finalize` with FakeProvider produces a finalized story of N scripted strips
  - [ ] All commands support `--json`
  - [ ] CLI and Studio operate on the same project files
- **Tests:** smoke_cli_new_auto_finalize_scripted_story, test_cli_new_narrative_creates_project_json_output, test_cli_bible_show_and_edit, test_cli_suggest_json_returns_three_options, test_cli_strip_pick_writes_script_only, test_cli_strip_beat_free_text, test_cli_branch_create_switch_list, test_cli_auto_until_target_policy_balanced, test_cli_all_story_commands_support_json_flag
- **Depends on:** S1-T10

### Sprint 1 Gate
Hard stop. Sprint 2 does not start until every item is checked.
- [ ] Fixture narrative produces bible, 8 strips of valid Panel Specs, and a finalized story with FakeProvider
- [ ] Real Ollama run produces distinct suggestions and valid scripts
- [ ] Moderation and denylist verified by tests
- [ ] Coverage for `story` at or above target
- [ ] Retrospective written, `sprint-1-complete` tagged

---

## Sprint 2: Cast, Style, and Backends

**Milestone:** Sprint 2: Cast, Style, Backends
**Duration:** 1 week
**Goal:** A reference photo becomes an approved, original character sheet in a chosen style, generated through any image backend.

### S2-T01: Implement asset ingest
- **Labels:** type: feature, area: cast, priority: p0, size: M, sprint: 2
- **Estimate:** M
- **Spec refs:** PRD FR-002, US-003, NFR-006, ARCHITECTURE Pipelines (seed to cast), Data model
- **Description:** Pillow plus pillow-heif ingest: type sniffing (not extension), size limits, EXIF strip, orientation fix, HEIC to PNG, downscale to 4096 px on the long edge, and SHA-256 storage.
- **Acceptance criteria:**
  - [ ] Accepts narrative text of 1 to 5,000 characters and zero to four reference images (PNG, JPG, WebP, HEIC; max 20 MB each)
  - [ ] Images are re-encoded with EXIF stripped (location removed) and stored by SHA-256
  - [ ] HEIC is converted to PNG; images over 4096 px on the long edge are downscaled
  - [ ] Corrupt and oversized fixtures are rejected with clear errors
- **Tests:** test_assets_ingest_exif_gps_stripped, test_assets_ingest_heic_converted_to_png, test_assets_ingest_type_sniffed_not_extension, test_assets_ingest_corrupt_jpg_rejected_clear_error, test_assets_ingest_huge_30mb_png_rejected_over_20mb_limit, test_assets_ingest_downscales_over_4096_long_edge, test_assets_ingest_orientation_fixed_from_exif, test_assets_ingest_stored_by_sha256, test_assets_ingest_fifth_reference_rejected, test_assets_ingest_narrative_over_5000_chars_rejected
- **Depends on:** S0-T06

### S2-T02: Build vision provider interface and providers
- **Labels:** type: feature, area: backend-vision, priority: p0, size: L, sprint: 2
- **Estimate:** L
- **Spec refs:** PRD FR-003, FR-007, FR-017, ARCHITECTURE ADR-012, Contracts (VisionProvider)
- **Description:** `describe` (structured JSON) and `locate` (bounding boxes for named targets, normalized 0 to 1 coordinates). Providers: `OllamaVisionProvider` (Qwen2.5-VL class model), `AnthropicVisionProvider`, `OpenAICompatVisionProvider`, and `FakeVisionProvider`.
- **Acceptance criteria:**
  - [ ] respx tests exist for each provider
  - [ ] `locate` returns valid boxes for the fixtures
  - [ ] Doctor checks reachability of the vision provider
- **Tests:** test_vision_describe_returns_structured_json_with_palette_hex, test_vision_locate_returns_normalized_boxes, test_vision_locate_box_outside_unit_range_rejected, test_vision_ollama_provider_request_shape, test_vision_anthropic_provider_image_block, test_vision_openai_compat_provider_request_shape, test_vision_fake_provider_replays_recorded_responses, test_vision_doctor_reachability_check_hint, it_vision_ollama_locate_duck_fixture_valid_box
- **Depends on:** S1-T01

### S2-T03: Add reference understanding and people guard
- **Labels:** type: feature, area: safety, priority: p0, size: M, sprint: 2
- **Estimate:** M
- **Spec refs:** PRD FR-003, FR-007, NFR-012, ARCHITECTURE ADR-013, Security and safety model
- **Description:** Implement FR-003 describe (structured description the user can edit), FR-007 person detection with an attestation requirement, and public-figure decline in the prompt layer.
- **Acceptance criteria:**
  - [ ] Description is stored as structured JSON (subject, palette hex list, features, accessories) and every field is editable
  - [ ] Person fixture blocks sheet generation until the attestation is recorded
  - [ ] Attestation is stored with the character
  - [ ] Photoreal styles are disabled for person-derived characters
  - [ ] Requests to depict public figures are declined by the story and prompt layers
- **Tests:** test_cast_reference_person_detected_requires_attestation, test_cast_reference_describe_stored_as_editable_json, test_cast_reference_attestation_stored_with_character, test_cast_reference_photoreal_style_disabled_for_person_derived, test_cast_reference_public_figure_request_declined, test_cast_reference_sheet_generation_blocked_until_attested, test_cast_reference_no_person_duck_fixture_no_attestation_needed
- **Depends on:** S2-T02

### S2-T04: Define ImageBackend interface, registry, and mock backend
- **Labels:** type: feature, area: backend-image, priority: p0, size: M, sprint: 2
- **Estimate:** M
- **Spec refs:** PRD NFR-001, ARCHITECTURE ADR-005, Contracts (ImageBackend)
- **Description:** Define Capabilities, ImageRequest, and GeneratedImage, plus a registry. `MockBackend` draws deterministic flat-color scenes with labeled shapes per character (Pillow), respects size and seed, and simulates progress and occasional failures (configurable) for testing.
- **Acceptance criteria:**
  - [ ] Mock outputs are byte-identical across platforms for the same request
  - [ ] Registry exposes capability flags per backend
  - [ ] Mock simulates progress and configurable failures
- **Tests:** test_backends_mock_output_byte_identical_for_same_request, test_backends_mock_respects_size_and_seed, test_backends_mock_draws_labeled_shape_per_character, test_backends_mock_simulated_failures_configurable, test_backends_mock_emits_progress_events, test_backends_registry_lists_capabilities, test_backends_registry_unknown_backend_raises, test_backends_capabilities_max_reference_images_exposed
- **Depends on:** S0-T06

### S2-T05: Build ComfyUI backend with bundled workflows
- **Labels:** type: feature, area: backend-image, priority: p0, size: XL, sprint: 2
- **Estimate:** XL
- **Spec refs:** PRD FR-004, NFR-001, NFR-011, ARCHITECTURE ADR-005, ADR-006, Contracts (ImageBackend)
- **Description:** Client for a running ComfyUI server: upload reference images, queue a workflow (prompt JSON), stream progress over its websocket, fetch outputs from history, and interrupt on cancel. Workflow templates live in `backends/image/workflows/` with named input slots (prompt, negative, refs[], width, height, seed, steps, mask). Ship `qwen-image-edit` (default, Apache-2.0), `flux-kontext-dev` (opt-in, non-commercial license gate), and `sdxl-ipadapter` (fallback for smaller GPUs). The workflow manifest declares required model files with download URLs and SHA-256; `mr-comic-smith models pull <workflow>` downloads into ComfyUI's model folders. Verify current node names, model files, licenses, and VRAM requirements at implementation time and record them in ARCHITECTURE. This is an XL task and must be split before starting into three parts: (1) client: connection, queueing, websocket progress, history fetch, interrupt; (2) workflows: the three templates, slot filling, manifest with checksums, `models pull`, license gate; (3) references: reference upload and slot mapping for multi-reference panels.
- **Acceptance criteria:**
  - [ ] Stub-server integration tests run in CI
  - [ ] GPU integration test renders a panel with two reference images
  - [ ] License gate is enforced for `flux-kontext-dev`
  - [ ] `models pull` verifies SHA-256 and rejects a corrupt download
- **Tests:** it_comfyui_stub_server_queue_and_fetch_output, it_comfyui_stub_websocket_progress_events_streamed, it_comfyui_cancel_interrupts_running_prompt, it_comfyui_reference_upload_returns_server_filename, test_comfyui_workflow_slots_filled_prompt_negative_size_seed, test_comfyui_workflow_templates_all_three_validate, test_comfyui_workflow_manifest_declares_models_with_sha256, test_comfyui_flux_kontext_requires_license_acceptance, test_comfyui_models_pull_verifies_checksum, test_comfyui_models_pull_corrupt_download_rejected, it_comfyui_qwen_edit_workflow_returns_image, it_comfyui_gpu_two_reference_panel_renders
- **Depends on:** S2-T04

### S2-T06: Add Gemini image backend
- **Labels:** type: feature, area: backend-image, priority: p0, size: M, sprint: 2
- **Estimate:** M
- **Spec refs:** PRD FR-004, NFR-001, ARCHITECTURE ADR-005, Contracts (ImageBackend)
- **Description:** Google GenAI SDK with the current image-generation model and multiple reference images (verify model id and reference limits at implementation time). The key comes from the environment or keyring. The backend is flagged as cloud so the UI shows the cloud badge.
- **Acceptance criteria:**
  - [ ] respx contract tests pass
  - [ ] Nightly live test runs behind a secret
  - [ ] Missing key produces an actionable error
  - [ ] Backend reports the cloud badge
- **Tests:** test_gemini_contract_request_includes_reference_images, test_gemini_contract_response_decoded_to_generated_image, test_gemini_key_from_env_or_keyring, test_gemini_missing_key_raises_with_hint, test_gemini_capabilities_declare_reference_limit, test_gemini_backend_reports_cloud_badge, test_gemini_safety_block_response_maps_to_error, it_gemini_nightly_live_generates_panel
- **Depends on:** S2-T04

### S2-T07: Add OpenAI images backend
- **Labels:** type: feature, area: backend-image, priority: p1, size: M, sprint: 2
- **Estimate:** M
- **Spec refs:** PRD FR-004, NFR-001, ARCHITECTURE ADR-005, Contracts (ImageBackend)
- **Description:** OpenAI SDK images generate and edit with reference images and masks (verify the current model id at implementation time). Flagged as cloud.
- **Acceptance criteria:**
  - [ ] respx contract tests pass
  - [ ] Nightly live test runs behind a secret
  - [ ] Edit capability is declared and masks are honored
- **Tests:** test_openai_images_contract_generate_request_shape, test_openai_images_contract_edit_with_reference_and_mask, test_openai_images_key_missing_raises_with_hint, test_openai_images_capabilities_declare_edit_support, test_openai_images_content_policy_error_mapped, test_openai_images_reports_cloud_badge, it_openai_images_nightly_live_generates_panel
- **Depends on:** S2-T04

### S2-T08: Add style presets
- **Labels:** type: feature, area: style, priority: p0, size: M, sprint: 2
- **Estimate:** M
- **Spec refs:** PRD FR-008, US-018, ARCHITECTURE Data formats (Style), Appendix I principle 4
- **Description:** Six built-in presets (picture-book-watercolor, bold-cartoon, manga-ink, newspaper-strip, soft-3d-clay, pixel-art) as YAML with tokens, negative tokens, palette hints, line weight, and per-backend overrides. Custom preset creation from text plus up to two owned style reference images. A preview grid job renders the cast in the style.
- **Acceptance criteria:**
  - [ ] Presets validate against the style schema
  - [ ] Preview renders with the mock backend
  - [ ] Custom presets accept up to two style reference images
- **Tests:** test_style_presets_six_builtin_validate, test_style_preset_has_tokens_negative_palette_line_weight, test_style_preset_backend_override_applied, test_style_custom_preset_from_text_and_two_refs, test_style_custom_preset_three_refs_rejected, test_style_preset_photoreal_flag_declared, it_style_preview_grid_job_renders_with_mock_backend
- **Depends on:** S2-T04

### S2-T09: Generate and approve character sheets
- **Labels:** type: feature, area: cast, priority: p0, size: L, sprint: 2
- **Estimate:** L
- **Spec refs:** PRD FR-004, FR-005, US-001, ARCHITECTURE ADR-004, Pipelines (seed to cast)
- **Description:** Generate views and expressions using the reference image (when the backend accepts references) plus description and style, compose a sheet image, support per-view regenerate and approve, and derive the visual DNA paragraph from the description plus the approved front view via the vision model. Text-only characters follow the same workflow (FR-005).
- **Acceptance criteria:**
  - [ ] Front, side, and three-quarter views plus expressions neutral, happy, sad, surprised, angry, and scared are generated
  - [ ] Sheet is rendered as separate images plus a composed sheet
  - [ ] User approves or regenerates per view; the approved sheet becomes the canonical reference
  - [ ] Character has a stable id and a visual DNA paragraph used in every panel prompt
  - [ ] Text-only characters use the same sheet workflow
- **Tests:** test_cast_sheet_generates_three_views_and_six_expressions, test_cast_sheet_uses_reference_when_backend_supports_references, test_cast_sheet_text_only_character_same_workflow, test_cast_sheet_regenerate_single_view_keeps_others, test_cast_sheet_approve_makes_canonical_reference, test_cast_sheet_visual_dna_paragraph_derived_from_front_view, test_cast_sheet_character_has_stable_id, test_cast_sheet_composed_sheet_image_includes_all_views, test_cast_sheet_unapproved_character_cannot_be_used_in_panels, it_cast_sheet_duck_fixture_mock_backend_end_to_end
- **Depends on:** S2-T03, S2-T05, S2-T08

### S2-T10: Add originality guard
- **Labels:** type: security, area: safety, priority: p0, size: M, sprint: 2
- **Estimate:** M
- **Spec refs:** PRD FR-006, NFR-012, ARCHITECTURE ADR-013, Security and safety model
- **Description:** A denylist applies to user text and compiled prompts. After a sheet is approved, a resemblance question goes to the vision model. A match blocks approval with an explanation. The denylist is data, editable, and versioned.
- **Acceptance criteria:**
  - [ ] Denylist check runs on all user text and compiled prompts (configurable list with a shipped starter set)
  - [ ] Vision similarity question asked on each approved sheet
  - [ ] On a match, the user is told which rule triggered and asked to change the design; there is no override flag in v1
  - [ ] Denylist is data, editable, and versioned
- **Tests:** test_cast_originality_denylisted_name_blocked, test_cast_originality_resemblance_flag_blocks_approval, test_cast_originality_block_message_names_rule, test_cast_originality_no_override_flag_exists, test_cast_originality_denylist_check_on_compiled_prompt, test_cast_originality_living_artist_style_blocked, test_cast_originality_denylist_versioned_data_file, test_cast_originality_clean_duck_passes
- **Depends on:** S2-T09

### S2-T11: Add cast and library CLI plus doctor checks
- **Labels:** type: feature, area: cli, priority: p1, size: M, sprint: 2
- **Estimate:** M
- **Spec refs:** PRD FR-027, FR-030, FR-031, US-015, US-022, ARCHITECTURE Contracts (CLI)
- **Description:** `cast add|sheet|approve`, `library add|list|import`, `models pull`. Doctor adds checks for ComfyUI reachability, installed workflow models, GPU and VRAM (nvidia-smi or torch if present), and cloud keys present.
- **Acceptance criteria:**
  - [ ] CLI flows are covered by smoke with the mock backend
  - [ ] Imported characters keep sheets and visual DNA; the version is recorded (FR-027)
  - [ ] Each doctor failure has a fix hint
- **Tests:** smoke_cli_cast_add_sheet_approve_mock_backend, test_cli_library_add_list_import_roundtrip, test_library_import_keeps_sheets_and_visual_dna, test_library_import_records_version, test_cli_models_pull_invokes_workflow_downloads, test_doctor_comfyui_unreachable_hint, test_doctor_reports_installed_workflow_models, test_doctor_gpu_vram_detected_via_nvidia_smi, test_doctor_cloud_keys_presence_reported
- **Depends on:** S2-T09

### Sprint 2 Gate
Hard stop. Sprint 3 does not start until every item is checked.
- [ ] Duck photo fixture becomes an approved character sheet (mock in CI, ComfyUI on GPU runner, Gemini on nightly)
- [ ] People and originality guards verified
- [ ] Six style presets preview correctly
- [ ] Retrospective written, `sprint-2-complete` tagged

---

## Sprint 3: Panels, Lettering, and Strips

**Milestone:** Sprint 3: Panels, Lettering, Strips
**Duration:** 2 weeks
**Goal:** The complete co-plotting loop works in the Studio: pick a plot, edit the script, render consistent panels, letter them, approve, repeat. This sprint IS the product.

### S3-T01: Build prompt compiler
- **Labels:** type: feature, area: panels, priority: p0, size: L, sprint: 3
- **Estimate:** L
- **Spec refs:** PRD FR-015, ARCHITECTURE ADR-003, ADR-004, Pipelines (beat to strip)
- **Description:** Compile Panel Spec, style, and characters into an ImageRequest: ordered prompt sections (style, shot and angle vocabulary mapped per backend, setting, each character's visual DNA with position, pose, expression, facing, action, mood, and continuity), a negative prompt with the no-text constraint, reference selection (pick the sheet views closest to the required facing and expression, respect backend `max_reference_images`, prioritize characters by screen importance), aspect ratio from the layout slot, and a headroom hint from `balloon_space`.
- **Acceptance criteria:**
  - [ ] Compiler is deterministic and unit-tested
  - [ ] Compiled prompt includes the 'no text, no letters, no speech bubbles' constraint
  - [ ] Empty space for balloons is reserved via composition hints when a panel has dialogue
  - [ ] Snapshot tests exist per backend; the reference limit is never exceeded
  - [ ] Compiled prompt is viewable in the UI
- **Tests:** test_panels_compiler_includes_no_text_constraint, test_panels_compiler_adds_headroom_when_dialogue, test_panels_compiler_deterministic_same_spec_same_prompt, test_panels_compiler_snapshot_comfyui, test_panels_compiler_snapshot_gemini, test_panels_compiler_snapshot_openai, test_panels_compiler_reference_count_never_exceeds_backend_limit, test_panels_compiler_picks_sheet_views_closest_to_facing_and_expression, test_panels_compiler_prioritizes_characters_by_screen_importance, test_panels_compiler_aspect_ratio_from_layout_slot, test_panels_compiler_includes_visual_dna_per_character, test_panels_compiler_denylist_checked_on_compiled_prompt
- **Depends on:** Sprint 2

### S3-T02: Build job queue and workers
- **Labels:** type: feature, area: jobs, priority: p0, size: L, sprint: 3
- **Estimate:** L
- **Spec refs:** PRD FR-016, NFR-006, ARCHITECTURE ADR-011, Job system
- **Description:** SQLite job queue with a GPU worker and text workers, priorities, cancellation, resume after restart, and progress events over WebSocket.
- **Acceptance criteria:**
  - [ ] Kill-and-resume integration test passes
  - [ ] Priority ordering test passes
  - [ ] Cancel works; failures retried twice
- **Tests:** it_jobs_kill_worker_mid_render_resumes, it_jobs_priority_ordering_thumbnail_below_render, it_jobs_cancel_running_job, it_jobs_progress_events_over_websocket, it_jobs_resume_after_restart, test_jobs_retry_twice_then_fail, test_jobs_single_gpu_worker_serializes_gpu_jobs, test_jobs_text_workers_run_concurrently, test_jobs_enqueue_idempotent_same_key
- **Depends on:** S0-T06

### S3-T03: Render panels and manage takes
- **Labels:** type: feature, area: panels, priority: p0, size: M, sprint: 3
- **Estimate:** M
- **Spec refs:** PRD FR-016, FR-014, US-007, ARCHITECTURE Pipelines (beat to strip), Caching model
- **Description:** A render job per panel; take records with seed, backend, model, and compiled prompt; select a take; retake with a new seed. Edits that change visuals mark the panel stale; text-only edits do not.
- **Acceptance criteria:**
  - [ ] Per-panel seed is recorded and takes are stored
  - [ ] Renders run in the job queue with progress events; cancel works; failures retried twice
  - [ ] Visual edits mark a panel stale; text-only edits do not trigger re-rendering
- **Tests:** test_panels_render_records_seed_backend_model_prompt_in_take, test_panels_render_select_take_updates_active, test_panels_render_retake_uses_new_seed, test_panels_render_failure_retried_twice, test_panels_render_cancel_leaves_no_partial_take, test_panels_render_cache_hit_same_compiled_prompt_and_seed, test_panels_script_text_only_edit_does_not_mark_stale, test_panels_script_visual_edit_marks_panel_stale, it_panels_render_four_panel_strip_mock_backend
- **Depends on:** S3-T01, S3-T02

### S3-T04: Add consistency QA with auto retakes
- **Labels:** type: feature, area: qa, priority: p0, size: L, sprint: 3
- **Estimate:** L
- **Spec refs:** PRD FR-017, NFR-004, NFR-005, ARCHITECTURE ADR-004, Caching model
- **Description:** The vision model scores each character against its sheet checklist (1 to 5 with reasons) using the panel and the sheet front view. OCR text detection (RapidOCR, ONNX, CPU) uses a confidence threshold. An auto retake loop selects the best take by minimum character score, then OCR-clean.
- **Acceptance criteria:**
  - [ ] Panels with any character under 4, or with detected text, are flagged and auto-retaken up to N times (default 2, new seed)
  - [ ] The best take is selected and scores and reasons are shown to the user
  - [ ] QA results are cached
  - [ ] Thresholds are configurable per project
- **Tests:** test_panels_qa_detected_text_triggers_retake, test_panels_qa_low_consistency_keeps_best_take, test_panels_qa_score_below_four_flags_panel, test_panels_qa_auto_retake_stops_after_n_attempts, test_panels_qa_best_take_ordering_min_score_then_ocr_clean, test_panels_qa_results_cached_per_take, test_panels_qa_threshold_configurable_per_project, test_panels_qa_reasons_surface_to_user, it_panels_qa_rapidocr_detects_text_in_fixture, it_panels_qa_vision_scores_duck_against_sheet
- **Depends on:** S3-T03

### S3-T05: Add panel editing
- **Labels:** type: feature, area: panels, priority: p1, size: M, sprint: 3
- **Estimate:** M
- **Spec refs:** PRD FR-018, US-007, ARCHITECTURE ADR-005, Contracts (ImageBackend)
- **Description:** Region edit with a mask and an instruction (backends with `supports_edit`), non-destructive crop and reframe, and a shot change that triggers a re-render.
- **Acceptance criteria:**
  - [ ] Inpaint is limited to the selected mask
  - [ ] Crop is non-destructive
  - [ ] Edit is disabled with a tooltip when the backend lacks support
- **Tests:** test_panels_edit_inpaint_limited_to_mask, test_panels_edit_disabled_when_backend_lacks_edit_support, test_panels_edit_crop_is_non_destructive, test_panels_edit_shot_change_triggers_rerender, test_panels_edit_reframe_preserves_original_asset, test_panels_edit_undo_restores_previous_take, it_panels_edit_region_mock_backend_changes_only_mask
- **Depends on:** S3-T03

### S3-T06: Build lettering placement engine
- **Labels:** type: feature, area: letter, priority: p0, size: XL, sprint: 3
- **Estimate:** XL
- **Spec refs:** PRD FR-019, NFR-005, ARCHITECTURE ADR-003, DESIGN Lettering visual spec
- **Description:** Inputs: panel size, character boxes (vision `locate`, head sub-box when available), dialogue list in order, caption, sfx, and style lettering rules. Algorithm: measure text with the real font metrics (fontTools) to size balloons; candidate positions on a grid inside the panel weighted by the `balloon_space` hint; a cost function penalizing overlap with character boxes (heavy), overlap with other balloons (infinite), distance from the speaker head (medium), violation of reading order (heavy), and proximity to the panel edge (light); greedy placement in reading order with local search refinement; tails as quadratic curves to the speaker head box edge; font downsizing to a minimum before splitting lines; fallback to caption boxes at top when no valid position exists. This is an XL task and must be split before starting into three parts: (1) geometry: font metrics, text measurement, balloon sizing, panel bounds; (2) placement: candidate grid, cost function, greedy plus local search, reading order, fallback; (3) tails: quadratic tail curves to the speaker head box edge.
- **Acceptance criteria:**
  - [ ] Placement avoids character bounding boxes, follows reading order (top-left to bottom-right), and points tails at the speaker's head box
  - [ ] Font auto-sizes within min and max sizes and never overflows the panel
  - [ ] Property tests: no balloon overlaps another, all balloons are inside the panel, reading order holds
- **Tests:** test_letter_layout_balloons_avoid_character_boxes, test_letter_layout_reading_order_left_to_right, test_letter_layout_text_never_overflows_panel, test_letter_layout_property_no_balloon_overlaps_another, test_letter_layout_property_all_balloons_inside_panel, test_letter_layout_property_reading_order_holds, test_letter_layout_text_measured_with_real_font_metrics, test_letter_layout_font_downsizes_to_minimum_before_splitting, test_letter_layout_tail_points_at_speaker_head_box_edge, test_letter_layout_no_valid_position_falls_back_to_top_caption, test_letter_layout_balloon_space_hint_biases_candidates, test_letter_layout_deterministic_same_input_same_output
- **Depends on:** S2-T02

### S3-T07: Render lettering SVG and bundle fonts
- **Labels:** type: feature, area: letter, priority: p0, size: L, sprint: 3
- **Estimate:** L
- **Spec refs:** PRD FR-019, NFR-005, NFR-011, ARCHITECTURE ADR-003, ADR-008, DESIGN Lettering visual spec
- **Description:** SVG generation for speech, thought, shout, whisper, caption, and SFX per the DESIGN lettering spec. Bundle open-licensed fonts (Comic Neue for dialogue, Bangers for SFX and shouts, and a picture-book friendly rounded face such as Andika or Atkinson Hyperlegible for kids styles; verify licenses, all OFL expected). Fonts are embedded as base64 `@font-face` in the SVG for exact export.
- **Acceptance criteria:**
  - [ ] Visual goldens exist for every balloon type
  - [ ] Text remains real text in SVG
  - [ ] Fonts are open-licensed and embedded
  - [ ] Minimum font size is 9 pt at print size and 14 px on web
- **Tests:** vis_letter_balloon_speech, vis_letter_balloon_thought, vis_letter_balloon_shout, vis_letter_balloon_whisper, vis_letter_caption, vis_letter_sfx, test_letter_svg_text_remains_real_text_elements, test_letter_svg_fonts_embedded_as_base64_font_face, test_letter_svg_uppercase_per_style_setting, test_letter_svg_minimum_font_size_print_and_web, test_letter_fonts_licenses_all_ofl_recorded
- **Depends on:** S3-T06

### S3-T08: Compose strips and approve
- **Labels:** type: feature, area: layout, priority: p0, size: M, sprint: 3
- **Estimate:** M
- **Spec refs:** PRD FR-020, ARCHITECTURE ADR-008, Pipelines (beat to strip)
- **Description:** Strip SVG with panels in a row, gutters, borders, and rounded or square corners per style. The approve flow (FR-020) triggers the arc update and the next suggestions.
- **Acceptance criteria:**
  - [ ] Approval requires all panels rendered and lettered
  - [ ] Approved strips are immutable until unapprove
  - [ ] Approving triggers the bible thread update and next plot suggestions
  - [ ] Strip goldens pass
- **Tests:** vis_strip_four_panel_bold_cartoon, vis_strip_rounded_corners_picture_book, test_layout_strip_svg_gutters_and_borders_per_style, test_layout_strip_approve_requires_all_panels_rendered_and_lettered, test_layout_strip_approved_immutable_until_unapprove, test_layout_strip_approve_triggers_arc_update_and_next_suggestions, test_layout_strip_unapprove_reopens_editing, test_layout_strip_approve_emits_undoable_event
- **Depends on:** S3-T07

### S3-T09: Render suggestion thumbnails
- **Labels:** type: feature, area: story, priority: p2, size: M, sprint: 3
- **Estimate:** M
- **Spec refs:** PRD FR-011, NFR-003, ARCHITECTURE ADR-011, Job system
- **Description:** A low-cost thumbnail per suggestion (fast steps, small size, low priority job). Skipped when the backend estimate exceeds a configurable budget; a placeholder illustration is shown otherwise.
- **Acceptance criteria:**
  - [ ] Suggestions never wait on thumbnails
  - [ ] Thumbnails fill in as they arrive
  - [ ] Thumbnails are skipped when the backend estimate exceeds the budget
- **Tests:** test_story_thumbnail_job_low_priority_small_size, test_story_thumbnail_skipped_when_estimate_exceeds_budget, test_story_thumbnail_placeholder_when_skipped, test_story_suggest_does_not_wait_on_thumbnails, it_story_thumbnail_fills_in_as_arrives
- **Depends on:** S3-T03

### S3-T10: Build Studio Cast and Story views
- **Labels:** type: feature, area: studio, priority: p0, size: L, sprint: 3
- **Estimate:** L
- **Spec refs:** PRD FR-029, FR-007, US-001, US-002, US-003, US-020, DESIGN Wireframes, Component inventory
- **Description:** New project wizard (narrative, photos, style, audience, length). Cast view with sheet approval, per-view regenerate, and originality and attestation states. Story view with the bible editor, arc progress, open threads, and branches.
- **Acceptance criteria:**
  - [ ] e2e: create the duck project and approve the character with mocks
  - [ ] Person photo requires attestation before the sheet is generated
  - [ ] Branch switch shows alternate strips
- **Tests:** e2e_US001_create_duck_project_and_approve_character_with_mocks, e2e_US001_person_photo_requires_attestation_before_sheet, e2e_US003_start_from_narrative_only, e2e_US003_start_from_photo_only, e2e_US002_edit_story_bible_creates_version, e2e_US020_branch_switch_shows_alternate_strips, test_studio_wizard_store_validates_length_and_audience, test_studio_cast_store_regenerate_single_view_updates_state
- **Depends on:** S3-T08

### S3-T11: Build Studio Strips view
- **Labels:** type: feature, area: studio, priority: p0, size: XL, sprint: 3
- **Estimate:** XL
- **Spec refs:** PRD FR-029, FR-014, FR-018, FR-033, US-004, US-005, US-006, US-007, US-009, US-021, DESIGN Wireframes, Motion and feedback
- **Description:** Implement the Strips wireframe: plot choice cards with thumbnails and 'write my own'; the strip canvas with per-panel progress placeholders; the panel inspector (shot, angle, action, characters, dialogue editor); a takes carousel; QA badges; retake and edit region; a timeline with approved strips and branch selector; undo and redo; and keyboard shortcuts (J/K panel navigation, R retake, A approve, Cmd/Ctrl+Z undo). This is the core screen. This is an XL task and must be split before starting into four parts: (1) canvas: strip canvas and progress placeholders; (2) inspector: panel fields, dialogue editor, takes carousel, QA badges; (3) choices: plot choice cards, write my own, end-here; (4) timeline: approved strips, branch selector, undo and redo, shortcuts.
- **Acceptance criteria:**
  - [ ] e2e: pick a suggestion, render, retake one panel, approve, and next suggestions appear
  - [ ] Keyboard shortcuts J/K, R, A, and Cmd/Ctrl+Z work
  - [ ] Rendering shows per-panel progress with a sketch placeholder, never a blank spinner
- **Tests:** e2e_US006_pick_suggestion_render_retake_approve_next_suggestions, e2e_US005_write_own_beat_via_write_my_own, e2e_US006_edit_script_before_rendering, e2e_US007_regenerate_single_panel_leaves_others, e2e_US007_keyboard_shortcuts_jk_r_a, e2e_US009_end_here_option_offered_at_final_stage, e2e_US021_undo_redo_with_keyboard_shortcuts, test_studio_strips_store_panel_progress_events_update, test_studio_strips_inspector_dialogue_editor_validates_audience_limits
- **Depends on:** S3-T10

### S3-T12: Build Studio lettering editor
- **Labels:** type: feature, area: studio, priority: p0, size: L, sprint: 3
- **Estimate:** L
- **Spec refs:** PRD FR-019, FR-033, US-008, US-021, DESIGN Lettering visual spec
- **Description:** SVG overlay editing: drag a balloon, drag a tail tip, resize, edit text inline, change balloon type, add a caption or SFX, and re-run auto placement. Changes are persisted as events so they can be undone.
- **Acceptance criteria:**
  - [ ] `e2e_US008_drag_balloon_persists_after_reload` passes
  - [ ] Balloons can be dragged, resized, retyped, and changed in type
  - [ ] Every change is an undoable event
- **Tests:** e2e_US008_drag_balloon_persists_after_reload, e2e_US008_drag_tail_tip_updates_tail, e2e_US008_resize_balloon_and_edit_text_inline, e2e_US008_change_balloon_type_to_shout, e2e_US008_add_caption_and_sfx, e2e_US008_rerun_auto_placement_resets_manual_positions, e2e_US021_undo_lettering_edit, test_studio_lettering_store_edit_emits_event, test_studio_lettering_balloon_drag_clamped_inside_panel
- **Depends on:** S3-T11

### S3-T13: Add image-side audience check
- **Labels:** type: security, area: safety, priority: p0, size: S, sprint: 3
- **Estimate:** S
- **Spec refs:** PRD FR-028, US-019, NFR-012, ARCHITECTURE ADR-013
- **Description:** The vision model returns a suitability verdict per take for the project audience. Failing takes are hidden and auto-retaken.
- **Acceptance criteria:**
  - [ ] Image outputs are checked by the vision model for audience suitability
  - [ ] Failing takes are hidden and auto-retaken
  - [ ] Blocked content is explained in plain words
- **Tests:** test_safety_image_audience_failing_take_hidden, test_safety_image_audience_failing_take_auto_retaken, test_safety_image_audience_verdict_per_take_cached, test_safety_image_audience_verdict_respects_project_audience, test_safety_image_audience_all_ages_blocks_gore_fixture, test_safety_image_audience_retake_exhausted_surfaces_plain_words_message
- **Depends on:** S3-T04

### Sprint 3 Gate
Hard stop. Sprint 4 does not start until every item is checked.
- [ ] Full duck story (8 strips) completed in the Studio with ComfyUI on the GPU runner and with Gemini on nightly
- [ ] NFR-004 consistency measured and recorded in `docs/EVALS.md`
- [ ] Zero model-drawn text in approved panels (OCR verified)
- [ ] Lettering property tests and goldens green
- [ ] Coverage at or above targets for `panels`, `qa`, `letter`, `layout`, `jobs`
- [ ] Retrospective written, `sprint-3-complete` tagged

---

## Sprint 4: Pages and Book

**Milestone:** Sprint 4: Pages and Book
**Duration:** 1 week
**Goal:** Finalized stories stitch into pages, and pages bind into a book built page by page.

### S4-T01: Define layout templates
- **Labels:** type: feature, area: layout, priority: p0, size: M, sprint: 4
- **Estimate:** M
- **Spec refs:** PRD FR-023, US-011, ARCHITECTURE Data formats (Layout), DESIGN Page layout templates
- **Description:** Templates per FR-023 as data (`layout/templates/*.yaml`) in page units with slots and reading order: strip-stack (3 per page default), classic-three-tier, grid-2x2, grid-3x3, splash-plus-two, and vertical-scroll (web). Page sizes: US comic (6.625 x 10.25 in), US Letter, A4, square 8.5 x 8.5 in, and web. Margins, gutter, and bleed are configurable.
- **Acceptance criteria:**
  - [ ] Template schema validation passes for all six templates
  - [ ] Goldens exist per template
  - [ ] Five page sizes are defined and margins, gutter, and bleed are configurable
- **Tests:** test_layout_templates_six_templates_load_and_validate, test_layout_templates_schema_rejects_overlapping_slots, test_layout_templates_slots_have_unique_reading_order, test_layout_page_sizes_us_comic_letter_a4_square_web, test_layout_margins_gutter_bleed_configurable, vis_template_strip_stack, vis_template_classic_three_tier, vis_template_grid_2x2, vis_template_grid_3x3, vis_template_splash_plus_two, vis_template_vertical_scroll
- **Depends on:** Sprint 3

### S4-T02: Implement auto-paginate
- **Labels:** type: feature, area: layout, priority: p0, size: M, sprint: 4
- **Estimate:** M
- **Spec refs:** PRD FR-023, US-011, ARCHITECTURE Pipelines (strip to page)
- **Description:** Stitch strips into pages without splitting strips (unless allowed), filling slots in order. Panel-level templates (three-tier, grids, splash) map strip panels into slots with aspect-aware crop and an optional re-render at the slot aspect ratio.
- **Acceptance criteria:**
  - [ ] Pagination respects strip boundaries by default
  - [ ] Pagination property tests pass and a panel is never dropped
  - [ ] User can change the page layout per page
- **Tests:** test_layout_paginate_never_splits_strip_by_default, test_layout_paginate_splits_strip_when_allowed, test_layout_paginate_property_never_drops_a_panel, test_layout_paginate_strip_stack_three_per_page_default, test_layout_paginate_three_tier_maps_panels_to_slots_in_order, test_layout_paginate_aspect_aware_crop_nondestructive, test_layout_paginate_slot_aspect_rerender_request_built, test_layout_paginate_extra_strips_flow_to_next_page, test_layout_paginate_user_override_layout_per_page
- **Depends on:** S4-T01

### S4-T03: Compose page SVG
- **Labels:** type: feature, area: layout, priority: p0, size: M, sprint: 4
- **Estimate:** M
- **Spec refs:** PRD FR-023, NFR-009, ARCHITECTURE ADR-008, DESIGN Page layout templates
- **Description:** Page SVG with panel art, lettering layers, borders, page captions, and page number. The bleed area extends the art when bleed is on.
- **Acceptance criteria:**
  - [ ] Goldens pass for every template and size
  - [ ] Lettering layer sits above the art
  - [ ] Bleed extends art only when enabled
- **Tests:** vis_page_strip_stack_us_comic, vis_page_three_tier_a4, vis_page_grid_2x2_letter, vis_page_grid_3x3_square, vis_page_splash_plus_two_us_comic, vis_page_vertical_scroll_web, vis_page_bleed_extends_art, test_layout_page_svg_contains_page_number_and_caption, test_layout_page_svg_lettering_layer_above_art, test_layout_page_svg_bleed_off_has_no_extra_area
- **Depends on:** S4-T02

### S4-T04: Build book model and builder
- **Labels:** type: feature, area: book, priority: p0, size: L, sprint: 4
- **Estimate:** L
- **Spec refs:** PRD FR-024, US-012, ARCHITECTURE Data formats (Book manifest), Data model
- **Description:** Book entity; page kinds (cover, title, dedication, story, cast, back, custom); chapters from multiple finalized stories; table of contents page generation; page numbering rules (no number on the cover and title).
- **Acceptance criteria:**
  - [ ] Add, remove, reorder, and duplicate pages
  - [ ] Page numbers shown, none on cover and title
  - [ ] Table of contents is generated for multi-story books
  - [ ] Book metadata holds title, author, year, and language
  - [ ] Optional about-the-characters page is built from character sheets
- **Tests:** test_book_page_kinds_cover_title_dedication_story_cast_back_custom, test_book_add_remove_reorder_duplicate_pages, test_book_page_numbers_skip_cover_and_title, test_book_toc_generated_for_multi_story, test_book_toc_not_generated_for_single_story, test_book_chapters_from_multiple_finalized_stories, test_book_unfinalized_story_cannot_be_added, test_book_metadata_title_author_year_language, test_book_cast_page_built_from_character_sheets, test_book_manifest_roundtrip
- **Depends on:** S4-T03

### S4-T05: Generate book covers
- **Labels:** type: feature, area: book, priority: p1, size: M, sprint: 4
- **Estimate:** M
- **Spec refs:** PRD FR-024, US-012, ARCHITECTURE ADR-004, Pipelines (book to export)
- **Description:** Cover art from a cover prompt derived from the bible and cast (rendered with references) or chosen from panels. Title and author lettering use a cover typography preset. The back cover carries the blurb.
- **Acceptance criteria:**
  - [ ] Cover renders with the mock backend
  - [ ] Cover passes QA with ComfyUI on the GPU runner
  - [ ] Back cover shows the blurb
- **Tests:** test_book_cover_prompt_derived_from_bible_and_cast, test_book_cover_chosen_from_existing_panel, test_book_cover_title_author_lettering_uses_cover_preset, test_book_back_cover_has_blurb, it_book_cover_renders_with_mock_backend, it_book_cover_gpu_passes_qa_with_comfyui, vis_cover_front_picture_book
- **Depends on:** S4-T04

### S4-T06: Build Studio Pages view
- **Labels:** type: feature, area: studio, priority: p0, size: L, sprint: 4
- **Estimate:** L
- **Spec refs:** PRD FR-023, FR-029, US-011, DESIGN Wireframes (Pages), Component inventory
- **Description:** Page list, page canvas, layout picker, drag panels between slots, an unplaced strips tray, an auto-paginate button, and page captions.
- **Acceptance criteria:**
  - [ ] e2e: change layout, drag a panel, undo
  - [ ] Auto-paginate fills pages and the tray lists leftovers
- **Tests:** e2e_US011_change_layout_drag_panel_undo, e2e_US011_auto_paginate_button_fills_pages, e2e_US011_unplaced_strips_tray_lists_leftovers, e2e_US011_add_page_caption, test_studio_pages_store_move_panel_between_slots, test_studio_pages_store_layout_change_preserves_panels
- **Depends on:** S4-T03

### S4-T07: Build Studio Book view
- **Labels:** type: feature, area: studio, priority: p0, size: L, sprint: 4
- **Estimate:** L
- **Spec refs:** PRD FR-024, FR-029, US-012, DESIGN Wireframes (Book), Component inventory
- **Description:** Spread view, page strip, add page by kind, reorder by drag, an inspector for page fields, cover picker and generator, and chapter management.
- **Acceptance criteria:**
  - [ ] e2e: build a 6-page book with cover and title page
  - [ ] Pages can be reordered by drag and added by kind
- **Tests:** e2e_US012_build_six_page_book_with_cover_and_title, e2e_US012_reorder_pages_by_drag, e2e_US012_add_page_by_kind, e2e_US012_generate_cover_from_book_view, e2e_US012_chapter_management_for_two_stories, test_studio_book_store_reorder_emits_event
- **Depends on:** S4-T04, S4-T06

### S4-T08: Add pages and book CLI
- **Labels:** type: feature, area: cli, priority: p1, size: S, sprint: 4
- **Estimate:** S
- **Spec refs:** PRD FR-030, FR-023, FR-024, ARCHITECTURE Contracts (CLI)
- **Description:** `pages`, `book add-page|move|remove|cover|show`, all with `--json`.
- **Acceptance criteria:**
  - [ ] Smoke test extended through book creation
  - [ ] CLI and Studio operate on the same project files
- **Tests:** smoke_cli_pages_and_book_build_extends_auto, test_cli_pages_json_lists_pages, test_cli_book_add_page_move_remove, test_cli_book_cover_sets_cover, test_cli_book_show_json
- **Depends on:** S4-T04

### Sprint 4 Gate
Hard stop. Sprint 5 does not start until every item is checked.
- [ ] Finalized duck story paginates in all templates without losing panels
- [ ] A book with cover, title, story pages, and back cover is buildable in Studio and CLI
- [ ] Page goldens green
- [ ] Retrospective written, `sprint-4-complete` tagged

---

## Sprint 5: Export

**Milestone:** Sprint 5: Export
**Duration:** 1 week
**Goal:** Every page, story, and book exports as images, PDF, CBZ, long strip, and a web page that matches the Studio exactly.

### S5-T01: Build Chromium renderer
- **Labels:** type: feature, area: export, priority: p0, size: M, sprint: 5
- **Estimate:** M
- **Spec refs:** PRD FR-025, NFR-009, ARCHITECTURE ADR-008, Pipelines (book to export)
- **Description:** Playwright Chromium with the network disabled (route abort for any non-`data:`/`file:` request), device scale factor computed from the target dpi, and page SVG to PNG. One browser per export job, pages streamed.
- **Acceptance criteria:**
  - [ ] Pixel diff between the Studio preview capture and the export is under 0.1 percent
  - [ ] Any non-data and non-file request is aborted
  - [ ] One browser is used per export job
- **Tests:** it_export_chromium_pixel_diff_vs_studio_preview_under_0_1_percent, it_export_chromium_network_disabled_blocks_http, test_export_chromium_dsf_computed_from_target_dpi, it_export_chromium_one_browser_per_job_pages_streamed, it_export_chromium_missing_browser_error_hint, test_export_chromium_data_and_file_urls_allowed
- **Depends on:** Sprint 4

### S5-T02: Add image exports
- **Labels:** type: feature, area: export, priority: p0, size: M, sprint: 5
- **Estimate:** M
- **Spec refs:** PRD FR-025, US-013, US-014, NFR-010, ARCHITECTURE Pipelines (book to export)
- **Description:** PNG, JPG (quality 92), and WebP at 72, 150, and 300 dpi. Long strip image (strips stacked vertically, max height guard with automatic splitting into parts for social sizes). An upscale step for print when art is under the target resolution (Real-ESRGAN via a ComfyUI workflow when available, else Lanczos with a warning).
- **Acceptance criteria:**
  - [ ] Dimensions and dpi metadata are correct for each format and dpi
  - [ ] Long strip splits into parts above the max height
  - [ ] Upscale falls back to Lanczos with a warning
- **Tests:** it_export_png_300dpi_dimensions_and_metadata, it_export_jpg_quality_92, it_export_webp_written, test_export_dpi_options_72_150_300_resolved, it_export_long_strip_stacks_strips_vertically, test_export_long_strip_splits_into_parts_over_max_height, test_export_upscale_applied_when_art_below_target_dpi, test_export_upscale_falls_back_to_lanczos_with_warning, test_export_option_resolution_defaults_per_format
- **Depends on:** S5-T01

### S5-T03: Add PDF export
- **Labels:** type: feature, area: export, priority: p0, size: L, sprint: 5
- **Estimate:** L
- **Spec refs:** PRD FR-025, NFR-009, NFR-010, ARCHITECTURE ADR-008, Pipelines (book to export)
- **Description:** Book HTML (one page per SVG) printed with Chromium `page.pdf` at the exact page size (plus bleed for print). Post-process with pikepdf: set TrimBox and BleedBox, document metadata (title, author, subject, keywords, producer), an optional trim marks layer, and page labels. Verify fonts are embedded and text is selectable.
- **Acceptance criteria:**
  - [ ] PDF text in balloons is selectable and searchable
  - [ ] Print PDF adds 0.125 in bleed and optional trim marks
  - [ ] Fonts are embedded; page count and size match the book
  - [ ] Opens in Preview, Acrobat, Chrome, and iOS Books (manual checklist)
- **Tests:** it_export_pdf_fonts_embedded_and_text_selectable, it_export_pdf_print_adds_bleed, it_export_pdf_trimbox_and_bleedbox_set, it_export_pdf_metadata_title_author_subject_keywords_producer, it_export_pdf_page_count_and_size_match_book, it_export_pdf_trim_marks_layer_optional, it_export_pdf_page_labels_skip_cover, it_export_pdf_balloon_text_searchable, test_export_pdf_screen_vs_print_option_resolution, smoke_export_pdf_manual_viewers_checklist
- **Depends on:** S5-T01

### S5-T04: Add CBZ export
- **Labels:** type: feature, area: export, priority: p2, size: S, sprint: 5
- **Estimate:** S
- **Spec refs:** PRD FR-025, US-013, ARCHITECTURE Pipelines (book to export)
- **Description:** A zip of page images in order with `ComicInfo.xml` metadata.
- **Acceptance criteria:**
  - [ ] Archive structure validates
  - [ ] Opens in a CBZ reader (manual)
- **Tests:** it_export_cbz_pages_in_order, it_export_cbz_comicinfo_xml_valid, test_export_cbz_filename_padding_sorts_lexically, it_export_cbz_zip_structure_validates
- **Depends on:** S5-T02

### S5-T05: Build reader web component
- **Labels:** type: feature, area: reader, priority: p0, size: L, sprint: 5
- **Estimate:** L
- **Spec refs:** PRD NFR-007, FR-025, US-013, ARCHITECTURE ADR-014, DESIGN Reader spec
- **Description:** `@mr-comic-smith/reader`: a zero-dependency TypeScript web component with flipbook and scroll modes, keyboard and swipe, spreads on wide screens, reduced motion, alt text, and balloons rendered as DOM text over images (positions from the lettering JSON) so text is selectable. Under 25 KB gzipped.
- **Acceptance criteria:**
  - [ ] WCAG 2.2 AA: axe reports zero violations
  - [ ] Alt text for every panel
  - [ ] e2e passes for both modes
  - [ ] Bundle is under 25 KB gzipped
- **Tests:** e2e_US013_reader_flipbook_keyboard_and_swipe, e2e_US013_reader_scroll_mode_stacks_pages, e2e_US013_reader_axe_zero_violations, test_reader_spread_on_wide_screens, test_reader_reduced_motion_disables_page_turn, test_reader_alt_text_per_panel, test_reader_balloons_rendered_as_dom_text, test_reader_bundle_under_25kb_gzipped, test_reader_no_external_requests
- **Depends on:** S4-T03

### S5-T06: Add web export
- **Labels:** type: feature, area: export, priority: p0, size: M, sprint: 5
- **Estimate:** M
- **Spec refs:** PRD FR-025, US-023, NFR-007, ARCHITECTURE ADR-014, DESIGN Reader spec
- **Description:** A static folder (index.html, reader.js, pages/*.webp, book.json) and a single-file mode (everything inlined as base64, size warning above 50 MB). Open Graph tags with the cover image. `data-narrate` markup: the book title as `h1` and each page's balloons in reading order as paragraphs inside `<article data-narrate>` (visually hidden for screen readers and narration, with `data-narrate-role` for speaker names) so mr-audio-smith can narrate it.
- **Acceptance criteria:**
  - [ ] Web export works offline from file://, is responsive, and is keyboard navigable
  - [ ] Alt text per panel comes from the panel action description
  - [ ] Reading text carries data-narrate attributes for mr-audio-smith
  - [ ] Single-file mode warns above 50 MB
- **Tests:** it_export_web_single_file_works_offline, it_export_web_has_data_narrate_markup, it_export_web_static_folder_layout, it_export_web_works_from_file_url, it_export_web_og_tags_with_cover, it_export_web_single_file_size_warning_over_50mb, it_export_web_title_h1_and_speaker_roles, it_export_web_balloons_in_reading_order_in_narrate_article, it_export_web_alt_text_from_panel_action, smoke_export_web_narrated_by_audio_smith
- **Depends on:** S5-T05

### S5-T07: Build Studio export dialog and CLI export
- **Labels:** type: feature, area: studio, priority: p0, size: M, sprint: 5
- **Estimate:** M
- **Spec refs:** PRD FR-025, FR-029, FR-030, US-013, US-014, DESIGN Wireframes (Export dialog)
- **Description:** Export dialog per DESIGN: target (page, story, book), format cards (PNG, PDF, Web, CBZ, Long strip), options per format (dpi, print bleed, trim marks, single file), estimated size, Export button, progress, then 'Open folder' and 'Copy path'. Export history list. CLI `export` with all formats.
- **Acceptance criteria:**
  - [ ] `e2e_US013_export_book_pdf_from_studio` passes
  - [ ] CLI `export` supports every format and the page, story, and book targets
  - [ ] Export history lists previous exports
- **Tests:** e2e_US013_export_book_pdf_from_studio, e2e_US014_export_long_strip_from_studio, e2e_US013_export_history_lists_previous_exports, smoke_cli_auto_to_pdf_outputs_exist, smoke_cli_export_json_lists_files, test_cli_export_all_formats_flag_parsing, test_cli_export_target_page_story_book, test_studio_export_dialog_store_estimates_size
- **Depends on:** S5-T03, S5-T06

### Sprint 5 Gate
Hard stop. Sprint 6 does not start until every item is checked.
- [ ] All formats export from Studio and CLI for page, story, and book targets
- [ ] PDF fidelity, embedded fonts, selectable text verified
- [ ] Web export works offline and narrates with mr-audio-smith (manual check recorded)
- [ ] Retrospective written, `sprint-5-complete` tagged

---

## Sprint 6: Release v1.0.0

**Milestone:** Sprint 6: Release v1.0.0
**Duration:** 1 week
**Goal:** Ship v1.0.0 with child mode, auto mode, safety review, evaluations, and docs.

### S6-T01: Build child mode
- **Labels:** type: feature, area: studio, priority: p0, size: L, sprint: 6
- **Estimate:** L
- **Spec refs:** PRD US-004, NFR-007, FR-029, DESIGN Child mode rules
- **Description:** DESIGN child mode: a 'Kid mode' toggle showing only the current strip, three big picture choices (240 px thumbnail plus a 3 to 5 word label read aloud with the browser's speech synthesis on tap), a big 'Make it!' button that renders and auto-letters, and a 'Read our comic' button that opens the reader. No settings, no text fields, no delete. A parent exits with a long press (2 s) on the lock icon.
- **Acceptance criteria:**
  - [ ] `e2e_US004_child_mode_pick_choice_renders_strip` passes
  - [ ] 64 px minimum targets are verified
  - [ ] No settings, text fields, or delete are reachable in child mode
  - [ ] Long press of 2 s exits
- **Tests:** e2e_US004_child_mode_pick_choice_renders_strip, e2e_US004_child_mode_touch_targets_at_least_64px, e2e_US004_child_mode_hides_settings_and_delete, e2e_US004_child_mode_long_press_exit_after_2s, e2e_US004_child_mode_choice_label_read_aloud, e2e_US004_child_mode_read_our_comic_opens_reader, e2e_US004_child_mode_axe_zero_violations, test_studio_child_mode_store_long_press_threshold
- **Depends on:** Sprint 5

### S6-T02: Complete auto mode end to end
- **Labels:** type: feature, area: story, priority: p1, size: M, sprint: 6
- **Estimate:** M
- **Spec refs:** PRD FR-026, US-016, FR-033, ARCHITECTURE ADR-010
- **Description:** Extend `auto` to render, QA, letter, and approve strips. Add a Studio button 'Draft the rest for me' with progress and per-strip review afterwards. The policy is steer-heavy, balanced, or twist-heavy and the run stops before finalize.
- **Acceptance criteria:**
  - [ ] Policy picks suggestions until the target length, then stops before finalize
  - [ ] Every auto action is recorded with actor `auto` and is undoable
  - [ ] Studio shows progress and allows per-strip review
- **Tests:** test_story_auto_policy_steer_heavy_picks_steer, test_story_auto_policy_twist_heavy_picks_twist, test_story_auto_policy_balanced_mix, test_story_auto_stops_at_target_before_finalize, test_story_auto_actions_recorded_with_actor_auto, test_story_auto_each_action_undoable, test_story_auto_qa_failure_after_retakes_flags_strip_for_review, it_story_auto_renders_letters_approves_with_mock_backend, e2e_US016_draft_the_rest_for_me_shows_progress_and_review
- **Depends on:** Sprint 5

### S6-T03: Run safety review
- **Labels:** type: security, area: safety, priority: p0, size: M, sprint: 6
- **Estimate:** M
- **Spec refs:** PRD NFR-012, NFR-001, NFR-002, FR-006, FR-007, FR-028, ARCHITECTURE Security and safety model
- **Description:** Walk the Security Guidelines checklist. Build a red-team prompt set for the originality and audience guards (documented test set). Add `pip-audit`, `npm audit`, `gitleaks`, and bandit (ruff S) in CI. Fuzz uploads.
- **Acceptance criteria:**
  - [ ] Report `docs/SECURITY_REVIEW.md` is written
  - [ ] Zero high or critical findings
  - [ ] Guards are enforced in core, not only in the UI
- **Tests:** test_safety_redteam_originality_prompts_all_blocked, test_safety_redteam_audience_prompts_all_blocked, test_safety_redteam_people_prompts_all_declined, it_safety_fuzz_uploads_never_crash_ingest, test_ci_security_jobs_pip_audit_npm_audit_gitleaks_bandit_declared, test_safety_zero_telemetry_no_outbound_calls_by_default, test_safety_guards_enforced_below_front_doors, test_safety_review_doc_has_no_high_or_critical_findings
- **Depends on:** Sprint 5

### S6-T04: Run evaluation round
- **Labels:** type: test, area: qa, priority: p0, size: M, sprint: 6
- **Estimate:** M
- **Spec refs:** PRD NFR-004, NFR-005, ARCHITECTURE ADR-004
- **Description:** Run the TEST_PLAN model evaluation (section 6) on the three fixture stories with the default local backend and with Gemini. Record results in `docs/EVALS.md`.
- **Acceptance criteria:**
  - [ ] NFR-004 met: at least 90 percent of character appearances score 4 or higher after retakes
  - [ ] Human scores average at least 4 of 5
  - [ ] Zero model-drawn text in approved panels (OCR verified)
  - [ ] Results recorded in `docs/EVALS.md`
- **Tests:** it_eval_duck_story_consistency_at_least_90_percent_score_4_plus, it_eval_robot_story_consistency_at_least_90_percent, it_eval_newsletter_gpu_gag_consistency_at_least_90_percent, it_eval_gemini_backend_duck_story_consistency, it_eval_zero_model_drawn_text_in_approved_panels, smoke_eval_human_scores_average_at_least_4, test_eval_script_writes_evals_md_table
- **Depends on:** S6-T02

### S6-T05: Write docs site
- **Labels:** type: docs, area: cli, priority: p0, size: L, sprint: 6
- **Estimate:** L
- **Spec refs:** PRD Success metrics, FR-030, ARCHITECTURE Contracts
- **Description:** README plus an mkdocs-material site at getcomicsmith.com: quickstart (cloud and local paths), making your first comic (duck tutorial with screenshots), cast and consistency tips, styles, pages and books, exports and printing, safety and originality, backends and GPUs, CLI and API reference, and troubleshooting.
- **Acceptance criteria:**
  - [ ] Quickstart completes in under 15 minutes on a fresh machine with a cloud key
  - [ ] mkdocs build is strict with no broken links
  - [ ] CLI and API references match the code
- **Tests:** smoke_docs_mkdocs_build_strict_no_broken_links, smoke_docs_quickstart_commands_copy_paste_cleanly, smoke_docs_quickstart_under_15_minutes_fresh_machine, test_docs_cli_reference_matches_typer_commands, test_docs_api_reference_matches_openapi, test_docs_site_sections_all_listed_present
- **Depends on:** S6-T03

### S6-T06: Generate THIRD_PARTY_LICENSES.md
- **Labels:** type: docs, area: packaging, priority: p0, size: S, sprint: 6
- **Estimate:** S
- **Spec refs:** PRD NFR-011, ARCHITECTURE ADR-006
- **Description:** Generated from pip-licenses and license-checker, plus sections for model weights (per workflow), fonts (OFL texts included), and bundled assets. CI fails on missing entries.
- **Acceptance criteria:**
  - [ ] File is complete and verified at implementation time
  - [ ] CI fails when an entry is missing
  - [ ] Non-commercial weights are labeled
- **Tests:** test_licenses_third_party_file_covers_all_python_deps, test_licenses_third_party_file_covers_all_npm_deps, test_licenses_model_weights_section_per_workflow, test_licenses_fonts_ofl_texts_included, test_licenses_ci_fails_on_missing_entry, test_licenses_non_commercial_weights_labeled
- **Depends on:** S6-T03

### S6-T07: Build release pipeline and ship v1.0.0
- **Labels:** type: chore, area: packaging, priority: p0, size: M, sprint: 6
- **Estimate:** M
- **Spec refs:** PRD NFR-008, NFR-011, ARCHITECTURE Deployment topologies
- **Description:** Release workflow per the Versioning section: TestPyPI rc first, then v1.0.0 to PyPI (with the bundled Studio static assets in the wheel) and npm (reader), and a GitHub Release with an SBOM. PyPI and npm publishing needs trusted-publisher setup by the owner and is recorded as a manual step if unavailable to the executing agent.
- **Acceptance criteria:**
  - [ ] `uv tool install mr-comic-smith` installs v1.0.0 and `studio` works offline after install
  - [ ] GitHub Release carries an SBOM
  - [ ] Provenance attestation is attached
- **Tests:** it_release_testpypi_rc_install_and_studio_offline, it_release_wheel_contains_studio_static_assets, test_release_workflow_runs_check_versions, test_release_github_release_attaches_sbom, test_release_npm_package_reader_published_files, test_release_provenance_attestation_declared, smoke_release_uv_tool_install_v1_0_0_studio_works_offline, smoke_release_duck_book_launch_validation
- **Depends on:** S6-T04, S6-T05, S6-T06

### Sprint 6 Gate
Hard stop. Release v1.0.0 only after every item is checked.
- [ ] Release checklist complete
- [ ] v1.0.0 published with provenance
- [ ] Duck book made with v1.0.0 and exported to PDF and web as the launch validation
- [ ] Retrospective written, `sprint-6-complete` tagged, `v1.0.0` annotated tag on `main`

---

## Sprint 7: Server and MCP

**Milestone:** Sprint 7: Server and MCP
**Duration:** 1 week
**Goal:** mr-comic-smith runs as a shared service for a classroom or team, and agents can make comics through MCP.

### S7-T01: Harden the server
- **Labels:** type: feature, area: server, priority: p0, size: M, sprint: 7
- **Estimate:** M
- **Spec refs:** PRD FR-032, NFR-012, ARCHITECTURE Contracts (REST API), Security and safety model
- **Description:** `serve` mode without Studio static (API only) and with it. Bearer token on non-localhost binds, rate limits, a `/readyz` reflecting backend, LLM, vision, and Chromium readiness, problem+json everywhere, and OpenAPI published at `/v1/openapi.json`.
- **Acceptance criteria:**
  - [ ] Long jobs report progress
  - [ ] Bearer token is required for non-localhost binding
  - [ ] Auth tests pass and readiness flips when a dependency is down
  - [ ] OpenAPI is published at `/v1/openapi.json`
- **Tests:** test_server_non_localhost_requires_bearer_token, test_server_localhost_allows_without_token, test_server_wrong_token_returns_401, test_server_rate_limit_returns_429, it_server_readyz_flips_when_dependency_down, test_server_errors_are_problem_json, test_server_openapi_published_at_v1_openapi_json, test_server_api_only_mode_serves_no_static, test_server_with_studio_serves_static
- **Depends on:** Sprint 6

### S7-T02: Add LAN classroom mode
- **Labels:** type: feature, area: server, priority: p1, size: L, sprint: 7
- **Estimate:** L
- **Spec refs:** PRD FR-034, US-024, NFR-012, ARCHITECTURE Deployment topologies
- **Description:** `studio --lan --access-code` with per-user workspaces (name chosen at join, stored in a workspace table), project sharing within the instance, a teacher view listing all projects, and GPU job fairness (round-robin by user).
- **Acceptance criteria:**
  - [ ] Access code is required to join
  - [ ] Users see only their own projects unless shared
  - [ ] e2e with two browser contexts passes
- **Tests:** e2e_US024_two_browsers_see_only_own_projects, e2e_US024_access_code_required_to_join, e2e_US024_teacher_view_lists_all_projects, test_server_workspaces_name_chosen_at_join, test_server_project_sharing_within_instance, test_server_lan_requires_access_code_flag, test_server_wrong_access_code_rejected, it_jobs_gpu_fairness_round_robin_by_user
- **Depends on:** S7-T01

### S7-T03: Build MCP server
- **Labels:** type: feature, area: mcp, priority: p0, size: L, sprint: 7
- **Estimate:** L
- **Spec refs:** PRD FR-032, US-017, NFR-012, ARCHITECTURE Contracts (MCP tools), ADR-013
- **Description:** Official Python MCP SDK with stdio and streamable HTTP transports. Thirteen tools: `mr_comic_smith_create_project`, `_approve_character`, `_suggest_next`, `_make_strip` (long-running with progress notifications per panel), `_edit_panel`, `_finalize`, `_build_book`, `_export`, `_list_styles`, `_list_backends`, `_status`, `_recommend` (the full signatures are in Appendix E of the build prompt). Tool descriptions state the originality and people rules so agents do not attempt to bypass them.
- **Acceptance criteria:**
  - [ ] MCP inspector lists valid schemas for all tools
  - [ ] Integration test drives create, suggest, make_strip, export with mocks over stdio
  - [ ] Progress notifications are sent per panel during make_strip
  - [ ] Guards apply identically to MCP calls
- **Tests:** it_mcp_stdio_create_suggest_make_strip_export_with_mocks, test_mcp_tools_list_all_thirteen_tools, test_mcp_tool_schemas_valid_json_schema, test_mcp_tool_descriptions_state_originality_and_people_rules, it_mcp_make_strip_emits_progress_notifications_per_panel, it_mcp_streamable_http_transport_handshake, test_mcp_approve_character_blocked_by_originality_returns_error, test_mcp_create_project_person_photo_requires_attestation, test_mcp_list_backends_reports_capabilities, test_mcp_recommend_returns_style_audience_arc
- **Depends on:** S7-T01

### S7-T04: Add remote mode for CLI
- **Labels:** type: feature, area: cli, priority: p2, size: M, sprint: 7
- **Estimate:** M
- **Spec refs:** PRD FR-030, FR-032, ARCHITECTURE Contracts (CLI, REST API)
- **Description:** `--server URL --token` makes CLI commands operate against a remote server and download exports.
- **Acceptance criteria:**
  - [ ] End-to-end test passes against a local server process
  - [ ] Exports are downloaded to the local machine
- **Tests:** it_cli_remote_server_new_suggest_strip_against_local_server, it_cli_remote_export_downloads_files, test_cli_remote_token_sent_as_bearer, test_cli_remote_unreachable_server_exit_code, test_cli_remote_flags_env_precedence
- **Depends on:** S7-T01

### Sprint 7 Gate
Hard stop. Sprint 8 does not start until every item is checked.
- [ ] A laptop browser uses the Studio on the GPU box in LAN mode with an access code
- [ ] Claude Code makes a 4-panel strip and exports a PDF through MCP
- [ ] Coverage for `server` and `mcp_server` at or above targets
- [ ] Retrospective written, `sprint-7-complete` tagged

---

## Sprint 8: Harness Integrations

**Milestone:** Sprint 8: Harness Integrations
**Duration:** 1 week
**Goal:** "Make a comic about my duck" works from Pi, Goose, OpenCode, and Claude Code.

### S8-T01: Build Pi extension
- **Labels:** type: feature, area: harness, priority: p0, size: L, sprint: 8
- **Estimate:** L
- **Spec refs:** PRD FR-032, US-017, ARCHITECTURE Contracts (MCP tools), Appendix F of the build prompt
- **Description:** `@mr-comic-smith/pi-extension` on `pi-agent-core` plus TypeBox, calling REST. TypeBox schemas mirror the MCP tools. Slash commands: `/comic new <name>`, `/comic next` (shows three options, user picks by number), `/comic strip <n|"beat">`, `/comic book`, `/comic export pdf|web`. Streams panel progress with `onUpdate`; the context extension lists styles and the active project.
- **Acceptance criteria:**
  - [ ] vitest unit tests pass with mocked REST
  - [ ] A manual Pi session is recorded in TEST_PLAN
- **Tests:** test_pi_commands_comic_new_calls_rest_create_project, test_pi_commands_comic_next_shows_three_options_pick_by_number, test_pi_commands_comic_strip_by_number_or_beat, test_pi_commands_comic_book_and_export, test_pi_on_update_streams_panel_progress, test_pi_context_extension_lists_styles_and_active_project, test_pi_typebox_schemas_mirror_mcp_tools, test_pi_rest_error_surfaced_as_message, smoke_pi_manual_session_recorded
- **Depends on:** Sprint 7

### S8-T02: Add Goose toolkit
- **Labels:** type: feature, area: harness, priority: p1, size: S, sprint: 8
- **Estimate:** S
- **Spec refs:** PRD FR-032, US-017, ARCHITECTURE Contracts (MCP tools), Appendix F of the build prompt
- **Description:** `integrations/goose/toolkit.yaml` launches `mr-comic-smith mcp` over stdio so Goose, which speaks MCP natively, gets all thirteen tools with no custom code. Add a short README with setup steps and an example prompt ('Make a comic about my duck').
- **Acceptance criteria:**
  - [ ] Smoke test lists the tools from Goose
  - [ ] Toolkit file parses and launches the MCP command
  - [ ] README documents setup
- **Tests:** smoke_goose_toolkit_lists_tools, test_goose_toolkit_yaml_launches_mr_comic_smith_mcp, test_goose_toolkit_yaml_parses, smoke_goose_scripted_session_new_to_export_with_mocks
- **Depends on:** Sprint 7

### S8-T03: Add OpenCode config
- **Labels:** type: docs, area: harness, priority: p1, size: S, sprint: 8
- **Estimate:** S
- **Spec refs:** PRD FR-032, US-017, ARCHITECTURE Contracts (MCP tools), Appendix F of the build prompt
- **Description:** `integrations/opencode/opencode.json.example` plus a README. OpenCode speaks MCP natively, so this is configuration and documentation only, with zero code. The example registers the local MCP command and documents the remote HTTP option with a token.
- **Acceptance criteria:**
  - [ ] Smoke test lists the tools from OpenCode
  - [ ] Example config parses and points at the MCP command
  - [ ] README documents setup
- **Tests:** smoke_opencode_config_lists_tools, test_opencode_example_json_parses_and_points_to_mcp_command, test_opencode_readme_documents_setup_steps, smoke_opencode_scripted_session_new_to_export_with_mocks
- **Depends on:** Sprint 7

### S8-T04: Create Claude Code skill
- **Labels:** type: feature, area: harness, priority: p1, size: M, sprint: 8
- **Estimate:** M
- **Spec refs:** PRD FR-032, US-017, NFR-012, Appendix F of the build prompt
- **Description:** A skill teaching the co-plotting loop through MCP: create, approve character (show the sheet path to the user first), suggest, ask the user which option, make strip, repeat, finalize, build book, export. Includes the rules on originality and people, and `claude mcp add` instructions.
- **Acceptance criteria:**
  - [ ] Scripted session makes a 3-strip story with mocks
  - [ ] Skill requires showing the sheet path before strips
  - [ ] Skill states the originality and people rules
- **Tests:** smoke_claude_code_scripted_session_makes_three_strip_story, test_claude_code_skill_md_frontmatter_valid, test_claude_code_skill_states_originality_and_people_rules, test_claude_code_skill_requires_showing_sheet_path_before_strips, test_claude_code_skill_documents_claude_mcp_add_command, test_claude_code_skill_loop_order_create_approve_suggest_make_finalize_book_export
- **Depends on:** Sprint 7

### S8-T05: Add harness smoke tests in CI
- **Labels:** type: test, area: ci, priority: p2, size: M, sprint: 8
- **Estimate:** M
- **Spec refs:** PRD FR-032, ARCHITECTURE Contracts (MCP tools)
- **Description:** A `harness-smoke-tests` job on staging and release: MCP stdio handshake and `tools/list`, plus Pi extension unit tests.
- **Acceptance criteria:**
  - [ ] Job is green on staging
  - [ ] Job runs only on staging and release
- **Tests:** smoke_harness_mcp_stdio_handshake, smoke_harness_mcp_tools_list_matches_expected, test_harness_ci_job_runs_pi_extension_unit_tests, test_ci_harness_smoke_job_runs_on_staging_and_release_only, smoke_harness_green_on_staging
- **Depends on:** S8-T01, S8-T02, S8-T03, S8-T04

### Sprint 8 Gate
Hard stop. Sprint 9 does not start until every item is checked.
- [ ] Each harness completes a recorded mock session from new project to export
- [ ] Docs cover setup for all four harnesses
- [ ] Retrospective written, `sprint-8-complete` tagged

---

## Sprint 9: Packaging

**Milestone:** Sprint 9: Packaging
**Duration:** 1 week
**Goal:** All three deployment tiers documented and tested.

### S9-T01: Build Dockerfiles
- **Labels:** type: chore, area: packaging, priority: p0, size: L, sprint: 9
- **Estimate:** L
- **Spec refs:** PRD NFR-008, ARCHITECTURE Deployment topologies
- **Description:** `Dockerfile.cpu` (python slim, Chromium deps, non-root, Studio bundled), `Dockerfile.cuda` (CUDA runtime base for future in-process backends; same app), and `Dockerfile.comfyui` (pinned ComfyUI commit, required custom nodes pinned by commit, no model weights baked in). Multi-arch amd64 and arm64.
- **Acceptance criteria:**
  - [ ] Images run `doctor` green
  - [ ] CPU image is under 1.5 GB
  - [ ] Images run as non-root; the ComfyUI image has no model weights
- **Tests:** smoke_docker_cpu_image_doctor_green, smoke_docker_cuda_image_doctor_green, smoke_docker_cpu_image_under_1_5_gb, smoke_docker_cpu_image_studio_bundled_serves_root, smoke_docker_multiarch_manifest_has_amd64_and_arm64, test_docker_images_run_as_non_root, test_docker_comfyui_image_pins_commit_and_nodes, test_docker_comfyui_image_contains_no_model_weights
- **Depends on:** Sprint 7

### S9-T02: Add Compose files
- **Labels:** type: chore, area: packaging, priority: p0, size: M, sprint: 9
- **Estimate:** M
- **Spec refs:** PRD NFR-001, NFR-008, ARCHITECTURE Deployment topologies
- **Description:** `deploy/docker-compose.local.yml` (ollama, ollama-pull, comfyui, models-pull, and comic-smith services as specified in Appendix G, access code required) and `deploy/docker-compose.prod.yml` (images pinned by digest, resource limits, read-only root filesystems with writable volumes only, internal network for ollama and comfyui with no published ports, comic-smith behind a TLS reverse proxy, restart policies, log rotation, server token and access code from secrets).
- **Acceptance criteria:**
  - [ ] `docker compose -f deploy/docker-compose.local.yml up` on a GPU host serves the Studio and completes the duck strip
  - [ ] Local file requires `COMIC_SMITH_ACCESS_CODE`
  - [ ] Prod file pins digests, uses read-only roots, and publishes no ollama or comfyui ports
- **Tests:** smoke_compose_local_up_serves_studio, smoke_compose_local_duck_strip_completes_on_gpu_host, test_compose_local_yaml_valid_config, test_compose_local_requires_access_code_env, test_compose_prod_images_pinned_by_digest, test_compose_prod_read_only_root_filesystems, test_compose_prod_ollama_comfyui_not_published, test_compose_prod_secrets_for_token_and_access_code
- **Depends on:** S9-T01

### S9-T03: Build Helm chart
- **Labels:** type: chore, area: packaging, priority: p0, size: L, sprint: 9
- **Estimate:** L
- **Spec refs:** PRD NFR-008, ARCHITECTURE Deployment topologies, Appendix G of the build prompt
- **Description:** `charts/mr-comic-smith`: StatefulSet `comfyui` (one NVIDIA GPU, PVC 100Gi, init container runs `models pull` with checksum verification, readiness on `/system_stats`), optional StatefulSet `ollama` (PVC 50Gi; or an existing OpenAI-compatible vLLM endpoint), StatefulSet `comic-smith` (single replica in v1 because the SQLite job queue and project databases live on one volume; PVC 50Gi; Secret for server token and access code; liveness `/healthz`, readiness `/readyz`), optional Deployment `comic-smith-export` (HPA on CPU, ReadWriteMany PVC), Ingress (TLS, `proxy-read-timeout: 900`, `proxy-body-size: 25m`, WebSocket upgrade), NetworkPolicy (only comic-smith pods reach comfyui and ollama), and `values-k3s-gpu.yaml` for a 2-node k3s plus Cilium GPU cluster.
- **Acceptance criteria:**
  - [ ] `helm lint`, `helm template`, and `ct install` in kind with the mock backend pass
  - [ ] Manual GPU cluster install is documented
  - [ ] comic-smith StatefulSet is a single replica
- **Tests:** smoke_helm_lint_passes, smoke_helm_template_renders_all_resources, smoke_helm_ct_install_kind_mock_backend, test_helm_comic_smith_statefulset_single_replica, test_helm_networkpolicy_only_comic_smith_reaches_comfyui_ollama, test_helm_ingress_timeout_body_size_websocket, test_helm_values_k3s_gpu_renders, test_helm_export_deployment_optional_hpa
- **Depends on:** S9-T01

### S9-T04: Sign and publish images and chart
- **Labels:** type: chore, area: ci, area: packaging, priority: p1, size: M, sprint: 9
- **Estimate:** M
- **Spec refs:** PRD NFR-011, ARCHITECTURE Deployment topologies
- **Description:** Publish workflow signs container images and the Helm chart with cosign (keyless, GitHub OIDC), attaches an SBOM attestation to each image, and runs only on release tags. Verification instructions go in the docs.
- **Acceptance criteria:**
  - [ ] `cosign verify` succeeds for released images and chart
  - [ ] SBOM attestation is attached to each image
- **Tests:** smoke_cosign_verify_released_image, smoke_cosign_verify_released_chart, test_ci_publish_workflow_signs_images_and_chart, test_ci_publish_workflow_attaches_sbom_attestation, test_ci_publish_workflow_runs_only_on_tags
- **Depends on:** S9-T02, S9-T03

### Sprint 9 Gate
Hard stop. Release v1.1.0 only after every item is checked.
- [ ] All three tiers documented and tested
- [ ] Signed images and chart published
- [ ] Retrospective written, `sprint-9-complete` tagged; release v1.1.0

---

## Out of scope (enhancement issues)

Each item below becomes a GitHub issue with the `enhancement` label. These are deliberately not built in v1.

### OOS-01: Desktop app shell (Tauri)
- **Labels:** enhancement
- **Description:** Studio PWA covers v1; revisit for app-store distribution.
- **Acceptance criteria:**
  - [ ] Revisit after v1.1.0
- **Depends on:** none

### OOS-02: Hosted SaaS with accounts and billing
- **Labels:** enhancement
- **Description:** Local-first first; conflicts with zero telemetry until designed.
- **Acceptance criteria:**
  - [ ] Revisit after v1.1.0
- **Depends on:** none

### OOS-03: Built-in narration audio
- **Labels:** enhancement
- **Description:** mr-audio-smith narrates the web export already; deeper integration (audio in reader) is v1.1.
- **Acceptance criteria:**
  - [ ] Revisit after v1.1.0
- **Depends on:** none

### OOS-04: Animated panels and motion comics
- **Labels:** enhancement
- **Description:** Belongs with mr-motion-smith.
- **Acceptance criteria:**
  - [ ] Revisit after v1.1.0
- **Depends on:** none

### OOS-05: Multi-language lettering and translation
- **Labels:** enhancement
- **Description:** Lettering is vector text so this is feasible; needs translation UX and font coverage.
- **Acceptance criteria:**
  - [ ] Revisit after v1.1.0
- **Depends on:** none

### OOS-06: Real-time collaboration (multi-cursor)
- **Labels:** enhancement
- **Description:** LAN classroom mode gives separate workspaces; co-editing later.
- **Acceptance criteria:**
  - [ ] Revisit after v1.1.0
- **Depends on:** none

### OOS-07: Print-on-demand ordering and CMYK PDF/X
- **Labels:** enhancement
- **Description:** v1 exports RGB print PDF; CMYK conversion and PDF/X-1a need a color pipeline.
- **Acceptance criteria:**
  - [ ] Revisit after v1.1.0
- **Depends on:** none

### OOS-08: EPUB fixed-layout export
- **Labels:** enhancement
- **Description:** Web and PDF cover reading; EPUB later.
- **Acceptance criteria:**
  - [ ] Revisit after v1.1.0
- **Depends on:** none

### OOS-09: LoRA training per character
- **Labels:** enhancement
- **Description:** Reference sheets plus QA meet NFR-004; LoRA as an advanced option later.
- **Acceptance criteria:**
  - [ ] Revisit after v1.1.0
- **Depends on:** none

### OOS-10: Manga right-to-left reading order
- **Labels:** enhancement
- **Description:** Template and reader support needed.
- **Acceptance criteria:**
  - [ ] Revisit after v1.1.0
- **Depends on:** none

### OOS-11: Vector inking (SVG art)
- **Labels:** enhancement
- **Description:** Raster art is fine for v1.
- **Acceptance criteria:**
  - [ ] Revisit after v1.1.0
- **Depends on:** none

### OOS-12: Mobile native apps
- **Labels:** enhancement
- **Description:** PWA first.
- **Acceptance criteria:**
  - [ ] Revisit after v1.1.0
- **Depends on:** none

### OOS-13: Style transfer from copyrighted artists
- **Labels:** enhancement
- **Description:** Blocked by design, not deferred. This is recorded as a decision: FR-006 forbids requests that name living artists' styles, and no override exists in v1. Close as won't fix unless the originality policy changes.
- **Acceptance criteria:**
  - [ ] Revisit after v1.1.0
- **Depends on:** none

---

## Spec change log

Record every change to the spec documents made after this plan was approved.

| Date | Document | Section | Change | Reason | Issue |
|---|---|---|---|---|---|
