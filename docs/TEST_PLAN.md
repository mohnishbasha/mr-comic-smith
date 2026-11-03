# mr-comic-smith Test Plan

Version: 1.0 (spec, pre-implementation)
Date: 2026-11-02
Owner: Serverless Ventures LLC
Related documents: PRD.md (FR, NFR, and US ids), ARCHITECTURE.md (data formats, ADRs), SPRINT_PLAN.md (task ids), DESIGN.md (Studio, child mode, and reader states)

This plan lists every automated and manual test the project commits to, mapped to the functional requirements (FR-001 to FR-034) and non-functional requirements (NFR-001 to NFR-012). Sprint tasks in SPRINT_PLAN.md reference the scenario ids defined here in their **Tests** field, and every scenario below names the task that delivers it.

## Contents

1. Strategy and test pyramid
2. Coverage targets
3. Naming convention
4. Fixtures and golden files
5. Scenario tables per feature area
6. Model evaluation protocol
7. Visual regression strategy
8. Smoke checklist for staging
9. Regression policy and flake policy

---

## 1. Strategy and test pyramid

- **Unit** (pytest, vitest): prompt compiler, schema validation, arc tracking, suggestion distinctness, paginate, layout math, balloon placement geometry, SVG generation, safety denylist, event log and undo, cache keys, export option resolution.
- **Integration** (pytest -m integration): SQLite migrations, job queue with real workers, Ollama with a tiny model, ComfyUI against a CPU-friendly tiny workflow (a fixture workflow using a small SD model or a stub ComfyUI server), Chromium exports (PNG and PDF), PDF inspection with pypdf (page count, page size, embedded fonts, selectable text).
- **Contract tests**: each ImageBackend and LLMProvider adapter against recorded HTTP fixtures (respx). Cloud adapters additionally run against live APIs on a nightly job with secrets, never on PRs.
- **Visual regression**: page SVG and exported PNG compared with a perceptual diff (SSIM plus a pixel threshold) against goldens, using the mock image backend (deterministic art). Threshold 0.1 percent of pixels.
- **E2E** (Playwright): the full core loop with mock backends: create a project from the fixture duck photo, approve the sheet, pick a suggestion, render a strip, edit a balloon, approve, finalize, paginate, build a book, export PDF and web. Also the child mode flow and the reader flow.
- **Smoke**: `tests/smoke/smoke.sh` runs doctor, then the CLI `new` + `auto` + `finalize` + `pages` + `export --format pdf,web` with fake LLM, fake vision, and the mock image backend; it asserts the files exist and the PDF has the expected page count.
- **Model evaluation** (manual plus scripted, per release): three fixture stories (duck from photo, robot from text, newsletter GPU gag-a-day). Score story coherence, suggestion usefulness, character consistency (vision QA scores plus a human spot check), and lettering readability. Release is blocked if consistency NFR-004 fails or any human score averages under 4 of 5.
- **Regression**: one test per fixed bug, never deleted. Generation-quality bugs get a regression test against the deterministic layer that caused them (compiler, QA threshold, placement), never against model output.

### Test pyramid

```
                      /\
                     /  \          Evaluation (manual + scripted, per release)
                    /    \         3 fixture stories, human raters
                   /------\
                  /        \       E2E (Playwright)
                 /          \      Studio, child mode, reader, axe-core
                /------------\
               /              \    Smoke (tests/smoke/smoke.sh)
              /                \   CLI auto to PDF + web with fakes, ~2 minutes
             /------------------\
            /                    \ Visual (SSIM goldens) + Contract (respx)
           /                      \ page, strip, balloon goldens; backend adapters
          /--------------------------\
         /                            \ Integration (pytest -m integration)
        /                              \ SQLite, jobs, Chromium, Ollama tiny,
       /                                \ stub ComfyUI; GPU and cloud on schedule
      /--------------------------------- \
     /                                    \ Unit (pytest, vitest): the majority
    /                                      \ pure logic, no I/O, no network
   /----------------------------------------\

   Many, fast, cheap  <------------------>  Few, slow, expensive
```

### Test types and locations

| Type | When | Runner | Location |
|---|---|---|---|
| Unit | Pure logic, no I/O | pytest / vitest | `tests/unit/`, `web/studio/src/**/*.test.ts`, `reader/tests/` |
| Integration | DB, jobs, Chromium, Ollama tiny, stub ComfyUI | pytest -m integration | `tests/integration/` |
| Contract | Backend adapters vs recorded HTTP | pytest + respx | `tests/integration/contracts/` |
| Visual | Page, strip, balloon goldens | pytest + SSIM | `tests/visual/` |
| Smoke | CLI end to end with fakes | `tests/smoke/smoke.sh` | `tests/smoke/` |
| E2E | Studio, child mode, reader | Playwright | `tests/e2e/` |
| GPU | ComfyUI real workflows | pytest -m gpu (self-hosted) | `tests/integration/gpu/` |
| Nightly cloud | Gemini, OpenAI live | pytest -m cloud | `tests/integration/cloud/` |
| Regression | Every fixed bug | pytest / vitest | `tests/regression/` |
| Evaluation | Story, consistency, lettering quality per release | scripted + human | `docs/EVALS.md` |

### Pytest markers

| Marker | Meaning |
|---|---|
| `integration` | Needs SQLite with real workers, Chromium, Ollama tiny, or a stub ComfyUI server |
| `gpu` | Needs an NVIDIA GPU with ComfyUI; runs only on the self-hosted `gpu` runner |
| `cloud` | Needs live Gemini or OpenAI keys; runs only on the nightly job |
| `slow` | Over 10 seconds; excluded from the default local run |
| `flaky_quarantine` | Quarantined flaky test (see section 9) |

### CI mapping

| CI job | Test types it runs |
|---|---|
| lint-and-typecheck | ruff, mypy --strict, eslint, tsc, dash check, API types diff |
| unit-tests | Unit and regression, 3 OS x Python 3.12/3.13; vitest |
| coverage | Threshold script (`scripts/check-coverage.py`), Codecov upload |
| integration-tests | SQLite, jobs, Chromium, Ollama tiny model, stub ComfyUI, contract tests |
| visual-regression | SSIM goldens with fixed fonts; uploads diffs on failure |
| e2e-tests | Playwright plus axe-core with mock backends |
| check-versions | `scripts/check-versions.sh` on PRs to staging and main |
| smoke | `tests/smoke/smoke.sh` with fakes |
| gpu-integration | Self-hosted `[gpu]` runner, ComfyUI workflows (PRs to staging/main and dispatch) |
| nightly-cloud | Schedule; Gemini and OpenAI live with secrets |
| harness-smoke-tests | Staging and release only |

### Status legend (used in section 5)

| Status | Meaning |
|---|---|
| ✅ Automated | Test exists and runs in CI |
| ⚠️ Deferred | Specified, not yet implemented; implemented in the sprint of the linked task |
| ❌ Skipped | Cannot run in the default CI or by the executing agent; the reason and manual step are in the row |

All rows start as ⚠️ Deferred. A row moves to ✅ Automated in the same PR that adds the test. Rows that need a GPU runner, cloud secrets, or a person (marked in the Scenario text) move to ❌ Skipped with the reason and manual step if they cannot run in the default CI.

---

## 2. Coverage targets

Mirrors `.coverage-thresholds.toml` exactly. `scripts/check-coverage.py` fails CI when any module is under its threshold.

```toml
# .coverage-thresholds.toml
[python]
"comic_smith/story" = 90
"comic_smith/cast" = 85
"comic_smith/panels" = 85
"comic_smith/letter" = 92
"comic_smith/layout" = 90
"comic_smith/book" = 85
"comic_smith/export" = 85
"comic_smith/backends" = 80
"comic_smith/jobs" = 85
"comic_smith/events.py" = 95
"comic_smith/assets" = 90
"comic_smith/server" = 80
"comic_smith/mcp_server" = 80
"comic_smith/cli.py" = 75
overall = 85

[typescript]
"web/studio/src/stores" = 85
"web/studio/src/lettering" = 85
"web/studio/src/components" = 75
"reader/src" = 85
"integrations/pi/src" = 70
```

Notes:

- GPU-only code paths (real ComfyUI workflows) are covered by stub-server integration tests and respx-mocked adapter tests so the `backends` threshold is reachable without a GPU.
- Coverage is measured on the unit plus integration suites on ubuntu; Windows and macOS runs do not gate coverage.

---

## 3. Naming convention

```
Unit:        test_{module}_{function}_{scenario}_{expected_outcome}
Integration: it_{component}_{operation}_{scenario}
Smoke:       smoke_{feature}_{minimal_assertion}
E2E:         e2e_{user_story_id}_{scenario}
Regression:  regression_{gh_issue_number}_{what_was_broken}
Visual:      vis_{surface}_{template_or_state}
```

Scenario ids in section 5 are written in backticks and are unique across the plan. The vitest suites use the same `test_` prefix.

---

## 4. Fixtures and golden files

### Fixture layout

```
tests/fixtures/
  images/duck.jpg                 photo owned by the maintainer (rubber duck), EXIF with GPS
  images/person-consented.jpg     maintainer's own photo for people-flow tests
  images/large.heic | tiny.png | corrupt.jpg | huge-30mb.png
  narratives/duck.txt | robot.txt | gpu-gag.txt
  llm/                            recorded provider responses keyed by prompt hash
  vision/                         recorded describe and locate responses
  comfyui/                        recorded websocket and history responses
  projects/finalized-duck/        a complete project (mock art) for pages, book, export tests
  goldens/                        page SVGs, PNGs, PDF page images
  denylist/                       test entries for the originality guard
```

### Golden files

| Golden set | Produced by | Compared by | Update rule |
|---|---|---|---|
| `goldens/` page, strip, balloon, cover, and template SVGs and PNGs | Mock image backend plus bundled fonts, rendered by pinned Chromium | SSIM plus pixel threshold of 0.1 percent (`tests/visual/compare.py`) | `scripts/update-goldens.sh`; PRs that change goldens attach before and after images and explain why |
| `llm/` recorded provider responses | `make record-fixtures` against Ollama | Keyed by prompt template version and prompt hash | Re-record when a template version changes; review the diff |
| `vision/` recorded describe and locate responses | `make record-fixtures` | Keyed by image hash and template version | Same as above |
| `comfyui/` recorded websocket and history responses | Stub-server recorder | Replayed by the stub ComfyUI server | Re-record when a workflow manifest changes |

### Fixture maintenance

- Story integration tests (`it_story_*_ollama_*`) send every call through the fail-closed moderation classifier, which needs a capable model. `qwen3:0.6b` blocks harmless text, so they default to `qwen3:14b` plus `nomic-embed-text` (`COMIC_SMITH_IT_STORY_MODEL` overrides) and skip when those are not installed, including on the hosted CI runner. Only the provider-level test `it_ollama_tiny_model_returns_schema_valid_json` uses the tiny model.
- Recorded LLM, vision, and ComfyUI fixtures are keyed by prompt template version; changing a template requires re-recording (`make record-fixtures`, needs Ollama) and reviewing diffs.
- Goldens render with bundled fonts only and a pinned Chromium version from Playwright.
- `images/duck.jpg` and `images/person-consented.jpg` are the maintainer's own photos; never use third-party photos. The duck photo carries EXIF GPS on purpose to test stripping.
- `tests/fixtures/images/*` and `tests/fixtures/goldens/*` are tracked in Git LFS (see `.gitattributes`).
- The mock backend output is byte-identical across platforms, so goldens built on it are stable; real-backend output is never compared byte for byte.

---

## 5. Scenario tables per feature area

Conventions: ids follow section 3. Types are Unit, Integration, Integration (GPU), Integration (cloud), Smoke, E2E, Visual, Regression (none exist yet), and Evaluation. The Task column links each scenario to the SPRINT_PLAN task that delivers it. Rows marked manual or GPU in the Scenario text cannot run in the default CI and become ❌ Skipped with a manual step if they stay out of reach.


### 5.1 Scaffold, config, and doctor (PRD FR-030, FR-031, US-022)

| ID | Scenario | Type | Task | Status |
|---|---|---|---|---|
| `test_docs_spec_files_all_five_present` | PRD, ARCHITECTURE, DESIGN, SPRINT_PLAN, TEST_PLAN exist under docs/ | Unit | `S0-T01` | ✅ Automated |
| `test_docs_required_sections_present_in_each_spec` | Each spec has every required section heading | Unit | `S0-T01` | ✅ Automated |
| `test_docs_every_fr_has_acceptance_criteria` | Every FR block in PRD.md carries an AC line | Unit | `S0-T01` | ✅ Automated |
| `test_docs_every_us_maps_to_at_least_one_fr` | Each US-nnn is referenced by at least one FR or task | Unit | `S0-T01` | ✅ Automated |
| `test_docs_no_em_or_en_dash_in_committed_files` | Scan of tracked text files finds no U+2014 or U+2013 | Unit | `S0-T01` | ✅ Automated |
| `test_cli_version_prints_pyproject_version` | `--version` output equals the pyproject version | Unit | `S0-T02` | ✅ Automated |
| `smoke_cli_version_exits_zero` | `mr-comic-smith --version` exits 0 | Smoke | `S0-T02` | ✅ Automated |
| `test_packaging_base_install_does_not_pull_torch` | Resolved base dependency set contains no torch | Unit | `S0-T02` | ✅ Automated |
| `test_packaging_optional_extras_declared` | All eight dependency groups are declared | Unit | `S0-T02` | ✅ Automated |
| `test_packaging_python_range_is_312_to_313` | requires-python is >=3.12,<3.14 | Unit | `S0-T02` | ✅ Automated |
| `it_packaging_uv_sync_all_extras_clean_env` | uv sync --all-extras --dev succeeds in a clean environment | Integration | `S0-T02` | ⚠️ Deferred |
| `test_repo_gitignore_contains_required_groups` | Every required ignore pattern is present | Unit | `S0-T03` | ✅ Automated |
| `test_repo_gitignore_fixtures_not_ignored` | Fixture project.db is not ignored | Unit | `S0-T03` | ✅ Automated |
| `test_repo_gitignore_user_projects_ignored` | projects/ and *.db are ignored | Unit | `S0-T03` | ✅ Automated |
| `test_repo_gitattributes_lfs_patterns_declared` | LFS patterns for images, goldens, and fonts | Unit | `S0-T03` | ✅ Automated |
| `test_repo_license_names_serverless_ventures_2026` | LICENSE holder and year | Unit | `S0-T03` | ✅ Automated |
| `test_repo_hygiene_files_all_present` | All hygiene files exist at the repo root | Unit | `S0-T03` | ✅ Automated |
| `test_lint_ruff_rules_configured_as_specified` | pyproject ruff select list matches the specified rule set | Unit | `S0-T04` | ✅ Automated |
| `test_lint_mypy_strict_enabled` | mypy strict mode is on | Unit | `S0-T04` | ✅ Automated |
| `test_lint_em_dash_hook_rejects_u2014` | Hook exits non-zero on an em dash | Unit | `S0-T04` | ✅ Automated |
| `test_lint_en_dash_hook_rejects_u2013` | Hook exits non-zero on an en dash | Unit | `S0-T04` | ✅ Automated |
| `test_lint_makefile_targets_all_defined` | All twelve Makefile targets exist | Unit | `S0-T04` | ✅ Automated |
| `smoke_make_lint_typecheck_exit_zero` | `make lint typecheck` is green on the skeleton | Smoke | `S0-T04` | ⚠️ Deferred |
| `test_harness_coverage_script_fails_under_threshold` | check-coverage.py exits 1 when a module is below target | Unit | `S0-T05` | ✅ Automated |
| `test_harness_coverage_script_passes_at_threshold` | check-coverage.py exits 0 at exactly the target | Unit | `S0-T05` | ✅ Automated |
| `test_harness_thresholds_toml_matches_test_plan` | TOML in the repo equals the block in TEST_PLAN section 2 | Unit | `S0-T05` | ✅ Automated |
| `test_visual_compare_identical_images_pass` | Identical PNGs pass | Unit | `S0-T05` | ✅ Automated |
| `test_visual_compare_over_threshold_fails` | More than 0.1 percent differing pixels fails | Unit | `S0-T05` | ✅ Automated |
| `test_visual_compare_ssim_detects_shifted_glyph` | A one-pixel glyph shift is detected by SSIM | Unit | `S0-T05` | ✅ Automated |
| `smoke_make_test_and_visual_run` | `make test` and `make visual` execute on the skeleton | Smoke | `S0-T05` | ⚠️ Deferred |
| `test_ci_workflow_declares_all_required_jobs` | ci.yml lists every job from Appendix J | Unit | `S0-T09` | ✅ Automated |
| `test_ci_concurrency_cancels_superseded_runs` | concurrency group with cancel-in-progress is set | Unit | `S0-T09` | ✅ Automated |
| `test_ci_dependabot_covers_uv_npm_actions_docker` | dependabot.yml has all four ecosystems | Unit | `S0-T09` | ✅ Automated |
| `test_ci_gpu_integration_targets_self_hosted_gpu_label` | gpu-integration runs-on includes self-hosted and gpu | Unit | `S0-T09` | ✅ Automated |
| `smoke_ci_skeleton_all_jobs_green` | Every job passes on the skeleton commit | Smoke | `S0-T09` | ⚠️ Deferred |
| `test_scripts_check_versions_mismatch_exits_one_naming_file` | Mismatch exits 1 with the offending file | Unit | `S0-T10` | ✅ Automated |
| `test_scripts_check_versions_match_exits_zero` | Aligned versions exit 0 | Unit | `S0-T10` | ✅ Automated |
| `test_scripts_bump_version_updates_all_files` | bump-version rewrites every versioned file | Unit | `S0-T10` | ✅ Automated |
| `test_scripts_extract_changelog_prints_only_requested_section` | Only the requested version section is printed | Unit | `S0-T10` | ✅ Automated |
| `test_scripts_extract_changelog_missing_section_fails` | Unknown version exits non-zero | Unit | `S0-T10` | ✅ Automated |
| `test_agent_files_all_present` | AGENTS.md, CLAUDE.md, SKILLS.md, SOUL.md exist | Unit | `S0-T11` | ✅ Automated |
| `test_agent_claude_md_starts_with_import_agents_md` | First line of CLAUDE.md is the import | Unit | `S0-T11` | ✅ Automated |
| `test_agent_soul_md_has_at_least_six_hard_constraints` | SOUL.md constraint count is 6 or more | Unit | `S0-T11` | ✅ Automated |
| `test_agent_soul_md_contains_no_commands_or_paths` | No code fences or filesystem paths in SOUL.md | Unit | `S0-T11` | ✅ Automated |
| `test_agent_skills_run_tests_check_types_make_fixture_comic_exist` | Three skill folders with SKILL.md | Unit | `S0-T11` | ✅ Automated |
| `smoke_agent_skills_run_green` | Each skill script exits 0 | Smoke | `S0-T11` | ⚠️ Deferred |
| `test_config_precedence_flags_over_env` | Flag beats env | Unit | `S0-T12` | ✅ Automated |
| `test_config_precedence_env_over_file` | Env beats file | Unit | `S0-T12` | ✅ Automated |
| `test_config_precedence_file_over_defaults` | File beats defaults | Unit | `S0-T12` | ✅ Automated |
| `test_config_env_prefix_comic_smith` | Only COMIC_SMITH_ variables are read | Unit | `S0-T12` | ✅ Automated |
| `test_doctor_check_registry_runs_all_checks` | Every registered check runs and reports | Unit | `S0-T12` | ✅ Automated |
| `test_doctor_json_output_parses` | --json output is valid JSON with check ids | Unit | `S0-T12` | ✅ Automated |
| `test_doctor_required_failure_exits_three` | Required failure exits 3 | Unit | `S0-T12` | ✅ Automated |
| `test_doctor_missing_chromium_reports_fix_hint` | Missing Chromium prints the install command | Unit | `S0-T12` | ✅ Automated |
| `test_doctor_unwritable_data_dir_fails` | Unwritable data dir is a required failure | Unit | `S0-T12` | ✅ Automated |

### 5.2 Database and assets (PRD FR-001, NFR-006)

| ID | Scenario | Type | Task | Status |
|---|---|---|---|---|
| `it_db_migrations_up_and_down_roundtrip` | Upgrade to head then downgrade to base succeeds | Integration | `S0-T06` | ✅ Automated |
| `it_db_project_open_creates_new_project` | Project.open on an empty folder creates project.db and assets/ | Integration | `S0-T06` | ✅ Automated |
| `it_db_project_open_migrates_old_schema` | Project.open on an older schema migrates it | Integration | `S0-T06` | ✅ Automated |
| `it_db_wal_concurrent_reader_during_write` | A reader gets a consistent snapshot while a writer commits | Integration | `S0-T06` | ✅ Automated |
| `it_db_foreign_keys_enforced` | Orphan insert raises an integrity error | Integration | `S0-T06` | ✅ Automated |
| `test_assets_store_write_atomic_temp_then_rename` | Write goes through a temp file then rename | Unit | `S0-T06` | ✅ Automated |
| `test_assets_store_write_idempotent_same_sha` | Writing the same bytes twice stores one object | Unit | `S0-T06` | ✅ Automated |
| `test_assets_store_crash_mid_write_leaves_no_partial_file` | Simulated crash leaves no partial object | Unit | `S0-T06` | ✅ Automated |

### 5.3 Events and undo (PRD FR-033, US-021)

| ID | Scenario | Type | Task | Status |
|---|---|---|---|---|
| `test_events_apply_records_actor_and_inverse` | Applied event stores actor and inverse payload | Unit | `S0-T07` | ✅ Automated |
| `test_events_undo_redo_roundtrip_lettering_edit` | Undo then redo of a lettering edit restores state | Unit | `S0-T07` | ✅ Automated |
| `test_events_property_random_apply_undo_redo_restores_state` | Hypothesis: random sequences return to identical state | Unit | `S0-T07` | ✅ Automated |
| `test_events_redo_cleared_after_new_apply` | A new apply after undo drops the redo stack | Unit | `S0-T07` | ✅ Automated |
| `test_events_history_survives_restart` | Reopened project replays the same history | Unit | `S0-T07` | ✅ Automated |
| `test_events_service_mutations_all_go_through_apply` | Import-linter or grep rule: no direct writes outside events | Unit | `S0-T07` | ✅ Automated |

### 5.4 LLM providers (PRD FR-013, ADR-012)

| ID | Scenario | Type | Task | Status |
|---|---|---|---|---|
| `test_llm_ollama_chat_request_sends_schema_in_format` | Ollama /api/chat body carries the schema in format (respx) | Unit | `S1-T01` | ✅ Automated |
| `test_llm_anthropic_provider_uses_tool_use_for_json` | Anthropic call uses tool-use or structured output (stubbed SDK) | Unit | `S1-T01` | ✅ Automated |
| `test_llm_openai_compat_response_format_json_schema` | response_format carries the schema | Unit | `S1-T01` | ✅ Automated |
| `test_llm_fake_provider_replays_by_prompt_hash` | FakeProvider returns the recorded response | Unit | `S1-T01` | ✅ Automated |
| `test_llm_fake_provider_unknown_hash_names_record_command` | Missing recording names the hash and `make record-fixtures` | Unit | `S1-T01` | ✅ Automated |
| `test_llm_provider_string_parsing_all_three_formats` | ollama, anthropic, and openai_compat strings parse | Unit | `S1-T01` | ✅ Automated |
| `test_llm_complete_json_invalid_output_one_corrective_retry` | One retry with validation errors in the prompt | Unit | `S1-T01` | ✅ Automated |
| `test_llm_complete_json_second_failure_raises` | Second failure raises a typed error | Unit | `S1-T01` | ✅ Automated |
| `test_llm_retry_backoff_on_5xx` | 5xx responses retry with backoff | Unit | `S1-T01` | ✅ Automated |
| `test_llm_timeout_raises_provider_timeout` | Timeout maps to ComicSmithError | Unit | `S1-T01` | ✅ Automated |
| `test_llm_token_usage_recorded_per_call` | Usage is stored with the call record | Unit | `S1-T01` | ✅ Automated |
| `it_ollama_tiny_model_returns_schema_valid_json` | Real Ollama tiny model returns valid JSON | Integration | `S1-T01` | ✅ Automated |

### 5.5 Schemas (PRD ADR-007)

| ID | Scenario | Type | Task | Status |
|---|---|---|---|---|
| `test_schemas_models_roundtrip_all_five_documents` | Model to JSON to model is identity | Unit | `S1-T02` | ✅ Automated |
| `test_schemas_export_json_schemas_are_current` | schemas/ matches the pydantic models | Unit | `S1-T02` | ✅ Automated |
| `test_schemas_fixture_documents_validate` | Fixture documents validate against the schemas | Unit | `S1-T02` | ✅ Automated |
| `test_schemas_panel_spec_invalid_shot_rejected` | Unknown shot value fails validation | Unit | `S1-T02` | ✅ Automated |
| `test_schemas_beat_requires_arc_stage` | Beat without arc stage fails validation | Unit | `S1-T02` | ✅ Automated |
| `test_schemas_continuity_report_issue_kinds_enum` | Issue kind outside the enum fails | Unit | `S1-T02` | ✅ Automated |

### 5.6 Story bible and arc (PRD FR-009, FR-010, US-002)

| ID | Scenario | Type | Task | Status |
|---|---|---|---|---|
| `test_story_bible_target_strips_out_of_range_rejected` | Targets of 0 and 41 are rejected | Unit | `S1-T03` | ✅ Automated |
| `test_story_bible_generate_from_narrative_fake_provider_validates` | FakeProvider bible validates against the schema | Unit | `S1-T03` | ✅ Automated |
| `test_story_bible_audience_values_enum_with_all_ages_default` | Audience enum and default | Unit | `S1-T03` | ✅ Automated |
| `test_story_bible_edit_creates_new_version` | Each edit increments the bible version | Unit | `S1-T03` | ✅ Automated |
| `test_story_bible_edit_is_undoable_event` | Edit is an event and undo restores the prior version | Unit | `S1-T03` | ✅ Automated |
| `test_story_arc_templates_five_templates_load_with_stages` | Five templates with stages load | Unit | `S1-T03` | ✅ Automated |
| `test_story_bible_default_arc_for_kids_is_problem_try_try_succeed` | Kids audiences default to problem-try-try-succeed | Unit | `S1-T03` | ✅ Automated |
| `test_story_prompts_bible_template_version_recorded` | Prompt template version is stored with the bible | Unit | `S1-T03` | ✅ Automated |
| `it_story_bible_ollama_generates_valid_bible` | Real Ollama run yields a valid bible | Integration | `S1-T03` | ✅ Automated |
| `test_story_arc_progress_updates_after_approval` | Approval advances progress | Unit | `S1-T04` | ✅ Automated |
| `test_story_arc_progress_computed_from_stage_index_and_target` | Progress formula | Unit | `S1-T04` | ✅ Automated |
| `test_story_arc_threads_opened_and_closed_from_diff` | Diff opens and closes threads | Unit | `S1-T04` | ✅ Automated |
| `test_story_arc_diff_unknown_thread_close_ignored` | Closing an unknown thread is ignored with a warning | Unit | `S1-T04` | ✅ Automated |
| `test_story_arc_gag_a_day_has_no_stage_progress` | gag-a-day has no arc progress | Unit | `S1-T04` | ✅ Automated |
| `test_story_arc_each_strip_tagged_with_stage` | Strip record stores its stage | Unit | `S1-T04` | ✅ Automated |
| `test_story_arc_progress_clamped_0_to_100` | Progress never leaves 0 to 100 | Unit | `S1-T04` | ✅ Automated |

### 5.7 Plot suggestions, custom beats, and thumbnails (PRD FR-011, FR-012, US-004, US-005, US-009)

| ID | Scenario | Type | Task | Status |
|---|---|---|---|---|
| `test_story_suggest_returns_three_distinct_intents` | continue, twist, steer returned | Unit | `S1-T05` | ✅ Automated |
| `test_story_suggest_similar_options_regenerated_once` | Similar pair triggers one regeneration | Unit | `S1-T05` | ✅ Automated |
| `test_story_suggest_final_stage_includes_end_here` | Final stage adds end-here | Unit | `S1-T05` | ✅ Automated |
| `test_story_suggest_target_length_reached_includes_end_here` | Target length adds end-here | Unit | `S1-T05` | ✅ Automated |
| `test_story_suggest_option_has_required_fields` | Beat, description, stage, characters, thumbnail prompt | Unit | `S1-T05` | ✅ Automated |
| `test_story_suggest_context_includes_bible_last_three_summaries_threads` | Prompt context contents | Unit | `S1-T05` | ✅ Automated |
| `test_story_suggest_still_similar_after_regen_returns_with_warning` | No infinite regeneration | Unit | `S1-T05` | ✅ Automated |
| `test_story_suggest_embeddings_cosine_threshold_085` | Threshold boundary at 0.85 | Unit | `S1-T05` | ✅ Automated |
| `it_story_suggest_ollama_distinct_options` | Real Ollama yields distinct options | Integration | `S1-T05` | ✅ Automated |
| `it_story_suggest_local_model_within_10s` | Local 14B suggestions in under 10 s (GPU runner) | Integration (GPU) | `S1-T05` | ✅ Automated |
| `test_story_beat_normalize_free_text_to_beat_structure` | Free text becomes a valid beat | Unit | `S1-T06` | ✅ Automated |
| `test_story_beat_normalized_returned_for_confirmation` | Result is returned unconfirmed | Unit | `S1-T06` | ✅ Automated |
| `test_story_beat_edit_suggestion_keeps_other_fields` | Edited suggestion retains other fields | Unit | `S1-T06` | ✅ Automated |
| `test_story_beat_empty_text_rejected` | Empty text is rejected | Unit | `S1-T06` | ✅ Automated |
| `test_story_thumbnail_job_low_priority_small_size` | Job parameters | Unit | `S3-T09` | ⚠️ Deferred |
| `test_story_thumbnail_skipped_when_estimate_exceeds_budget` | Budget gate | Unit | `S3-T09` | ⚠️ Deferred |
| `test_story_thumbnail_placeholder_when_skipped` | Placeholder used | Unit | `S3-T09` | ⚠️ Deferred |
| `test_story_suggest_does_not_wait_on_thumbnails` | Suggestions return first | Unit | `S3-T09` | ⚠️ Deferred |
| `it_story_thumbnail_fills_in_as_arrives` | Progressive fill-in | Integration | `S3-T09` | ⚠️ Deferred |

### 5.8 Strip writer (PRD FR-013, FR-014, US-006)

| ID | Scenario | Type | Task | Status |
|---|---|---|---|---|
| `test_story_writer_unknown_speaker_rejected` | Speaker outside the cast fails | Unit | `S1-T07` | ✅ Automated |
| `test_story_writer_kids_word_limit_enforced` | 11-word balloon fails for kids-5-8 | Unit | `S1-T07` | ✅ Automated |
| `test_story_writer_kids_max_two_balloons_per_panel` | Third balloon fails for kids-5-8 | Unit | `S1-T07` | ✅ Automated |
| `test_story_writer_total_words_per_strip_limit` | Per-audience strip word cap | Unit | `S1-T07` | ✅ Automated |
| `test_story_writer_shot_variety_no_three_consecutive_same_shot` | Three equal shots in a row fail | Unit | `S1-T07` | ✅ Automated |
| `test_story_writer_panel_count_default_four_range_one_to_six` | Default and range | Unit | `S1-T07` | ✅ Automated |
| `test_story_writer_invalid_output_one_corrective_retry` | One retry then success or typed error | Unit | `S1-T07` | ✅ Automated |
| `test_story_writer_balloon_space_hint_present_per_panel` | Every panel has a balloon_space hint | Unit | `S1-T07` | ✅ Automated |
| `test_story_writer_continuity_notes_from_previous_strips` | Prior strips feed continuity notes | Unit | `S1-T07` | ✅ Automated |
| `it_story_writer_ollama_valid_panel_specs` | Real Ollama yields valid Panel Specs | Integration | `S1-T07` | ✅ Automated |

### 5.9 Moderation and audience safety (PRD FR-028, US-019, NFR-012)

| ID | Scenario | Type | Task | Status |
|---|---|---|---|---|
| `test_safety_moderation_blocked_bible_raises_safety_blocked` | Blocked bible raises safety_blocked | Unit | `S1-T08` | ✅ Automated |
| `test_safety_moderation_verdict_strict_json_schema` | Verdict must match the schema | Unit | `S1-T08` | ✅ Automated |
| `test_safety_moderation_runs_on_suggestions_beats_scripts` | All four text artifacts are checked | Unit | `S1-T08` | ✅ Automated |
| `test_safety_audience_rules_in_every_system_prompt` | Every story prompt template includes audience rules | Unit | `S1-T08` | ✅ Automated |
| `test_safety_denylist_copyrighted_name_blocked_in_beat` | Denylisted name in a beat is blocked | Unit | `S1-T08` | ✅ Automated |
| `test_safety_blocked_error_explains_in_plain_words` | Message names the rule in plain words | Unit | `S1-T08` | ✅ Automated |
| `test_safety_denylist_loaded_from_yaml_data_file` | Denylist is data, not code | Unit | `S1-T08` | ✅ Automated |
| `test_safety_moderation_unparseable_verdict_fails_closed` | Bad verdict blocks | Unit | `S1-T08` | ✅ Automated |
| `test_safety_audience_kids_blocks_violent_beat` | Violent beat blocked for kids audience | Unit | `S1-T08` | ✅ Automated |
| `test_safety_image_audience_failing_take_hidden` | Hidden take | Unit | `S3-T13` | ⚠️ Deferred |
| `test_safety_image_audience_failing_take_auto_retaken` | Auto retake | Unit | `S3-T13` | ⚠️ Deferred |
| `test_safety_image_audience_verdict_per_take_cached` | Verdict cache | Unit | `S3-T13` | ⚠️ Deferred |
| `test_safety_image_audience_verdict_respects_project_audience` | Audience-specific verdict | Unit | `S3-T13` | ⚠️ Deferred |
| `test_safety_image_audience_all_ages_blocks_gore_fixture` | Gore fixture blocked | Unit | `S3-T13` | ⚠️ Deferred |
| `test_safety_image_audience_retake_exhausted_surfaces_plain_words_message` | Plain-words message | Unit | `S3-T13` | ⚠️ Deferred |

### 5.10 Branching and finalize (PRD FR-021, FR-022, US-010, US-020)

| ID | Scenario | Type | Task | Status |
|---|---|---|---|---|
| `test_story_branch_create_from_approved_strip` | Branch forks at an approved strip | Unit | `S1-T09` | ✅ Automated |
| `test_story_branch_strip_listing_follows_parent_chain_to_fork` | Listing includes parent strips up to the fork | Unit | `S1-T09` | ✅ Automated |
| `test_story_branch_switch_changes_active_branch` | Switch updates the active branch | Unit | `S1-T09` | ✅ Automated |
| `test_story_branch_rename` | Rename persists | Unit | `S1-T09` | ✅ Automated |
| `test_story_branch_delete_keeps_shared_strips` | Delete keeps strips used by other branches | Unit | `S1-T09` | ✅ Automated |
| `test_story_branch_delete_active_branch_rejected` | Active branch cannot be deleted | Unit | `S1-T09` | ✅ Automated |
| `test_story_branch_create_from_unapproved_strip_rejected` | Fork needs an approved strip | Unit | `S1-T09` | ✅ Automated |
| `test_story_finalize_continuity_report_structure` | Report has the four issue kinds | Unit | `S1-T10` | ✅ Automated |
| `test_story_finalize_returns_three_titles_and_blurb` | Three titles and a one-line blurb | Unit | `S1-T10` | ✅ Automated |
| `test_story_finalize_locks_story_read_only` | Locked story rejects edits | Unit | `S1-T10` | ✅ Automated |
| `test_story_finalize_anyway_with_open_issues_allowed` | Open issues do not block finalize | Unit | `S1-T10` | ✅ Automated |
| `test_story_finalize_reopen_creates_new_version` | Reopen increments the story version | Unit | `S1-T10` | ✅ Automated |
| `test_story_finalize_edit_locked_story_rejected` | Edit on locked story raises | Unit | `S1-T10` | ✅ Automated |
| `test_story_finalize_report_jump_to_strip_ids` | Each issue carries strip ids | Unit | `S1-T10` | ✅ Automated |

### 5.11 Story CLI (PRD FR-030, FR-026, US-016)

| ID | Scenario | Type | Task | Status |
|---|---|---|---|---|
| `smoke_cli_new_auto_finalize_scripted_story` | new, auto --until-target, finalize with FakeProvider | Smoke | `S1-T11` | ✅ Automated |
| `test_cli_new_narrative_creates_project_json_output` | new --narrative --json prints the project id | Unit | `S1-T11` | ✅ Automated |
| `test_cli_bible_show_and_edit` | bible show and edit round trip | Unit | `S1-T11` | ✅ Automated |
| `test_cli_suggest_json_returns_three_options` | suggest --json has three options | Unit | `S1-T11` | ✅ Automated |
| `test_cli_strip_pick_writes_script_only` | strip --pick writes a script without images | Unit | `S1-T11` | ✅ Automated |
| `test_cli_strip_beat_free_text` | strip --beat normalizes free text | Unit | `S1-T11` | ✅ Automated |
| `test_cli_branch_create_switch_list` | branch subcommands | Unit | `S1-T11` | ✅ Automated |
| `test_cli_auto_until_target_policy_balanced` | auto stops at the target | Unit | `S1-T11` | ✅ Automated |
| `test_cli_all_story_commands_support_json_flag` | Every command accepts --json | Unit | `S1-T11` | ✅ Automated |

### 5.12 Asset ingest (PRD FR-002)

| ID | Scenario | Type | Task | Status |
|---|---|---|---|---|
| `test_assets_ingest_exif_gps_stripped` | Uploads lose location data | Unit | `S2-T01` | ⚠️ Deferred |
| `test_assets_ingest_heic_converted_to_png` | HEIC support | Unit | `S2-T01` | ⚠️ Deferred |
| `test_assets_ingest_type_sniffed_not_extension` | A PNG named .jpg is detected as PNG | Unit | `S2-T01` | ⚠️ Deferred |
| `test_assets_ingest_corrupt_jpg_rejected_clear_error` | corrupt.jpg raises a clear error | Unit | `S2-T01` | ⚠️ Deferred |
| `test_assets_ingest_huge_30mb_png_rejected_over_20mb_limit` | huge-30mb.png rejected | Unit | `S2-T01` | ⚠️ Deferred |
| `test_assets_ingest_downscales_over_4096_long_edge` | Long edge capped at 4096 | Unit | `S2-T01` | ⚠️ Deferred |
| `test_assets_ingest_orientation_fixed_from_exif` | EXIF orientation applied then stripped | Unit | `S2-T01` | ⚠️ Deferred |
| `test_assets_ingest_stored_by_sha256` | Stored under its SHA-256 | Unit | `S2-T01` | ⚠️ Deferred |
| `test_assets_ingest_fifth_reference_rejected` | More than four references rejected | Unit | `S2-T01` | ⚠️ Deferred |
| `test_assets_ingest_narrative_over_5000_chars_rejected` | Narrative limit enforced | Unit | `S2-T01` | ⚠️ Deferred |

### 5.13 Vision providers (PRD FR-003, FR-017)

| ID | Scenario | Type | Task | Status |
|---|---|---|---|---|
| `test_vision_describe_returns_structured_json_with_palette_hex` | describe returns subject, palette hex list, features, accessories | Unit | `S2-T02` | ⚠️ Deferred |
| `test_vision_locate_returns_normalized_boxes` | Boxes are in 0 to 1 coordinates | Unit | `S2-T02` | ⚠️ Deferred |
| `test_vision_locate_box_outside_unit_range_rejected` | Out-of-range box fails validation | Unit | `S2-T02` | ⚠️ Deferred |
| `test_vision_ollama_provider_request_shape` | Ollama request carries image and schema (respx) | Unit | `S2-T02` | ⚠️ Deferred |
| `test_vision_anthropic_provider_image_block` | Anthropic image content block (stubbed SDK) | Unit | `S2-T02` | ⚠️ Deferred |
| `test_vision_openai_compat_provider_request_shape` | OpenAI-compatible request shape (respx) | Unit | `S2-T02` | ⚠️ Deferred |
| `test_vision_fake_provider_replays_recorded_responses` | Fixture replay by image hash | Unit | `S2-T02` | ⚠️ Deferred |
| `test_vision_doctor_reachability_check_hint` | Unreachable provider reports a fix hint | Unit | `S2-T02` | ⚠️ Deferred |
| `it_vision_ollama_locate_duck_fixture_valid_box` | Real Ollama locates the duck | Integration | `S2-T02` | ⚠️ Deferred |

### 5.14 Reference understanding and people guard (PRD FR-003, FR-007)

| ID | Scenario | Type | Task | Status |
|---|---|---|---|---|
| `test_cast_reference_person_detected_requires_attestation` | People guard | Unit | `S2-T03` | ⚠️ Deferred |
| `test_cast_reference_describe_stored_as_editable_json` | Description editable per field | Unit | `S2-T03` | ⚠️ Deferred |
| `test_cast_reference_attestation_stored_with_character` | Attestation record persisted | Unit | `S2-T03` | ⚠️ Deferred |
| `test_cast_reference_photoreal_style_disabled_for_person_derived` | Photoreal presets rejected | Unit | `S2-T03` | ⚠️ Deferred |
| `test_cast_reference_public_figure_request_declined` | Public figure request declined | Unit | `S2-T03` | ⚠️ Deferred |
| `test_cast_reference_sheet_generation_blocked_until_attested` | Sheet job refuses without attestation | Unit | `S2-T03` | ⚠️ Deferred |
| `test_cast_reference_no_person_duck_fixture_no_attestation_needed` | Duck photo needs no attestation | Unit | `S2-T03` | ⚠️ Deferred |

### 5.15 Image backends: mock and registry (PRD ADR-005)

| ID | Scenario | Type | Task | Status |
|---|---|---|---|---|
| `test_backends_mock_output_byte_identical_for_same_request` | Same request, same bytes | Unit | `S2-T04` | ⚠️ Deferred |
| `test_backends_mock_respects_size_and_seed` | Size and seed change the output as expected | Unit | `S2-T04` | ⚠️ Deferred |
| `test_backends_mock_draws_labeled_shape_per_character` | One labeled shape per character | Unit | `S2-T04` | ⚠️ Deferred |
| `test_backends_mock_simulated_failures_configurable` | Failure rate is configurable and deterministic by seed | Unit | `S2-T04` | ⚠️ Deferred |
| `test_backends_mock_emits_progress_events` | Progress events emitted | Unit | `S2-T04` | ⚠️ Deferred |
| `test_backends_registry_lists_capabilities` | Registry reports capabilities | Unit | `S2-T04` | ⚠️ Deferred |
| `test_backends_registry_unknown_backend_raises` | Unknown id raises a typed error | Unit | `S2-T04` | ⚠️ Deferred |
| `test_backends_capabilities_max_reference_images_exposed` | max_reference_images is exposed | Unit | `S2-T04` | ⚠️ Deferred |

### 5.16 Image backends: ComfyUI (PRD ADR-005, ADR-006, NFR-011)

| ID | Scenario | Type | Task | Status |
|---|---|---|---|---|
| `it_comfyui_stub_server_queue_and_fetch_output` | Stub server: queue, poll history, fetch image | Integration | `S2-T05` | ⚠️ Deferred |
| `it_comfyui_stub_websocket_progress_events_streamed` | Progress events forwarded from the websocket | Integration | `S2-T05` | ⚠️ Deferred |
| `it_comfyui_cancel_interrupts_running_prompt` | Cancel calls interrupt | Integration | `S2-T05` | ⚠️ Deferred |
| `it_comfyui_reference_upload_returns_server_filename` | Reference upload maps to a server filename | Integration | `S2-T05` | ⚠️ Deferred |
| `test_comfyui_workflow_slots_filled_prompt_negative_size_seed` | Named slots are substituted | Unit | `S2-T05` | ⚠️ Deferred |
| `test_comfyui_workflow_templates_all_three_validate` | Three templates pass the manifest schema | Unit | `S2-T05` | ⚠️ Deferred |
| `test_comfyui_workflow_manifest_declares_models_with_sha256` | Manifest lists URLs and SHA-256 | Unit | `S2-T05` | ⚠️ Deferred |
| `test_comfyui_flux_kontext_requires_license_acceptance` | Non-commercial gate blocks until opt-in | Unit | `S2-T05` | ⚠️ Deferred |
| `test_comfyui_models_pull_verifies_checksum` | Checksum verified after download | Unit | `S2-T05` | ⚠️ Deferred |
| `test_comfyui_models_pull_corrupt_download_rejected` | Mismatched checksum is rejected | Unit | `S2-T05` | ⚠️ Deferred |
| `it_comfyui_qwen_edit_workflow_returns_image` | Local backend returns an image from the qwen-image-edit workflow (GPU runner) | Integration (GPU) | `S2-T05` | ⚠️ Deferred |
| `it_comfyui_gpu_two_reference_panel_renders` | Panel with two references renders on the GPU runner | Integration (GPU) | `S2-T05` | ⚠️ Deferred |

### 5.17 Image backends: Gemini (PRD ADR-005)

| ID | Scenario | Type | Task | Status |
|---|---|---|---|---|
| `test_gemini_contract_request_includes_reference_images` | Reference images in the request (respx) | Unit | `S2-T06` | ⚠️ Deferred |
| `test_gemini_contract_response_decoded_to_generated_image` | Response decoded to GeneratedImage | Unit | `S2-T06` | ⚠️ Deferred |
| `test_gemini_key_from_env_or_keyring` | Key lookup order | Unit | `S2-T06` | ⚠️ Deferred |
| `test_gemini_missing_key_raises_with_hint` | Hint names the env var | Unit | `S2-T06` | ⚠️ Deferred |
| `test_gemini_capabilities_declare_reference_limit` | max_reference_images declared | Unit | `S2-T06` | ⚠️ Deferred |
| `test_gemini_backend_reports_cloud_badge` | cloud flag true | Unit | `S2-T06` | ⚠️ Deferred |
| `test_gemini_safety_block_response_maps_to_error` | Provider block maps to ComicSmithError | Unit | `S2-T06` | ⚠️ Deferred |
| `it_gemini_nightly_live_generates_panel` | Live generation behind secret (nightly) | Integration (cloud) | `S2-T06` | ⚠️ Deferred |

### 5.18 Image backends: OpenAI (PRD ADR-005)

| ID | Scenario | Type | Task | Status |
|---|---|---|---|---|
| `test_openai_images_contract_generate_request_shape` | Generate request shape (respx) | Unit | `S2-T07` | ⚠️ Deferred |
| `test_openai_images_contract_edit_with_reference_and_mask` | Edit request carries reference and mask | Unit | `S2-T07` | ⚠️ Deferred |
| `test_openai_images_key_missing_raises_with_hint` | Missing key hint | Unit | `S2-T07` | ⚠️ Deferred |
| `test_openai_images_capabilities_declare_edit_support` | supports_edit true | Unit | `S2-T07` | ⚠️ Deferred |
| `test_openai_images_content_policy_error_mapped` | Policy refusal maps to a typed error | Unit | `S2-T07` | ⚠️ Deferred |
| `test_openai_images_reports_cloud_badge` | cloud flag true | Unit | `S2-T07` | ⚠️ Deferred |
| `it_openai_images_nightly_live_generates_panel` | Live generation behind secret (nightly) | Integration (cloud) | `S2-T07` | ⚠️ Deferred |

### 5.19 Styles (PRD FR-008, US-018)

| ID | Scenario | Type | Task | Status |
|---|---|---|---|---|
| `test_style_presets_six_builtin_validate` | Six built-in presets validate | Unit | `S2-T08` | ⚠️ Deferred |
| `test_style_preset_has_tokens_negative_palette_line_weight` | Required fields present | Unit | `S2-T08` | ⚠️ Deferred |
| `test_style_preset_backend_override_applied` | Per-backend override wins | Unit | `S2-T08` | ⚠️ Deferred |
| `test_style_custom_preset_from_text_and_two_refs` | Custom preset created | Unit | `S2-T08` | ⚠️ Deferred |
| `test_style_custom_preset_three_refs_rejected` | More than two refs rejected | Unit | `S2-T08` | ⚠️ Deferred |
| `test_style_preset_photoreal_flag_declared` | Photoreal presets are flagged for the people guard | Unit | `S2-T08` | ⚠️ Deferred |
| `it_style_preview_grid_job_renders_with_mock_backend` | Preview grid job completes | Integration | `S2-T08` | ⚠️ Deferred |

### 5.20 Character sheets (PRD FR-004, FR-005, US-001)

| ID | Scenario | Type | Task | Status |
|---|---|---|---|---|
| `test_cast_sheet_generates_three_views_and_six_expressions` | Nine images requested | Unit | `S2-T09` | ⚠️ Deferred |
| `test_cast_sheet_uses_reference_when_backend_supports_references` | Reference attached only when supported | Unit | `S2-T09` | ⚠️ Deferred |
| `test_cast_sheet_text_only_character_same_workflow` | FR-005 path | Unit | `S2-T09` | ⚠️ Deferred |
| `test_cast_sheet_regenerate_single_view_keeps_others` | Per-view regenerate | Unit | `S2-T09` | ⚠️ Deferred |
| `test_cast_sheet_approve_makes_canonical_reference` | Approval marks canonical | Unit | `S2-T09` | ⚠️ Deferred |
| `test_cast_sheet_visual_dna_paragraph_derived_from_front_view` | Visual DNA from description plus front view | Unit | `S2-T09` | ⚠️ Deferred |
| `test_cast_sheet_character_has_stable_id` | Id stable across edits | Unit | `S2-T09` | ⚠️ Deferred |
| `test_cast_sheet_composed_sheet_image_includes_all_views` | Composed sheet has all views | Unit | `S2-T09` | ⚠️ Deferred |
| `test_cast_sheet_unapproved_character_cannot_be_used_in_panels` | Panels need an approved sheet | Unit | `S2-T09` | ⚠️ Deferred |
| `it_cast_sheet_duck_fixture_mock_backend_end_to_end` | Duck photo to approved sheet with mock | Integration | `S2-T09` | ⚠️ Deferred |

### 5.21 Originality guard (PRD FR-006)

| ID | Scenario | Type | Task | Status |
|---|---|---|---|---|
| `test_cast_originality_denylisted_name_blocked` | Name denylist | Unit | `S2-T10` | ⚠️ Deferred |
| `test_cast_originality_resemblance_flag_blocks_approval` | Resemblance check | Unit | `S2-T10` | ⚠️ Deferred |
| `test_cast_originality_block_message_names_rule` | Message names the triggered rule | Unit | `S2-T10` | ⚠️ Deferred |
| `test_cast_originality_no_override_flag_exists` | No CLI, API, or config override | Unit | `S2-T10` | ⚠️ Deferred |
| `test_cast_originality_denylist_check_on_compiled_prompt` | Compiled prompt is scanned | Unit | `S2-T10` | ⚠️ Deferred |
| `test_cast_originality_living_artist_style_blocked` | Living artist style request blocked | Unit | `S2-T10` | ⚠️ Deferred |
| `test_cast_originality_denylist_versioned_data_file` | Denylist carries a version | Unit | `S2-T10` | ⚠️ Deferred |
| `test_cast_originality_clean_duck_passes` | Original duck passes | Unit | `S2-T10` | ⚠️ Deferred |

### 5.22 Cast and library CLI, doctor checks (PRD FR-027, FR-031)

| ID | Scenario | Type | Task | Status |
|---|---|---|---|---|
| `smoke_cli_cast_add_sheet_approve_mock_backend` | cast add, sheet, approve with the mock backend | Smoke | `S2-T11` | ⚠️ Deferred |
| `test_cli_library_add_list_import_roundtrip` | Library round trip | Unit | `S2-T11` | ⚠️ Deferred |
| `test_library_import_keeps_sheets_and_visual_dna` | Imported character keeps sheet and DNA | Unit | `S2-T11` | ⚠️ Deferred |
| `test_library_import_records_version` | Version recorded on import | Unit | `S2-T11` | ⚠️ Deferred |
| `test_cli_models_pull_invokes_workflow_downloads` | models pull calls the downloader | Unit | `S2-T11` | ⚠️ Deferred |
| `test_doctor_comfyui_unreachable_hint` | ComfyUI down gives a hint | Unit | `S2-T11` | ⚠️ Deferred |
| `test_doctor_reports_installed_workflow_models` | Installed models listed | Unit | `S2-T11` | ⚠️ Deferred |
| `test_doctor_gpu_vram_detected_via_nvidia_smi` | VRAM parsed from nvidia-smi output | Unit | `S2-T11` | ⚠️ Deferred |
| `test_doctor_cloud_keys_presence_reported` | Cloud keys reported without printing values | Unit | `S2-T11` | ⚠️ Deferred |

### 5.23 Prompt compiler (PRD FR-015)

| ID | Scenario | Type | Task | Status |
|---|---|---|---|---|
| `test_panels_compiler_includes_no_text_constraint` | No-text rule | Unit | `S3-T01` | ⚠️ Deferred |
| `test_panels_compiler_adds_headroom_when_dialogue` | Balloon space | Unit | `S3-T01` | ⚠️ Deferred |
| `test_panels_compiler_deterministic_same_spec_same_prompt` | Determinism | Unit | `S3-T01` | ⚠️ Deferred |
| `test_panels_compiler_snapshot_comfyui` | Snapshot for ComfyUI | Unit | `S3-T01` | ⚠️ Deferred |
| `test_panels_compiler_snapshot_gemini` | Snapshot for Gemini | Unit | `S3-T01` | ⚠️ Deferred |
| `test_panels_compiler_snapshot_openai` | Snapshot for OpenAI | Unit | `S3-T01` | ⚠️ Deferred |
| `test_panels_compiler_reference_count_never_exceeds_backend_limit` | Reference limit property | Unit | `S3-T01` | ⚠️ Deferred |
| `test_panels_compiler_picks_sheet_views_closest_to_facing_and_expression` | Reference selection | Unit | `S3-T01` | ⚠️ Deferred |
| `test_panels_compiler_prioritizes_characters_by_screen_importance` | Priority under a tight limit | Unit | `S3-T01` | ⚠️ Deferred |
| `test_panels_compiler_aspect_ratio_from_layout_slot` | Slot aspect ratio | Unit | `S3-T01` | ⚠️ Deferred |
| `test_panels_compiler_includes_visual_dna_per_character` | Visual DNA per character | Unit | `S3-T01` | ⚠️ Deferred |
| `test_panels_compiler_denylist_checked_on_compiled_prompt` | Originality scan of final prompt | Unit | `S3-T01` | ⚠️ Deferred |

### 5.24 Jobs (PRD FR-016, NFR-006)

| ID | Scenario | Type | Task | Status |
|---|---|---|---|---|
| `it_jobs_kill_worker_mid_render_resumes` | Resilience | Integration | `S3-T02` | ⚠️ Deferred |
| `it_jobs_priority_ordering_thumbnail_below_render` | Higher priority runs first | Integration | `S3-T02` | ⚠️ Deferred |
| `it_jobs_cancel_running_job` | Cancel stops a running job | Integration | `S3-T02` | ⚠️ Deferred |
| `it_jobs_progress_events_over_websocket` | WebSocket receives progress | Integration | `S3-T02` | ⚠️ Deferred |
| `it_jobs_resume_after_restart` | Queued jobs survive a restart | Integration | `S3-T02` | ⚠️ Deferred |
| `test_jobs_retry_twice_then_fail` | Two retries then failure | Unit | `S3-T02` | ⚠️ Deferred |
| `test_jobs_single_gpu_worker_serializes_gpu_jobs` | GPU jobs run one at a time | Unit | `S3-T02` | ⚠️ Deferred |
| `test_jobs_text_workers_run_concurrently` | Text jobs overlap | Unit | `S3-T02` | ⚠️ Deferred |
| `test_jobs_enqueue_idempotent_same_key` | Duplicate enqueue returns the existing job | Unit | `S3-T02` | ⚠️ Deferred |

### 5.25 Panel render and takes (PRD FR-016, FR-014)

| ID | Scenario | Type | Task | Status |
|---|---|---|---|---|
| `test_panels_render_records_seed_backend_model_prompt_in_take` | Take record contents | Unit | `S3-T03` | ⚠️ Deferred |
| `test_panels_render_select_take_updates_active` | Select take | Unit | `S3-T03` | ⚠️ Deferred |
| `test_panels_render_retake_uses_new_seed` | Retake seed differs | Unit | `S3-T03` | ⚠️ Deferred |
| `test_panels_render_failure_retried_twice` | Retry policy | Unit | `S3-T03` | ⚠️ Deferred |
| `test_panels_render_cancel_leaves_no_partial_take` | Cancel is clean | Unit | `S3-T03` | ⚠️ Deferred |
| `test_panels_render_cache_hit_same_compiled_prompt_and_seed` | Cache key hit | Unit | `S3-T03` | ⚠️ Deferred |
| `test_panels_script_text_only_edit_does_not_mark_stale` | Text edit keeps panel fresh | Unit | `S3-T03` | ⚠️ Deferred |
| `test_panels_script_visual_edit_marks_panel_stale` | Visual edit marks stale | Unit | `S3-T03` | ⚠️ Deferred |
| `it_panels_render_four_panel_strip_mock_backend` | Four panels render end to end | Integration | `S3-T03` | ⚠️ Deferred |

### 5.26 Consistency QA (PRD FR-017, NFR-004, NFR-005)

| ID | Scenario | Type | Task | Status |
|---|---|---|---|---|
| `test_panels_qa_detected_text_triggers_retake` | OCR retake | Unit | `S3-T04` | ⚠️ Deferred |
| `test_panels_qa_low_consistency_keeps_best_take` | Best take | Unit | `S3-T04` | ⚠️ Deferred |
| `test_panels_qa_score_below_four_flags_panel` | Threshold of 4 | Unit | `S3-T04` | ⚠️ Deferred |
| `test_panels_qa_auto_retake_stops_after_n_attempts` | Retake cap | Unit | `S3-T04` | ⚠️ Deferred |
| `test_panels_qa_best_take_ordering_min_score_then_ocr_clean` | Selection order | Unit | `S3-T04` | ⚠️ Deferred |
| `test_panels_qa_results_cached_per_take` | QA cache | Unit | `S3-T04` | ⚠️ Deferred |
| `test_panels_qa_threshold_configurable_per_project` | Per-project thresholds | Unit | `S3-T04` | ⚠️ Deferred |
| `test_panels_qa_reasons_surface_to_user` | Reasons included in result | Unit | `S3-T04` | ⚠️ Deferred |
| `it_panels_qa_rapidocr_detects_text_in_fixture` | RapidOCR finds drawn text | Integration | `S3-T04` | ⚠️ Deferred |
| `it_panels_qa_vision_scores_duck_against_sheet` | Vision scoring on the duck fixture | Integration | `S3-T04` | ⚠️ Deferred |

### 5.27 Panel editing (PRD FR-018, US-007)

| ID | Scenario | Type | Task | Status |
|---|---|---|---|---|
| `test_panels_edit_inpaint_limited_to_mask` | Pixels outside the mask are unchanged | Unit | `S3-T05` | ⚠️ Deferred |
| `test_panels_edit_disabled_when_backend_lacks_edit_support` | Capability gate | Unit | `S3-T05` | ⚠️ Deferred |
| `test_panels_edit_crop_is_non_destructive` | Original asset preserved | Unit | `S3-T05` | ⚠️ Deferred |
| `test_panels_edit_shot_change_triggers_rerender` | Shot change marks stale and re-renders | Unit | `S3-T05` | ⚠️ Deferred |
| `test_panels_edit_reframe_preserves_original_asset` | Reframe keeps source | Unit | `S3-T05` | ⚠️ Deferred |
| `test_panels_edit_undo_restores_previous_take` | Undo of an edit | Unit | `S3-T05` | ⚠️ Deferred |
| `it_panels_edit_region_mock_backend_changes_only_mask` | Mock edit end to end | Integration | `S3-T05` | ⚠️ Deferred |

### 5.28 Lettering placement (PRD FR-019)

| ID | Scenario | Type | Task | Status |
|---|---|---|---|---|
| `test_letter_layout_balloons_avoid_character_boxes` | Placement | Unit | `S3-T06` | ⚠️ Deferred |
| `test_letter_layout_reading_order_left_to_right` | Reading order | Unit | `S3-T06` | ⚠️ Deferred |
| `test_letter_layout_text_never_overflows_panel` | Overflow | Unit | `S3-T06` | ⚠️ Deferred |
| `test_letter_layout_property_no_balloon_overlaps_another` | Hypothesis: no overlaps | Unit | `S3-T06` | ⚠️ Deferred |
| `test_letter_layout_property_all_balloons_inside_panel` | Hypothesis: inside panel | Unit | `S3-T06` | ⚠️ Deferred |
| `test_letter_layout_property_reading_order_holds` | Hypothesis: order holds | Unit | `S3-T06` | ⚠️ Deferred |
| `test_letter_layout_text_measured_with_real_font_metrics` | fontTools metrics drive size | Unit | `S3-T06` | ⚠️ Deferred |
| `test_letter_layout_font_downsizes_to_minimum_before_splitting` | Downsize then split lines | Unit | `S3-T06` | ⚠️ Deferred |
| `test_letter_layout_tail_points_at_speaker_head_box_edge` | Tail geometry | Unit | `S3-T06` | ⚠️ Deferred |
| `test_letter_layout_no_valid_position_falls_back_to_top_caption` | Fallback caption | Unit | `S3-T06` | ⚠️ Deferred |
| `test_letter_layout_balloon_space_hint_biases_candidates` | Hint weighting | Unit | `S3-T06` | ⚠️ Deferred |
| `test_letter_layout_deterministic_same_input_same_output` | Determinism | Unit | `S3-T06` | ⚠️ Deferred |

### 5.29 Lettering SVG and fonts (PRD FR-019, NFR-005)

| ID | Scenario | Type | Task | Status |
|---|---|---|---|---|
| `vis_letter_balloon_speech` | Speech golden | Visual | `S3-T07` | ⚠️ Deferred |
| `vis_letter_balloon_thought` | Thought golden | Visual | `S3-T07` | ⚠️ Deferred |
| `vis_letter_balloon_shout` | Shout golden | Visual | `S3-T07` | ⚠️ Deferred |
| `vis_letter_balloon_whisper` | Whisper golden | Visual | `S3-T07` | ⚠️ Deferred |
| `vis_letter_caption` | Caption golden | Visual | `S3-T07` | ⚠️ Deferred |
| `vis_letter_sfx` | SFX golden | Visual | `S3-T07` | ⚠️ Deferred |
| `test_letter_svg_text_remains_real_text_elements` | Balloon text is a text element, not paths | Unit | `S3-T07` | ⚠️ Deferred |
| `test_letter_svg_fonts_embedded_as_base64_font_face` | Base64 font-face present | Unit | `S3-T07` | ⚠️ Deferred |
| `test_letter_svg_uppercase_per_style_setting` | Case follows style | Unit | `S3-T07` | ⚠️ Deferred |
| `test_letter_svg_minimum_font_size_print_and_web` | Minimums enforced | Unit | `S3-T07` | ⚠️ Deferred |
| `test_letter_fonts_licenses_all_ofl_recorded` | Font licenses recorded | Unit | `S3-T07` | ⚠️ Deferred |

### 5.30 Strip composition and approval (PRD FR-020)

| ID | Scenario | Type | Task | Status |
|---|---|---|---|---|
| `vis_strip_four_panel_bold_cartoon` | Strip golden | Visual | `S3-T08` | ⚠️ Deferred |
| `vis_strip_rounded_corners_picture_book` | Rounded corners golden | Visual | `S3-T08` | ⚠️ Deferred |
| `test_layout_strip_svg_gutters_and_borders_per_style` | Style-driven geometry | Unit | `S3-T08` | ⚠️ Deferred |
| `test_layout_strip_approve_requires_all_panels_rendered_and_lettered` | Approval precondition | Unit | `S3-T08` | ⚠️ Deferred |
| `test_layout_strip_approved_immutable_until_unapprove` | Immutability | Unit | `S3-T08` | ⚠️ Deferred |
| `test_layout_strip_approve_triggers_arc_update_and_next_suggestions` | Side effects | Unit | `S3-T08` | ⚠️ Deferred |
| `test_layout_strip_unapprove_reopens_editing` | Unapprove | Unit | `S3-T08` | ⚠️ Deferred |
| `test_layout_strip_approve_emits_undoable_event` | Approve is an event | Unit | `S3-T08` | ⚠️ Deferred |

### 5.31 Studio views (PRD FR-029, US-001 to US-009, US-011, US-012, US-020, US-021)

| ID | Scenario | Type | Task | Status |
|---|---|---|---|---|
| `smoke_studio_shell_loads_in_chromium` | Playwright opens / and sees the header and tabs | Smoke | `S0-T08` | ⚠️ Deferred |
| `e2e_US002_empty_home_prompts_for_story_idea` | Empty Home shows 'Start with a story idea, a photo, or both.' | E2E | `S0-T08` | ⚠️ Deferred |
| `test_server_healthz_returns_ok` | GET /v1/healthz returns 200 | Unit | `S0-T08` | ✅ Automated |
| `it_server_serves_built_studio_at_root` | GET / returns the built index.html | Integration | `S0-T08` | ✅ Automated |
| `test_studio_tokens_light_and_dark_css_variables_defined` | Both themes define every token (vitest) | Unit | `S0-T08` | ✅ Automated |
| `test_cli_studio_binds_loopback_by_default` | `studio` binds 127.0.0.1 unless --host is given | Unit | `S0-T08` | ✅ Automated |
| `test_studio_theme_toggle_persists_in_try_catch_storage` | Theme choice persists and survives storage errors (vitest) | Unit | `S0-T08` | ✅ Automated |
| `e2e_US001_create_duck_project_and_approve_character_with_mocks` | Duck flow | E2E | `S3-T10` | ⚠️ Deferred |
| `e2e_US001_person_photo_requires_attestation_before_sheet` | Attestation UI gate | E2E | `S3-T10` | ⚠️ Deferred |
| `e2e_US003_start_from_narrative_only` | Narrative only | E2E | `S3-T10` | ⚠️ Deferred |
| `e2e_US003_start_from_photo_only` | Photo only | E2E | `S3-T10` | ⚠️ Deferred |
| `e2e_US002_edit_story_bible_creates_version` | Bible editor | E2E | `S3-T10` | ⚠️ Deferred |
| `e2e_US020_branch_switch_shows_alternate_strips` | Branching | E2E | `S3-T10` | ⚠️ Deferred |
| `test_studio_wizard_store_validates_length_and_audience` | Wizard validation (vitest) | Unit | `S3-T10` | ⚠️ Deferred |
| `test_studio_cast_store_regenerate_single_view_updates_state` | Cast store (vitest) | Unit | `S3-T10` | ⚠️ Deferred |
| `e2e_US006_pick_suggestion_render_retake_approve_next_suggestions` | Core loop | E2E | `S3-T11` | ⚠️ Deferred |
| `e2e_US005_write_own_beat_via_write_my_own` | Custom beat | E2E | `S3-T11` | ⚠️ Deferred |
| `e2e_US006_edit_script_before_rendering` | Script edit before art | E2E | `S3-T11` | ⚠️ Deferred |
| `e2e_US007_regenerate_single_panel_leaves_others` | Single-panel retake | E2E | `S3-T11` | ⚠️ Deferred |
| `e2e_US007_keyboard_shortcuts_jk_r_a` | Shortcuts | E2E | `S3-T11` | ⚠️ Deferred |
| `e2e_US009_end_here_option_offered_at_final_stage` | End here | E2E | `S3-T11` | ⚠️ Deferred |
| `e2e_US021_undo_redo_with_keyboard_shortcuts` | Undo and redo | E2E | `S3-T11` | ⚠️ Deferred |
| `test_studio_strips_store_panel_progress_events_update` | Store handles progress events (vitest) | Unit | `S3-T11` | ⚠️ Deferred |
| `test_studio_strips_inspector_dialogue_editor_validates_audience_limits` | Inspector validation (vitest) | Unit | `S3-T11` | ⚠️ Deferred |
| `e2e_US008_drag_balloon_persists_after_reload` | Lettering edit | E2E | `S3-T12` | ⚠️ Deferred |
| `e2e_US008_drag_tail_tip_updates_tail` | Tail drag | E2E | `S3-T12` | ⚠️ Deferred |
| `e2e_US008_resize_balloon_and_edit_text_inline` | Resize and retype | E2E | `S3-T12` | ⚠️ Deferred |
| `e2e_US008_change_balloon_type_to_shout` | Type change | E2E | `S3-T12` | ⚠️ Deferred |
| `e2e_US008_add_caption_and_sfx` | Add caption and SFX | E2E | `S3-T12` | ⚠️ Deferred |
| `e2e_US008_rerun_auto_placement_resets_manual_positions` | Re-run placement | E2E | `S3-T12` | ⚠️ Deferred |
| `e2e_US021_undo_lettering_edit` | Undo of lettering | E2E | `S3-T12` | ⚠️ Deferred |
| `test_studio_lettering_store_edit_emits_event` | Event emitted (vitest) | Unit | `S3-T12` | ⚠️ Deferred |
| `test_studio_lettering_balloon_drag_clamped_inside_panel` | Clamp to panel (vitest) | Unit | `S3-T12` | ⚠️ Deferred |
| `e2e_US011_change_layout_drag_panel_undo` | Pages core flow | E2E | `S4-T06` | ⚠️ Deferred |
| `e2e_US011_auto_paginate_button_fills_pages` | Auto-paginate | E2E | `S4-T06` | ⚠️ Deferred |
| `e2e_US011_unplaced_strips_tray_lists_leftovers` | Tray | E2E | `S4-T06` | ⚠️ Deferred |
| `e2e_US011_add_page_caption` | Page caption | E2E | `S4-T06` | ⚠️ Deferred |
| `test_studio_pages_store_move_panel_between_slots` | Store (vitest) | Unit | `S4-T06` | ⚠️ Deferred |
| `test_studio_pages_store_layout_change_preserves_panels` | Layout change keeps panels (vitest) | Unit | `S4-T06` | ⚠️ Deferred |
| `e2e_US012_build_six_page_book_with_cover_and_title` | Book flow | E2E | `S4-T07` | ⚠️ Deferred |
| `e2e_US012_reorder_pages_by_drag` | Reorder | E2E | `S4-T07` | ⚠️ Deferred |
| `e2e_US012_add_page_by_kind` | Add page | E2E | `S4-T07` | ⚠️ Deferred |
| `e2e_US012_generate_cover_from_book_view` | Cover generator | E2E | `S4-T07` | ⚠️ Deferred |
| `e2e_US012_chapter_management_for_two_stories` | Chapters | E2E | `S4-T07` | ⚠️ Deferred |
| `test_studio_book_store_reorder_emits_event` | Store emits event (vitest) | Unit | `S4-T07` | ⚠️ Deferred |

### 5.32 Layout templates, auto-paginate, and page SVG (PRD FR-023, US-011)

| ID | Scenario | Type | Task | Status |
|---|---|---|---|---|
| `test_layout_templates_six_templates_load_and_validate` | Six templates validate | Unit | `S4-T01` | ⚠️ Deferred |
| `test_layout_templates_schema_rejects_overlapping_slots` | Overlapping slots rejected | Unit | `S4-T01` | ⚠️ Deferred |
| `test_layout_templates_slots_have_unique_reading_order` | Reading order unique | Unit | `S4-T01` | ⚠️ Deferred |
| `test_layout_page_sizes_us_comic_letter_a4_square_web` | Five page sizes | Unit | `S4-T01` | ⚠️ Deferred |
| `test_layout_margins_gutter_bleed_configurable` | Configurable spacing | Unit | `S4-T01` | ⚠️ Deferred |
| `vis_template_strip_stack` | Template diagram golden | Visual | `S4-T01` | ⚠️ Deferred |
| `vis_template_classic_three_tier` | Template diagram golden | Visual | `S4-T01` | ⚠️ Deferred |
| `vis_template_grid_2x2` | Template diagram golden | Visual | `S4-T01` | ⚠️ Deferred |
| `vis_template_grid_3x3` | Template diagram golden | Visual | `S4-T01` | ⚠️ Deferred |
| `vis_template_splash_plus_two` | Template diagram golden | Visual | `S4-T01` | ⚠️ Deferred |
| `vis_template_vertical_scroll` | Template diagram golden | Visual | `S4-T01` | ⚠️ Deferred |
| `test_layout_paginate_never_splits_strip_by_default` | Pagination | Unit | `S4-T02` | ⚠️ Deferred |
| `test_layout_paginate_splits_strip_when_allowed` | Opt-in splitting | Unit | `S4-T02` | ⚠️ Deferred |
| `test_layout_paginate_property_never_drops_a_panel` | Hypothesis: panel count preserved | Unit | `S4-T02` | ⚠️ Deferred |
| `test_layout_paginate_strip_stack_three_per_page_default` | Default density | Unit | `S4-T02` | ⚠️ Deferred |
| `test_layout_paginate_three_tier_maps_panels_to_slots_in_order` | Slot order | Unit | `S4-T02` | ⚠️ Deferred |
| `test_layout_paginate_aspect_aware_crop_nondestructive` | Crop leaves source intact | Unit | `S4-T02` | ⚠️ Deferred |
| `test_layout_paginate_slot_aspect_rerender_request_built` | Optional re-render request | Unit | `S4-T02` | ⚠️ Deferred |
| `test_layout_paginate_extra_strips_flow_to_next_page` | Overflow to next page | Unit | `S4-T02` | ⚠️ Deferred |
| `test_layout_paginate_user_override_layout_per_page` | Per-page override | Unit | `S4-T02` | ⚠️ Deferred |
| `vis_page_strip_stack_us_comic` | Page golden | Visual | `S4-T03` | ⚠️ Deferred |
| `vis_page_three_tier_a4` | Page golden | Visual | `S4-T03` | ⚠️ Deferred |
| `vis_page_grid_2x2_letter` | Page golden | Visual | `S4-T03` | ⚠️ Deferred |
| `vis_page_grid_3x3_square` | Page golden | Visual | `S4-T03` | ⚠️ Deferred |
| `vis_page_splash_plus_two_us_comic` | Page golden | Visual | `S4-T03` | ⚠️ Deferred |
| `vis_page_vertical_scroll_web` | Page golden | Visual | `S4-T03` | ⚠️ Deferred |
| `vis_page_bleed_extends_art` | Bleed golden | Visual | `S4-T03` | ⚠️ Deferred |
| `test_layout_page_svg_contains_page_number_and_caption` | Page number and caption present | Unit | `S4-T03` | ⚠️ Deferred |
| `test_layout_page_svg_lettering_layer_above_art` | Layer order | Unit | `S4-T03` | ⚠️ Deferred |
| `test_layout_page_svg_bleed_off_has_no_extra_area` | No bleed area when off | Unit | `S4-T03` | ⚠️ Deferred |

### 5.33 Book builder, covers, and CLI (PRD FR-024, US-012)

| ID | Scenario | Type | Task | Status |
|---|---|---|---|---|
| `test_book_page_kinds_cover_title_dedication_story_cast_back_custom` | Seven page kinds | Unit | `S4-T04` | ⚠️ Deferred |
| `test_book_add_remove_reorder_duplicate_pages` | Page operations | Unit | `S4-T04` | ⚠️ Deferred |
| `test_book_page_numbers_skip_cover_and_title` | Numbering rules | Unit | `S4-T04` | ⚠️ Deferred |
| `test_book_toc_generated_for_multi_story` | TOC for multi-story | Unit | `S4-T04` | ⚠️ Deferred |
| `test_book_toc_not_generated_for_single_story` | No TOC for single story | Unit | `S4-T04` | ⚠️ Deferred |
| `test_book_chapters_from_multiple_finalized_stories` | Chapters | Unit | `S4-T04` | ⚠️ Deferred |
| `test_book_unfinalized_story_cannot_be_added` | Only finalized stories | Unit | `S4-T04` | ⚠️ Deferred |
| `test_book_metadata_title_author_year_language` | Metadata | Unit | `S4-T04` | ⚠️ Deferred |
| `test_book_cast_page_built_from_character_sheets` | Cast page | Unit | `S4-T04` | ⚠️ Deferred |
| `test_book_manifest_roundtrip` | Manifest round trip | Unit | `S4-T04` | ⚠️ Deferred |
| `test_book_cover_prompt_derived_from_bible_and_cast` | Cover prompt inputs | Unit | `S4-T05` | ⚠️ Deferred |
| `test_book_cover_chosen_from_existing_panel` | Pick from panels | Unit | `S4-T05` | ⚠️ Deferred |
| `test_book_cover_title_author_lettering_uses_cover_preset` | Cover typography | Unit | `S4-T05` | ⚠️ Deferred |
| `test_book_back_cover_has_blurb` | Back cover blurb | Unit | `S4-T05` | ⚠️ Deferred |
| `it_book_cover_renders_with_mock_backend` | Mock render | Integration | `S4-T05` | ⚠️ Deferred |
| `it_book_cover_gpu_passes_qa_with_comfyui` | GPU QA pass | Integration (GPU) | `S4-T05` | ⚠️ Deferred |
| `vis_cover_front_picture_book` | Cover golden | Visual | `S4-T05` | ⚠️ Deferred |
| `smoke_cli_pages_and_book_build_extends_auto` | auto then pages then book through the CLI | Smoke | `S4-T08` | ⚠️ Deferred |
| `test_cli_pages_json_lists_pages` | pages --json | Unit | `S4-T08` | ⚠️ Deferred |
| `test_cli_book_add_page_move_remove` | book page operations | Unit | `S4-T08` | ⚠️ Deferred |
| `test_cli_book_cover_sets_cover` | book cover | Unit | `S4-T08` | ⚠️ Deferred |
| `test_cli_book_show_json` | book show --json | Unit | `S4-T08` | ⚠️ Deferred |

### 5.34 Exports: Chromium renderer (PRD FR-025, NFR-009)

| ID | Scenario | Type | Task | Status |
|---|---|---|---|---|
| `it_export_chromium_pixel_diff_vs_studio_preview_under_0_1_percent` | Same renderer fidelity | Integration | `S5-T01` | ⚠️ Deferred |
| `it_export_chromium_network_disabled_blocks_http` | Network blocked | Integration | `S5-T01` | ⚠️ Deferred |
| `test_export_chromium_dsf_computed_from_target_dpi` | DSF math | Unit | `S5-T01` | ⚠️ Deferred |
| `it_export_chromium_one_browser_per_job_pages_streamed` | Browser reuse and streaming | Integration | `S5-T01` | ⚠️ Deferred |
| `it_export_chromium_missing_browser_error_hint` | Missing Chromium hint | Integration | `S5-T01` | ⚠️ Deferred |
| `test_export_chromium_data_and_file_urls_allowed` | Allowed schemes | Unit | `S5-T01` | ⚠️ Deferred |

### 5.35 Exports: images and long strip (PRD FR-025, NFR-010, US-013, US-014)

| ID | Scenario | Type | Task | Status |
|---|---|---|---|---|
| `it_export_png_300dpi_dimensions_and_metadata` | PNG dpi | Integration | `S5-T02` | ⚠️ Deferred |
| `it_export_jpg_quality_92` | JPG quality | Integration | `S5-T02` | ⚠️ Deferred |
| `it_export_webp_written` | WebP output | Integration | `S5-T02` | ⚠️ Deferred |
| `test_export_dpi_options_72_150_300_resolved` | Option resolution | Unit | `S5-T02` | ⚠️ Deferred |
| `it_export_long_strip_stacks_strips_vertically` | Long strip | Integration | `S5-T02` | ⚠️ Deferred |
| `test_export_long_strip_splits_into_parts_over_max_height` | Height guard | Unit | `S5-T02` | ⚠️ Deferred |
| `test_export_upscale_applied_when_art_below_target_dpi` | Upscale trigger | Unit | `S5-T02` | ⚠️ Deferred |
| `test_export_upscale_falls_back_to_lanczos_with_warning` | Fallback warning | Unit | `S5-T02` | ⚠️ Deferred |
| `test_export_option_resolution_defaults_per_format` | Defaults | Unit | `S5-T02` | ⚠️ Deferred |

### 5.36 Exports: PDF (PRD FR-025, NFR-009, NFR-010)

| ID | Scenario | Type | Task | Status |
|---|---|---|---|---|
| `it_export_pdf_fonts_embedded_and_text_selectable` | PDF quality | Integration | `S5-T03` | ⚠️ Deferred |
| `it_export_pdf_print_adds_bleed` | Print bleed | Integration | `S5-T03` | ⚠️ Deferred |
| `it_export_pdf_trimbox_and_bleedbox_set` | Boxes set | Integration | `S5-T03` | ⚠️ Deferred |
| `it_export_pdf_metadata_title_author_subject_keywords_producer` | Metadata | Integration | `S5-T03` | ⚠️ Deferred |
| `it_export_pdf_page_count_and_size_match_book` | Page count and size | Integration | `S5-T03` | ⚠️ Deferred |
| `it_export_pdf_trim_marks_layer_optional` | Trim marks | Integration | `S5-T03` | ⚠️ Deferred |
| `it_export_pdf_page_labels_skip_cover` | Page labels | Integration | `S5-T03` | ⚠️ Deferred |
| `it_export_pdf_balloon_text_searchable` | Search finds balloon text | Integration | `S5-T03` | ⚠️ Deferred |
| `test_export_pdf_screen_vs_print_option_resolution` | Screen and print options | Unit | `S5-T03` | ⚠️ Deferred |
| `smoke_export_pdf_manual_viewers_checklist` | Manual: Preview, Acrobat, Chrome, iOS Books | Smoke | `S5-T03` | ⚠️ Deferred |

### 5.37 Exports: CBZ (PRD FR-025)

| ID | Scenario | Type | Task | Status |
|---|---|---|---|---|
| `it_export_cbz_pages_in_order` | Order | Integration | `S5-T04` | ⚠️ Deferred |
| `it_export_cbz_comicinfo_xml_valid` | Metadata | Integration | `S5-T04` | ⚠️ Deferred |
| `test_export_cbz_filename_padding_sorts_lexically` | Zero-padded names | Unit | `S5-T04` | ⚠️ Deferred |
| `it_export_cbz_zip_structure_validates` | Structure | Integration | `S5-T04` | ⚠️ Deferred |

### 5.38 Exports: web (PRD FR-025, US-023, ADR-014)

| ID | Scenario | Type | Task | Status |
|---|---|---|---|---|
| `it_export_web_single_file_works_offline` | Web export | Integration | `S5-T06` | ⚠️ Deferred |
| `it_export_web_has_data_narrate_markup` | audio-smith compat | Integration | `S5-T06` | ⚠️ Deferred |
| `it_export_web_static_folder_layout` | Folder layout | Integration | `S5-T06` | ⚠️ Deferred |
| `it_export_web_works_from_file_url` | file:// load | Integration | `S5-T06` | ⚠️ Deferred |
| `it_export_web_og_tags_with_cover` | Open Graph | Integration | `S5-T06` | ⚠️ Deferred |
| `it_export_web_single_file_size_warning_over_50mb` | Size warning | Integration | `S5-T06` | ⚠️ Deferred |
| `it_export_web_title_h1_and_speaker_roles` | Title and roles | Integration | `S5-T06` | ⚠️ Deferred |
| `it_export_web_balloons_in_reading_order_in_narrate_article` | Reading order | Integration | `S5-T06` | ⚠️ Deferred |
| `it_export_web_alt_text_from_panel_action` | Alt text | Integration | `S5-T06` | ⚠️ Deferred |
| `smoke_export_web_narrated_by_audio_smith` | Manual check: narrate with mr-audio-smith | Smoke | `S5-T06` | ⚠️ Deferred |

### 5.39 Reader (PRD NFR-007, FR-025)

| ID | Scenario | Type | Task | Status |
|---|---|---|---|---|
| `e2e_US013_reader_flipbook_keyboard_and_swipe` | Flipbook | E2E | `S5-T05` | ⚠️ Deferred |
| `e2e_US013_reader_scroll_mode_stacks_pages` | Scroll mode | E2E | `S5-T05` | ⚠️ Deferred |
| `e2e_US013_reader_axe_zero_violations` | Accessibility | E2E | `S5-T05` | ⚠️ Deferred |
| `test_reader_spread_on_wide_screens` | Spread | Unit | `S5-T05` | ⚠️ Deferred |
| `test_reader_reduced_motion_disables_page_turn` | Reduced motion | Unit | `S5-T05` | ⚠️ Deferred |
| `test_reader_alt_text_per_panel` | Alt text | Unit | `S5-T05` | ⚠️ Deferred |
| `test_reader_balloons_rendered_as_dom_text` | DOM text | Unit | `S5-T05` | ⚠️ Deferred |
| `test_reader_bundle_under_25kb_gzipped` | Size budget | Unit | `S5-T05` | ⚠️ Deferred |
| `test_reader_no_external_requests` | No network | Unit | `S5-T05` | ⚠️ Deferred |

### 5.40 Export dialog and export CLI (PRD FR-025, FR-030, US-013, US-014)

| ID | Scenario | Type | Task | Status |
|---|---|---|---|---|
| `e2e_US013_export_book_pdf_from_studio` | Export | E2E | `S5-T07` | ⚠️ Deferred |
| `e2e_US014_export_long_strip_from_studio` | Long strip | E2E | `S5-T07` | ⚠️ Deferred |
| `e2e_US013_export_history_lists_previous_exports` | History | E2E | `S5-T07` | ⚠️ Deferred |
| `smoke_cli_auto_to_pdf_outputs_exist` | End to end | Smoke | `S5-T07` | ⚠️ Deferred |
| `smoke_cli_export_json_lists_files` | export --json | Smoke | `S5-T07` | ⚠️ Deferred |
| `test_cli_export_all_formats_flag_parsing` | Format flags | Unit | `S5-T07` | ⚠️ Deferred |
| `test_cli_export_target_page_story_book` | Targets | Unit | `S5-T07` | ⚠️ Deferred |
| `test_studio_export_dialog_store_estimates_size` | Size estimate (vitest) | Unit | `S5-T07` | ⚠️ Deferred |

### 5.41 Child mode (PRD US-004, NFR-007)

| ID | Scenario | Type | Task | Status |
|---|---|---|---|---|
| `e2e_US004_child_mode_pick_choice_renders_strip` | Child mode | E2E | `S6-T01` | ⚠️ Deferred |
| `e2e_US004_child_mode_touch_targets_at_least_64px` | Target size | E2E | `S6-T01` | ⚠️ Deferred |
| `e2e_US004_child_mode_hides_settings_and_delete` | Restricted UI | E2E | `S6-T01` | ⚠️ Deferred |
| `e2e_US004_child_mode_long_press_exit_after_2s` | Exit gesture | E2E | `S6-T01` | ⚠️ Deferred |
| `e2e_US004_child_mode_choice_label_read_aloud` | Speech synthesis called | E2E | `S6-T01` | ⚠️ Deferred |
| `e2e_US004_child_mode_read_our_comic_opens_reader` | Reader opens | E2E | `S6-T01` | ⚠️ Deferred |
| `e2e_US004_child_mode_axe_zero_violations` | Accessibility | E2E | `S6-T01` | ⚠️ Deferred |
| `test_studio_child_mode_store_long_press_threshold` | Threshold (vitest) | Unit | `S6-T01` | ⚠️ Deferred |

### 5.42 Auto mode (PRD FR-026, US-016)

| ID | Scenario | Type | Task | Status |
|---|---|---|---|---|
| `test_story_auto_policy_steer_heavy_picks_steer` | Steer-heavy | Unit | `S6-T02` | ⚠️ Deferred |
| `test_story_auto_policy_twist_heavy_picks_twist` | Twist-heavy | Unit | `S6-T02` | ⚠️ Deferred |
| `test_story_auto_policy_balanced_mix` | Balanced | Unit | `S6-T02` | ⚠️ Deferred |
| `test_story_auto_stops_at_target_before_finalize` | Stop condition | Unit | `S6-T02` | ⚠️ Deferred |
| `test_story_auto_actions_recorded_with_actor_auto` | Audit | Unit | `S6-T02` | ⚠️ Deferred |
| `test_story_auto_each_action_undoable` | Undo | Unit | `S6-T02` | ⚠️ Deferred |
| `test_story_auto_qa_failure_after_retakes_flags_strip_for_review` | QA failure path | Unit | `S6-T02` | ⚠️ Deferred |
| `it_story_auto_renders_letters_approves_with_mock_backend` | Full auto with mocks | Integration | `S6-T02` | ⚠️ Deferred |
| `e2e_US016_draft_the_rest_for_me_shows_progress_and_review` | Studio button | E2E | `S6-T02` | ⚠️ Deferred |

### 5.43 Safety review (PRD NFR-001, NFR-002, NFR-012)

| ID | Scenario | Type | Task | Status |
|---|---|---|---|---|
| `test_safety_redteam_originality_prompts_all_blocked` | Originality red team | Unit | `S6-T03` | ⚠️ Deferred |
| `test_safety_redteam_audience_prompts_all_blocked` | Audience red team | Unit | `S6-T03` | ⚠️ Deferred |
| `test_safety_redteam_people_prompts_all_declined` | People red team | Unit | `S6-T03` | ⚠️ Deferred |
| `it_safety_fuzz_uploads_never_crash_ingest` | Upload fuzz | Integration | `S6-T03` | ⚠️ Deferred |
| `test_ci_security_jobs_pip_audit_npm_audit_gitleaks_bandit_declared` | CI scanners declared | Unit | `S6-T03` | ⚠️ Deferred |
| `test_safety_zero_telemetry_no_outbound_calls_by_default` | NFR-002 | Unit | `S6-T03` | ⚠️ Deferred |
| `test_safety_guards_enforced_below_front_doors` | Import-linter rule | Unit | `S6-T03` | ⚠️ Deferred |
| `test_safety_review_doc_has_no_high_or_critical_findings` | Report gate | Unit | `S6-T03` | ⚠️ Deferred |

### 5.44 Evaluation (PRD NFR-004, NFR-005)

| ID | Scenario | Type | Task | Status |
|---|---|---|---|---|
| `it_eval_duck_story_consistency_at_least_90_percent_score_4_plus` | Duck story (scripted plus human review) | Evaluation | `S6-T04` | ⚠️ Deferred |
| `it_eval_robot_story_consistency_at_least_90_percent` | Robot story (scripted plus human review) | Evaluation | `S6-T04` | ⚠️ Deferred |
| `it_eval_newsletter_gpu_gag_consistency_at_least_90_percent` | Newsletter gag-a-day (scripted plus human review) | Evaluation | `S6-T04` | ⚠️ Deferred |
| `it_eval_gemini_backend_duck_story_consistency` | Cloud backend run (scripted plus human review) | Evaluation | `S6-T04` | ⚠️ Deferred |
| `it_eval_zero_model_drawn_text_in_approved_panels` | NFR-005 OCR check (scripted plus human review) | Evaluation | `S6-T04` | ⚠️ Deferred |
| `smoke_eval_human_scores_average_at_least_4` | Manual human rubric | Smoke | `S6-T04` | ⚠️ Deferred |
| `test_eval_script_writes_evals_md_table` | Scripted metrics output | Unit | `S6-T04` | ⚠️ Deferred |

### 5.45 Docs and licenses (PRD NFR-011)

| ID | Scenario | Type | Task | Status |
|---|---|---|---|---|
| `smoke_docs_mkdocs_build_strict_no_broken_links` | Docs build | Smoke | `S6-T05` | ⚠️ Deferred |
| `smoke_docs_quickstart_commands_copy_paste_cleanly` | Quickstart commands | Smoke | `S6-T05` | ⚠️ Deferred |
| `smoke_docs_quickstart_under_15_minutes_fresh_machine` | Manual timing check | Smoke | `S6-T05` | ⚠️ Deferred |
| `test_docs_cli_reference_matches_typer_commands` | CLI reference sync | Unit | `S6-T05` | ⚠️ Deferred |
| `test_docs_api_reference_matches_openapi` | API reference sync | Unit | `S6-T05` | ⚠️ Deferred |
| `test_docs_site_sections_all_listed_present` | All required pages exist | Unit | `S6-T05` | ⚠️ Deferred |
| `test_licenses_third_party_file_covers_all_python_deps` | Python deps | Unit | `S6-T06` | ⚠️ Deferred |
| `test_licenses_third_party_file_covers_all_npm_deps` | npm deps | Unit | `S6-T06` | ⚠️ Deferred |
| `test_licenses_model_weights_section_per_workflow` | Weights per workflow | Unit | `S6-T06` | ⚠️ Deferred |
| `test_licenses_fonts_ofl_texts_included` | OFL texts | Unit | `S6-T06` | ⚠️ Deferred |
| `test_licenses_ci_fails_on_missing_entry` | CI gate | Unit | `S6-T06` | ⚠️ Deferred |
| `test_licenses_non_commercial_weights_labeled` | Labeling | Unit | `S6-T06` | ⚠️ Deferred |

### 5.46 Release (PRD NFR-008, NFR-011)

| ID | Scenario | Type | Task | Status |
|---|---|---|---|---|
| `it_release_testpypi_rc_install_and_studio_offline` | RC install | Integration | `S6-T07` | ⚠️ Deferred |
| `it_release_wheel_contains_studio_static_assets` | Wheel contents | Integration | `S6-T07` | ⚠️ Deferred |
| `test_release_workflow_runs_check_versions` | Version gate | Unit | `S6-T07` | ⚠️ Deferred |
| `test_release_github_release_attaches_sbom` | SBOM | Unit | `S6-T07` | ⚠️ Deferred |
| `test_release_npm_package_reader_published_files` | npm files | Unit | `S6-T07` | ⚠️ Deferred |
| `test_release_provenance_attestation_declared` | Provenance | Unit | `S6-T07` | ⚠️ Deferred |
| `smoke_release_uv_tool_install_v1_0_0_studio_works_offline` | Post-release install | Smoke | `S6-T07` | ⚠️ Deferred |
| `smoke_release_duck_book_launch_validation` | Manual: duck book to PDF and web | Smoke | `S6-T07` | ⚠️ Deferred |

### 5.47 Server (PRD FR-032, NFR-012)

| ID | Scenario | Type | Task | Status |
|---|---|---|---|---|
| `test_server_non_localhost_requires_bearer_token` | Auth required off-loopback | Unit | `S7-T01` | ⚠️ Deferred |
| `test_server_localhost_allows_without_token` | Loopback open | Unit | `S7-T01` | ⚠️ Deferred |
| `test_server_wrong_token_returns_401` | Bad token | Unit | `S7-T01` | ⚠️ Deferred |
| `test_server_rate_limit_returns_429` | Rate limit | Unit | `S7-T01` | ⚠️ Deferred |
| `it_server_readyz_flips_when_dependency_down` | Readiness | Integration | `S7-T01` | ⚠️ Deferred |
| `test_server_errors_are_problem_json` | Error format | Unit | `S7-T01` | ⚠️ Deferred |
| `test_server_openapi_published_at_v1_openapi_json` | OpenAPI | Unit | `S7-T01` | ⚠️ Deferred |
| `test_server_api_only_mode_serves_no_static` | API-only mode | Unit | `S7-T01` | ⚠️ Deferred |
| `test_server_with_studio_serves_static` | Studio mode | Unit | `S7-T01` | ⚠️ Deferred |

### 5.48 Classroom mode (PRD FR-034, US-024)

| ID | Scenario | Type | Task | Status |
|---|---|---|---|---|
| `e2e_US024_two_browsers_see_only_own_projects` | Isolation | E2E | `S7-T02` | ⚠️ Deferred |
| `e2e_US024_access_code_required_to_join` | Access code | E2E | `S7-T02` | ⚠️ Deferred |
| `e2e_US024_teacher_view_lists_all_projects` | Teacher view | E2E | `S7-T02` | ⚠️ Deferred |
| `test_server_workspaces_name_chosen_at_join` | Workspace creation | Unit | `S7-T02` | ⚠️ Deferred |
| `test_server_project_sharing_within_instance` | Sharing | Unit | `S7-T02` | ⚠️ Deferred |
| `test_server_lan_requires_access_code_flag` | Flag validation | Unit | `S7-T02` | ⚠️ Deferred |
| `test_server_wrong_access_code_rejected` | Bad code | Unit | `S7-T02` | ⚠️ Deferred |
| `it_jobs_gpu_fairness_round_robin_by_user` | Fair scheduling | Integration | `S7-T02` | ⚠️ Deferred |

### 5.49 MCP server (PRD FR-032, US-017)

| ID | Scenario | Type | Task | Status |
|---|---|---|---|---|
| `it_mcp_stdio_create_suggest_make_strip_export_with_mocks` | Full flow over stdio | Integration | `S7-T03` | ⚠️ Deferred |
| `test_mcp_tools_list_all_thirteen_tools` | Tool inventory | Unit | `S7-T03` | ⚠️ Deferred |
| `test_mcp_tool_schemas_valid_json_schema` | Schemas valid | Unit | `S7-T03` | ⚠️ Deferred |
| `test_mcp_tool_descriptions_state_originality_and_people_rules` | Rules in descriptions | Unit | `S7-T03` | ⚠️ Deferred |
| `it_mcp_make_strip_emits_progress_notifications_per_panel` | Progress | Integration | `S7-T03` | ⚠️ Deferred |
| `it_mcp_streamable_http_transport_handshake` | HTTP transport | Integration | `S7-T03` | ⚠️ Deferred |
| `test_mcp_approve_character_blocked_by_originality_returns_error` | Guard through MCP | Unit | `S7-T03` | ⚠️ Deferred |
| `test_mcp_create_project_person_photo_requires_attestation` | People guard through MCP | Unit | `S7-T03` | ⚠️ Deferred |
| `test_mcp_list_backends_reports_capabilities` | Backend listing | Unit | `S7-T03` | ⚠️ Deferred |
| `test_mcp_recommend_returns_style_audience_arc` | Recommend tool | Unit | `S7-T03` | ⚠️ Deferred |

### 5.50 CLI remote mode (PRD FR-030, FR-032)

| ID | Scenario | Type | Task | Status |
|---|---|---|---|---|
| `it_cli_remote_server_new_suggest_strip_against_local_server` | Remote flow | Integration | `S7-T04` | ⚠️ Deferred |
| `it_cli_remote_export_downloads_files` | Export download | Integration | `S7-T04` | ⚠️ Deferred |
| `test_cli_remote_token_sent_as_bearer` | Auth header | Unit | `S7-T04` | ⚠️ Deferred |
| `test_cli_remote_unreachable_server_exit_code` | Failure mode | Unit | `S7-T04` | ⚠️ Deferred |
| `test_cli_remote_flags_env_precedence` | Config precedence | Unit | `S7-T04` | ⚠️ Deferred |

### 5.51 Harness integrations (PRD FR-032, US-017)

| ID | Scenario | Type | Task | Status |
|---|---|---|---|---|
| `test_pi_commands_comic_new_calls_rest_create_project` | /comic new | Unit | `S8-T01` | ⚠️ Deferred |
| `test_pi_commands_comic_next_shows_three_options_pick_by_number` | /comic next | Unit | `S8-T01` | ⚠️ Deferred |
| `test_pi_commands_comic_strip_by_number_or_beat` | /comic strip | Unit | `S8-T01` | ⚠️ Deferred |
| `test_pi_commands_comic_book_and_export` | /comic book and export | Unit | `S8-T01` | ⚠️ Deferred |
| `test_pi_on_update_streams_panel_progress` | Progress streaming | Unit | `S8-T01` | ⚠️ Deferred |
| `test_pi_context_extension_lists_styles_and_active_project` | Context hook | Unit | `S8-T01` | ⚠️ Deferred |
| `test_pi_typebox_schemas_mirror_mcp_tools` | Schema parity | Unit | `S8-T01` | ⚠️ Deferred |
| `test_pi_rest_error_surfaced_as_message` | Error surfacing | Unit | `S8-T01` | ⚠️ Deferred |
| `smoke_pi_manual_session_recorded` | Manual: recorded Pi session | Smoke | `S8-T01` | ⚠️ Deferred |
| `smoke_goose_toolkit_lists_tools` | Tools visible from Goose | Smoke | `S8-T02` | ⚠️ Deferred |
| `test_goose_toolkit_yaml_launches_mr_comic_smith_mcp` | Command in toolkit | Unit | `S8-T02` | ⚠️ Deferred |
| `test_goose_toolkit_yaml_parses` | YAML valid | Unit | `S8-T02` | ⚠️ Deferred |
| `smoke_goose_scripted_session_new_to_export_with_mocks` | Scripted session | Smoke | `S8-T02` | ⚠️ Deferred |
| `smoke_opencode_config_lists_tools` | Tools visible from OpenCode | Smoke | `S8-T03` | ⚠️ Deferred |
| `test_opencode_example_json_parses_and_points_to_mcp_command` | Config valid | Unit | `S8-T03` | ⚠️ Deferred |
| `test_opencode_readme_documents_setup_steps` | README | Unit | `S8-T03` | ⚠️ Deferred |
| `smoke_opencode_scripted_session_new_to_export_with_mocks` | Scripted session | Smoke | `S8-T03` | ⚠️ Deferred |
| `smoke_claude_code_scripted_session_makes_three_strip_story` | Scripted session | Smoke | `S8-T04` | ⚠️ Deferred |
| `test_claude_code_skill_md_frontmatter_valid` | Frontmatter | Unit | `S8-T04` | ⚠️ Deferred |
| `test_claude_code_skill_states_originality_and_people_rules` | Rules | Unit | `S8-T04` | ⚠️ Deferred |
| `test_claude_code_skill_requires_showing_sheet_path_before_strips` | Approval step | Unit | `S8-T04` | ⚠️ Deferred |
| `test_claude_code_skill_documents_claude_mcp_add_command` | Setup | Unit | `S8-T04` | ⚠️ Deferred |
| `test_claude_code_skill_loop_order_create_approve_suggest_make_finalize_book_export` | Loop order | Unit | `S8-T04` | ⚠️ Deferred |
| `smoke_harness_mcp_stdio_handshake` | Handshake | Smoke | `S8-T05` | ⚠️ Deferred |
| `smoke_harness_mcp_tools_list_matches_expected` | tools/list | Smoke | `S8-T05` | ⚠️ Deferred |
| `test_harness_ci_job_runs_pi_extension_unit_tests` | Pi tests wired | Unit | `S8-T05` | ⚠️ Deferred |
| `test_ci_harness_smoke_job_runs_on_staging_and_release_only` | Trigger rules | Unit | `S8-T05` | ⚠️ Deferred |
| `smoke_harness_green_on_staging` | Job result | Smoke | `S8-T05` | ⚠️ Deferred |

### 5.52 Packaging: Docker and Compose (PRD NFR-008)

| ID | Scenario | Type | Task | Status |
|---|---|---|---|---|
| `smoke_docker_cpu_image_doctor_green` | CPU doctor | Smoke | `S9-T01` | ⚠️ Deferred |
| `smoke_docker_cuda_image_doctor_green` | CUDA doctor | Smoke | `S9-T01` | ⚠️ Deferred |
| `smoke_docker_cpu_image_under_1_5_gb` | Size budget | Smoke | `S9-T01` | ⚠️ Deferred |
| `smoke_docker_cpu_image_studio_bundled_serves_root` | Studio bundled | Smoke | `S9-T01` | ⚠️ Deferred |
| `smoke_docker_multiarch_manifest_has_amd64_and_arm64` | Multi-arch | Smoke | `S9-T01` | ⚠️ Deferred |
| `test_docker_images_run_as_non_root` | Non-root | Unit | `S9-T01` | ⚠️ Deferred |
| `test_docker_comfyui_image_pins_commit_and_nodes` | Pinning | Unit | `S9-T01` | ⚠️ Deferred |
| `test_docker_comfyui_image_contains_no_model_weights` | No weights | Unit | `S9-T01` | ⚠️ Deferred |
| `smoke_compose_local_up_serves_studio` | Studio served | Smoke | `S9-T02` | ⚠️ Deferred |
| `smoke_compose_local_duck_strip_completes_on_gpu_host` | Manual GPU: duck strip | Smoke | `S9-T02` | ⚠️ Deferred |
| `test_compose_local_yaml_valid_config` | compose config passes | Unit | `S9-T02` | ⚠️ Deferred |
| `test_compose_local_requires_access_code_env` | Access code required | Unit | `S9-T02` | ⚠️ Deferred |
| `test_compose_prod_images_pinned_by_digest` | Digest pins | Unit | `S9-T02` | ⚠️ Deferred |
| `test_compose_prod_read_only_root_filesystems` | Read-only roots | Unit | `S9-T02` | ⚠️ Deferred |
| `test_compose_prod_ollama_comfyui_not_published` | No published ports | Unit | `S9-T02` | ⚠️ Deferred |
| `test_compose_prod_secrets_for_token_and_access_code` | Secrets | Unit | `S9-T02` | ⚠️ Deferred |

### 5.53 Packaging: Helm and signing (PRD NFR-008, NFR-011)

| ID | Scenario | Type | Task | Status |
|---|---|---|---|---|
| `smoke_helm_lint_passes` | helm lint | Smoke | `S9-T03` | ⚠️ Deferred |
| `smoke_helm_template_renders_all_resources` | helm template | Smoke | `S9-T03` | ⚠️ Deferred |
| `smoke_helm_ct_install_kind_mock_backend` | ct install in kind | Smoke | `S9-T03` | ⚠️ Deferred |
| `test_helm_comic_smith_statefulset_single_replica` | Single replica | Unit | `S9-T03` | ⚠️ Deferred |
| `test_helm_networkpolicy_only_comic_smith_reaches_comfyui_ollama` | NetworkPolicy | Unit | `S9-T03` | ⚠️ Deferred |
| `test_helm_ingress_timeout_body_size_websocket` | Ingress annotations | Unit | `S9-T03` | ⚠️ Deferred |
| `test_helm_values_k3s_gpu_renders` | k3s values | Unit | `S9-T03` | ⚠️ Deferred |
| `test_helm_export_deployment_optional_hpa` | Optional export workers | Unit | `S9-T03` | ⚠️ Deferred |
| `smoke_cosign_verify_released_image` | Image signature | Smoke | `S9-T04` | ⚠️ Deferred |
| `smoke_cosign_verify_released_chart` | Chart signature | Smoke | `S9-T04` | ⚠️ Deferred |
| `test_ci_publish_workflow_signs_images_and_chart` | Workflow signs | Unit | `S9-T04` | ⚠️ Deferred |
| `test_ci_publish_workflow_attaches_sbom_attestation` | SBOM | Unit | `S9-T04` | ⚠️ Deferred |
| `test_ci_publish_workflow_runs_only_on_tags` | Trigger | Unit | `S9-T04` | ⚠️ Deferred |

### 5.99 Additional automated scenarios

| ID | Scenario | Type | Task | Status |
|---|---|---|---|---|
| `e2e_US002_empty_home_prompts_for_story_idea` | US002 empty home prompts for story idea | E2E | none | ✅ Automated |
| `e2e_studio_client_route_and_theme_toggle` | studio client route and theme toggle | E2E | none | ✅ Automated |
| `it_db_failed_migration_restores_backup_and_unlocks` | db failed migration restores backup and unlocks | Integration | none | ✅ Automated |
| `it_db_lock_held_by_other_process` | db lock held by other process | Integration | none | ✅ Automated |
| `smoke_doctor_json_parses` | doctor json parses | Smoke | none | ✅ Automated |
| `test_assets_store_clean_tmp_removes_killed_write_leftovers` | assets store clean tmp removes killed write leftovers | Unit | none | ✅ Automated |
| `test_assets_store_gc_grace_period_protects_new_assets` | assets store gc grace period protects new assets | Unit | none | ✅ Automated |
| `test_assets_store_gc_removes_only_unreferenced` | assets store gc removes only unreferenced | Unit | none | ✅ Automated |
| `test_assets_store_gc_removes_orphan_file_without_row` | assets store gc removes orphan file without row | Unit | none | ✅ Automated |
| `test_assets_store_put_repairs_missing_row_and_joins_session` | assets store put repairs missing row and joins session | Unit | none | ✅ Automated |
| `test_assets_store_put_returns_ref_and_layout` | assets store put returns ref and layout | Unit | none | ✅ Automated |
| `test_assets_store_rejects_bad_ext_and_bad_sha` | assets store rejects bad ext and bad sha | Unit | none | ✅ Automated |
| `test_assets_store_same_bytes_other_ext_reuses_file` | assets store same bytes other ext reuses file | Unit | none | ✅ Automated |
| `test_cli_config_error_maps_to_exit_two` | cli config error maps to exit two | Unit | none | ✅ Automated |
| `test_cli_doctor_fix_flag_calls_fix` | cli doctor fix flag calls fix | Unit | none | ✅ Automated |
| `test_cli_no_args_shows_help` | cli no args shows help | Unit | none | ✅ Automated |
| `test_cli_studio_passes_port_to_api` | cli studio passes port to api | Unit | none | ✅ Automated |
| `test_config_bad_toml_raises` | config bad toml raises | Unit | none | ✅ Automated |
| `test_config_derived_dirs_under_data_dir` | config derived dirs under data dir | Unit | none | ✅ Automated |
| `test_config_explicit_missing_path_raises` | config explicit missing path raises | Unit | none | ✅ Automated |
| `test_config_invalid_value_raises_config_error` | config invalid value raises config error | Unit | none | ✅ Automated |
| `test_config_ollama_host_conventional_name` | config ollama host conventional name | Unit | none | ✅ Automated |
| `test_config_redacted_masks_secrets` | config redacted masks secrets | Unit | none | ✅ Automated |
| `test_config_secret_key_in_file_rejected` | config secret key in file rejected | Unit | none | ✅ Automated |
| `test_config_unknown_key_warns` | config unknown key warns | Unit | none | ✅ Automated |
| `test_config_user_config_dir_is_searched` | config user config dir is searched | Unit | none | ✅ Automated |
| `test_db_check_constraints_reject_bad_rows` | db check constraints reject bad rows | Unit | none | ✅ Automated |
| `test_db_models_cover_every_architecture_table` | db models cover every architecture table | Unit | none | ✅ Automated |
| `test_db_models_match_migrated_schema` | db models match migrated schema | Unit | none | ✅ Automated |
| `test_db_one_active_branch_per_project` | db one active branch per project | Unit | none | ✅ Automated |
| `test_db_open_existing_empty_file_migrates_without_backup` | db open existing empty file migrates without backup | Unit | none | ✅ Automated |
| `test_db_pragmas_applied_on_every_connection` | db pragmas applied on every connection | Unit | none | ✅ Automated |
| `test_db_project_lock_blocks_second_open_until_close` | db project lock blocks second open until close | Unit | none | ✅ Automated |
| `test_db_project_open_failure_releases_lock` | db project open failure releases lock | Unit | none | ✅ Automated |
| `test_db_project_open_missing_raises_not_found` | db project open missing raises not found | Unit | none | ✅ Automated |
| `test_db_readonly_session_rejects_writes` | db readonly session rejects writes | Unit | none | ✅ Automated |
| `test_db_reopen_does_not_back_up_when_current` | db reopen does not back up when current | Unit | none | ✅ Automated |
| `test_db_session_rolls_back_on_error` | db session rolls back on error | Unit | none | ✅ Automated |
| `test_doctor_chromium_present_ok` | doctor chromium present ok | Unit | none | ✅ Automated |
| `test_doctor_crashing_check_is_reported_not_raised` | doctor crashing check is reported not raised | Unit | none | ✅ Automated |
| `test_doctor_fix_runs_playwright_install` | doctor fix runs playwright install | Unit | none | ✅ Automated |
| `test_doctor_fonts_missing_is_warning` | doctor fonts missing is warning | Unit | none | ✅ Automated |
| `test_doctor_fonts_present_ok` | doctor fonts present ok | Unit | none | ✅ Automated |
| `test_doctor_optional_failure_still_exits_zero` | doctor optional failure still exits zero | Unit | none | ✅ Automated |
| `test_doctor_python_and_disk_checks_pass` | doctor python and disk checks pass | Unit | none | ✅ Automated |
| `test_doctor_table_output_lists_checks` | doctor table output lists checks | Unit | none | ✅ Automated |
| `test_events_actor_accepts_strings_and_rejects_unknown` | events actor accepts strings and rejects unknown | Unit | none | ✅ Automated |
| `test_events_non_undoable_event_does_not_clear_redo_or_enter_undo_stack` | events non undoable event does not clear redo or enter undo stack | Unit | none | ✅ Automated |
| `test_events_projects_have_separate_stacks` | events projects have separate stacks | Unit | none | ✅ Automated |
| `test_events_unknown_type_and_failing_handler_record_nothing` | events unknown type and failing handler record nothing | Unit | none | ✅ Automated |
| `test_events_workspace_scopes_undo_and_redo` | events workspace scopes undo and redo | Unit | none | ✅ Automated |
| `test_events_write_scanner_detects_direct_session_writes` | events write scanner detects direct session writes | Unit | none | ✅ Automated |
| `test_server_comic_smith_error_renders_problem_json` | server comic smith error renders problem json | Unit | none | ✅ Automated |
| `test_server_csp_matches_architecture_11_3` | server csp matches architecture 11 3 | Unit | none | ✅ Automated |
| `test_server_default_static_dir_still_answers` | server default static dir still answers | Unit | none | ✅ Automated |
| `test_server_missing_asset_is_404_not_index` | server missing asset is 404 not index | Unit | none | ✅ Automated |
| `test_server_placeholder_page_when_studio_not_built` | server placeholder page when studio not built | Unit | none | ✅ Automated |
| `test_server_readyz_returns_ok` | server readyz returns ok | Unit | none | ✅ Automated |
| `test_server_run_allows_non_localhost_with_credential` | server run allows non localhost with credential | Unit | none | ✅ Automated |
| `test_server_run_binds_given_loopback_host` | server run binds given loopback host | Unit | none | ✅ Automated |
| `test_server_run_empty_secret_does_not_count` | server run empty secret does not count | Unit | none | ✅ Automated |
| `test_server_run_opens_browser_when_requested` | server run opens browser when requested | Unit | none | ✅ Automated |
| `test_server_run_refuses_non_localhost_without_token` | server run refuses non localhost without token | Unit | none | ✅ Automated |
| `test_server_security_headers_on_every_response` | server security headers on every response | Unit | none | ✅ Automated |
| `test_server_serves_static_assets` | server serves static assets | Unit | none | ✅ Automated |
| `test_server_spa_fallback_does_not_apply_to_api` | server spa fallback does not apply to api | Unit | none | ✅ Automated |
| `test_server_spa_fallback_serves_index_for_client_routes` | server spa fallback serves index for client routes | Unit | none | ✅ Automated |
| `test_server_static_path_traversal_is_not_served` | server static path traversal is not served | Unit | none | ✅ Automated |
| `test_server_wait_for_port_times_out_on_closed_port` | server wait for port times out on closed port | Unit | none | ✅ Automated |
| `test_visual_compare_size_mismatch_fails` | visual compare size mismatch fails | Unit | none | ✅ Automated |
| `e2e_US002_empty_home_prompts_for_story_idea` | US002 empty home prompts for story idea | E2E | none | ✅ Automated |
| `it_ollama_embeddings_are_normalized` | ollama embeddings are normalized | Integration | none | ✅ Automated |
| `test_approve_unapprove_list_and_edit_panel` | approve unapprove list and edit panel | Unit | none | ✅ Automated |
| `test_auto_then_finalize_then_reopen` | auto then finalize then reopen | Unit | none | ✅ Automated |
| `test_balanced_policy_rotates_continue_steer_twist` | balanced policy rotates continue steer twist | Unit | none | ✅ Automated |
| `test_branch_none_means_the_active_branch` | branch none means the active branch | Unit | none | ✅ Automated |
| `test_branches_round_trip` | branches round trip | Unit | none | ✅ Automated |
| `test_cli_approve_and_history_undo_redo` | cli approve and history undo redo | Unit | none | ✅ Automated |
| `test_cli_auto_one_step_and_bad_policy` | cli auto one step and bad policy | Unit | none | ✅ Automated |
| `test_cli_branch_argument_and_confirmation_rules` | cli branch argument and confirmation rules | Unit | none | ✅ Automated |
| `test_cli_branch_delete_asks_and_deletes_on_yes` | cli branch delete asks and deletes on yes | Unit | none | ✅ Automated |
| `test_cli_errors_json_problem_object_and_exit_codes` | cli errors json problem object and exit codes | Unit | none | ✅ Automated |
| `test_cli_finalize_human_output` | cli finalize human output | Unit | none | ✅ Automated |
| `test_cli_finalize_json_and_human` | cli finalize json and human | Unit | none | ✅ Automated |
| `test_cli_new_human_output_shows_the_bible` | cli new human output shows the bible | Unit | none | ✅ Automated |
| `test_cli_new_without_narrative_or_with_image_is_a_usage_error` | cli new without narrative or with image is a usage error | Unit | none | ✅ Automated |
| `test_cli_strip_needs_exactly_one_of_pick_and_beat` | cli strip needs exactly one of pick and beat | Unit | none | ✅ Automated |
| `test_cli_undo_and_redo_with_nothing_to_do` | cli undo and redo with nothing to do | Unit | none | ✅ Automated |
| `test_create_project_duplicate_name_keeps_the_first` | create project duplicate name keeps the first | Unit | none | ✅ Automated |
| `test_create_project_generates_and_saves_the_bible` | create project generates and saves the bible | Unit | none | ✅ Automated |
| `test_create_project_needs_a_narrative_and_rejects_images_for_now` | create project needs a narrative and rejects images for now | Unit | none | ✅ Automated |
| `test_create_project_removes_the_folder_when_the_bible_fails` | create project removes the folder when the bible fails | Unit | none | ✅ Automated |
| `test_ctx_missing_backend_is_typed_error` | ctx missing backend is typed error | Unit | none | ✅ Automated |
| `test_ctx_opens_project_and_provides_helpers` | ctx opens project and provides helpers | Unit | none | ✅ Automated |
| `test_ctx_providers_are_lazy_and_use_factory` | ctx providers are lazy and use factory | Unit | none | ✅ Automated |
| `test_ctx_unknown_project_raises` | ctx unknown project raises | Unit | none | ✅ Automated |
| `test_edit_bible_is_undoable` | edit bible is undoable | Unit | none | ✅ Automated |
| `test_end_is_picked_when_offered_and_this_strip_reaches_target` | end is picked when offered and this strip reaches target | Unit | none | ✅ Automated |
| `test_end_pick_closes_the_story_at_target` | end pick closes the story at target | Unit | none | ✅ Automated |
| `test_ensure_registered_keeps_a_test_override` | ensure registered keeps a test override | Unit | none | ✅ Automated |
| `test_fake_provider_registers_its_answers_after_clear` | fake provider registers its answers after clear | Unit | none | ✅ Automated |
| `test_get_bible_unknown_project` | get bible unknown project | Unit | none | ✅ Automated |
| `test_ids_injected_clock_and_random_are_deterministic` | ids injected clock and random are deterministic | Unit | none | ✅ Automated |
| `test_ids_monotonic_within_same_millisecond` | ids monotonic within same millisecond | Unit | none | ✅ Automated |
| `test_ids_prefix_validation_and_table` | ids prefix validation and table | Unit | none | ✅ Automated |
| `test_ids_shape_and_alphabet` | ids shape and alphabet | Unit | none | ✅ Automated |
| `test_ids_sort_by_time` | ids sort by time | Unit | none | ✅ Automated |
| `test_llm_anthropic_builds_client_with_key_and_no_sdk_retries` | llm anthropic builds client with key and no sdk retries | Unit | none | ✅ Automated |
| `test_llm_anthropic_corrective_retry_then_failure` | llm anthropic corrective retry then failure | Unit | none | ✅ Automated |
| `test_llm_anthropic_find_api_key_env_then_keyring` | llm anthropic find api key env then keyring | Unit | none | ✅ Automated |
| `test_llm_anthropic_no_tool_call_is_invalid_reply` | llm anthropic no tool call is invalid reply | Unit | none | ✅ Automated |
| `test_llm_anthropic_preflight_reports_missing_sdk_and_key` | llm anthropic preflight reports missing sdk and key | Unit | none | ✅ Automated |
| `test_llm_anthropic_timeout_and_client_errors` | llm anthropic timeout and client errors | Unit | none | ✅ Automated |
| `test_llm_anthropic_transient_errors_retry_once` | llm anthropic transient errors retry once | Unit | none | ✅ Automated |
| `test_llm_anthropic_unknown_exceptions_propagate` | llm anthropic unknown exceptions propagate | Unit | none | ✅ Automated |
| `test_llm_doctor_check_invalid_provider_string_is_reported_not_raised` | llm doctor check invalid provider string is reported not raised | Unit | none | ✅ Automated |
| `test_llm_doctor_check_ollama_ok_missing_and_down` | llm doctor check ollama ok missing and down | Unit | none | ✅ Automated |
| `test_llm_doctor_checks_registered_and_fake_is_not_required` | llm doctor checks registered and fake is not required | Unit | none | ✅ Automated |
| `test_llm_fake_corrupt_fixture_is_an_invalid_reply` | llm fake corrupt fixture is an invalid reply | Unit | none | ✅ Automated |
| `test_llm_fake_embeddings_are_deterministic_unit_vectors` | llm fake embeddings are deterministic unit vectors | Unit | none | ✅ Automated |
| `test_llm_fake_embeddings_shared_words_score_higher` | llm fake embeddings shared words score higher | Unit | none | ✅ Automated |
| `test_llm_fake_no_responder_for_marker_or_without_marker_raises` | llm fake no responder for marker or without marker raises | Unit | none | ✅ Automated |
| `test_llm_fake_responder_exact_version_wins_over_name` | llm fake responder exact version wins over name | Unit | none | ✅ Automated |
| `test_llm_fake_responder_invalid_first_reply_gets_corrective_retry` | llm fake responder invalid first reply gets corrective retry | Unit | none | ✅ Automated |
| `test_llm_fake_responder_selected_by_template_marker_and_call_index` | llm fake responder selected by template marker and call index | Unit | none | ✅ Automated |
| `test_llm_fixtures_dir_resolution_order` | llm fixtures dir resolution order | Unit | none | ✅ Automated |
| `test_llm_get_embeddings_builds_each_kind_and_rejects_anthropic` | llm get embeddings builds each kind and rejects anthropic | Unit | none | ✅ Automated |
| `test_llm_get_llm_builds_each_kind` | llm get llm builds each kind | Unit | none | ✅ Automated |
| `test_llm_non_retryable_4xx_surfaces_without_retry` | llm non retryable 4xx surfaces without retry | Unit | none | ✅ Automated |
| `test_llm_ollama_embeddings_count_mismatch_raises` | llm ollama embeddings count mismatch raises | Unit | none | ✅ Automated |
| `test_llm_ollama_embeddings_posts_input_list_and_normalizes` | llm ollama embeddings posts input list and normalizes | Unit | none | ✅ Automated |
| `test_llm_ollama_missing_content_counts_as_invalid_reply` | llm ollama missing content counts as invalid reply | Unit | none | ✅ Automated |
| `test_llm_ollama_omits_seed_when_none_and_strips_think_block` | llm ollama omits seed when none and strips think block | Unit | none | ✅ Automated |
| `test_llm_ollama_preflight_model_present_missing_and_unreachable` | llm ollama preflight model present missing and unreachable | Unit | none | ✅ Automated |
| `test_llm_ollama_unknown_model_maps_to_model_missing` | llm ollama unknown model maps to model missing | Unit | none | ✅ Automated |
| `test_llm_openai_compat_embeddings_count_mismatch_raises` | llm openai compat embeddings count mismatch raises | Unit | none | ✅ Automated |
| `test_llm_openai_compat_embeddings_ordered_by_index_and_normalized` | llm openai compat embeddings ordered by index and normalized | Unit | none | ✅ Automated |
| `test_llm_openai_compat_empty_choices_is_invalid_reply` | llm openai compat empty choices is invalid reply | Unit | none | ✅ Automated |
| `test_llm_openai_compat_no_auth_header_without_key` | llm openai compat no auth header without key | Unit | none | ✅ Automated |
| `test_llm_openai_compat_preflight` | llm openai compat preflight | Unit | none | ✅ Automated |
| `test_llm_openai_compat_url_comes_from_settings_or_errors` | llm openai compat url comes from settings or errors | Unit | none | ✅ Automated |
| `test_llm_prompt_bad_or_unknown_name_raises` | llm prompt bad or unknown name raises | Unit | none | ✅ Automated |
| `test_llm_prompt_hash_is_canonical_and_input_sensitive` | llm prompt hash is canonical and input sensitive | Unit | none | ✅ Automated |
| `test_llm_prompt_loads_front_matter_and_key` | llm prompt loads front matter and key | Unit | none | ✅ Automated |
| `test_llm_prompt_malformed_files_raise` | llm prompt malformed files raise | Unit | none | ✅ Automated |
| `test_llm_prompt_missing_variable_raises` | llm prompt missing variable raises | Unit | none | ✅ Automated |
| `test_llm_prompt_system_renders_marker_vars_and_audience_rules` | llm prompt system renders marker vars and audience rules | Unit | none | ✅ Automated |
| `test_llm_prompt_variable_values_are_not_re_expanded` | llm prompt variable values are not re expanded | Unit | none | ✅ Automated |
| `test_llm_provider_string_invalid_raises` | llm provider string invalid raises | Unit | none | ✅ Automated |
| `test_llm_record_script_list_and_argument_errors` | llm record script list and argument errors | Unit | none | ✅ Automated |
| `test_llm_record_script_records_selftest_scenario` | llm record script records selftest scenario | Unit | none | ✅ Automated |
| `test_llm_recording_wrapper_writes_replayable_fixture` | llm recording wrapper writes replayable fixture | Unit | none | ✅ Automated |
| `test_llm_retry_gives_up_after_two_attempts_on_429_and_transport_errors` | llm retry gives up after two attempts on 429 and transport errors | Unit | none | ✅ Automated |
| `test_llm_template_of_parses_marker` | llm template of parses marker | Unit | none | ✅ Automated |
| `test_llm_usage_counts_corrective_retry_in_one_call` | llm usage counts corrective retry in one call | Unit | none | ✅ Automated |
| `test_llm_validation_errors_reports_paths_and_non_objects` | llm validation errors reports paths and non objects | Unit | none | ✅ Automated |
| `test_llm_wrap_untrusted_fences_text` | llm wrap untrusted fences text | Unit | none | ✅ Automated |
| `test_llm_wrap_untrusted_strips_delimiter_tokens` | llm wrap untrusted strips delimiter tokens | Unit | none | ✅ Automated |
| `test_make_strip_argument_errors` | make strip argument errors | Unit | none | ✅ Automated |
| `test_make_strip_free_text_and_panel_count` | make strip free text and panel count | Unit | none | ✅ Automated |
| `test_parse_assignments_nests_dotted_keys_and_parses_json` | parse assignments nests dotted keys and parses json | Unit | none | ✅ Automated |
| `test_projects_archive_undo_restores` | projects archive undo restores | Unit | none | ✅ Automated |
| `test_projects_create_duplicate_slug_refused` | projects create duplicate slug refused | Unit | none | ✅ Automated |
| `test_projects_create_empty_name_refused` | projects create empty name refused | Unit | none | ✅ Automated |
| `test_projects_create_invalid_options_leave_no_folder` | projects create invalid options leave no folder | Unit | none | ✅ Automated |
| `test_projects_create_makes_folder_row_branch_and_metadata` | projects create makes folder row branch and metadata | Unit | none | ✅ Automated |
| `test_projects_create_uses_default_audience_and_explicit_audience` | projects create uses default audience and explicit audience | Unit | none | ✅ Automated |
| `test_projects_delete_moves_to_trash` | projects delete moves to trash | Unit | none | ✅ Automated |
| `test_projects_list_hides_archived_by_default` | projects list hides archived by default | Unit | none | ✅ Automated |
| `test_projects_rename_changes_name_not_folder_and_undo_restores` | projects rename changes name not folder and undo restores | Unit | none | ✅ Automated |
| `test_projects_resolve_ambiguous_name_asks_for_id` | projects resolve ambiguous name asks for id | Unit | none | ✅ Automated |
| `test_projects_resolve_by_slug_name_id_and_path` | projects resolve by slug name id and path | Unit | none | ✅ Automated |
| `test_projects_update_metadata_merges_and_undoes` | projects update metadata merges and undoes | Unit | none | ✅ Automated |
| `test_rename_archive_delete_project` | rename archive delete project | Unit | none | ✅ Automated |
| `test_run_auto_is_undoable` | run auto is undoable | Unit | none | ✅ Automated |
| `test_run_auto_one_step_and_resume` | run auto one step and resume | Unit | none | ✅ Automated |
| `test_run_auto_refuses_unapproved_strips_and_missing_bible` | run auto refuses unapproved strips and missing bible | Unit | none | ✅ Automated |
| `test_run_auto_stops_at_target_and_records_actor_auto` | run auto stops at target and records actor auto | Unit | none | ✅ Automated |
| `test_safety_audience_rules_defined_for_all_five_audiences` | safety audience rules defined for all five audiences | Unit | none | ✅ Automated |
| `test_safety_empty_texts_skip_checks_and_unknown_audience_rejected` | safety empty texts skip checks and unknown audience rejected | Unit | none | ✅ Automated |
| `test_schemas_bible_arc_stages_filled_and_checked` | schemas bible arc stages filled and checked | Unit | none | ✅ Automated |
| `test_schemas_book_pages_consecutive` | schemas book pages consecutive | Unit | none | ✅ Automated |
| `test_schemas_character_id_prefix_and_dna_length` | schemas character id prefix and dna length | Unit | none | ✅ Automated |
| `test_schemas_layout_reading_order_must_be_permutation` | schemas layout reading order must be permutation | Unit | none | ✅ Automated |
| `test_schemas_lettering_balloon_must_stay_inside_panel` | schemas lettering balloon must stay inside panel | Unit | none | ✅ Automated |
| `test_schemas_llm_schema_is_inlined_and_plain` | schemas llm schema is inlined and plain | Unit | none | ✅ Automated |
| `test_schemas_llm_schema_still_validates_documents` | schemas llm schema still validates documents | Unit | none | ✅ Automated |
| `test_schemas_moderation_verdict_defaults` | schemas moderation verdict defaults | Unit | none | ✅ Automated |
| `test_schemas_project_info_fields` | schemas project info fields | Unit | none | ✅ Automated |
| `test_schemas_schema_field_has_default_and_is_fixed` | schemas schema field has default and is fixed | Unit | none | ✅ Automated |
| `test_schemas_secondary_documents_roundtrip` | schemas secondary documents roundtrip | Unit | none | ✅ Automated |
| `test_schemas_strip_script_panels_numbered` | schemas strip script panels numbered | Unit | none | ✅ Automated |
| `test_schemas_style_bad_hex_rejected` | schemas style bad hex rejected | Unit | none | ✅ Automated |
| `test_schemas_suggestions_require_three_ordered_options` | schemas suggestions require three ordered options | Unit | none | ✅ Automated |
| `test_schemas_target_strips_bounds` | schemas target strips bounds | Unit | none | ✅ Automated |
| `test_stale_suggestions_are_refused` | stale suggestions are refused | Unit | none | ✅ Automated |
| `test_steer_policy_prefers_steer` | steer policy prefers steer | Unit | none | ✅ Automated |
| `test_story_arc_final_stage_and_target_flag` | story arc final stage and target flag | Unit | none | ✅ Automated |
| `test_story_arc_requires_bible` | story arc requires bible | Unit | none | ✅ Automated |
| `test_story_arc_unlisted_stage_from_model_is_corrected` | story arc unlisted stage from model is corrected | Unit | none | ✅ Automated |
| `test_story_beat_edit_suggestion_rejects_unknown_and_invalid_changes` | story beat edit suggestion rejects unknown and invalid changes | Unit | none | ✅ Automated |
| `test_story_beat_requires_bible_and_passes_guards` | story beat requires bible and passes guards | Unit | none | ✅ Automated |
| `test_story_bible_cast_hints_are_used_as_given` | story bible cast hints are used as given | Unit | none | ✅ Automated |
| `test_story_bible_duplicate_names_get_unique_ids` | story bible duplicate names get unique ids | Unit | none | ✅ Automated |
| `test_story_bible_edit_errors_and_template_change` | story bible edit errors and template change | Unit | none | ✅ Automated |
| `test_story_bible_empty_or_long_narrative_rejected` | story bible empty or long narrative rejected | Unit | none | ✅ Automated |
| `test_story_bible_fit_characters_keeps_known_ids` | story bible fit characters keeps known ids | Unit | none | ✅ Automated |
| `test_story_bible_undo_first_version_removes_bible` | story bible undo first version removes bible | Unit | none | ✅ Automated |
| `test_story_branch_delete_branch_with_story_rejected` | story branch delete branch with story rejected | Unit | none | ✅ Automated |
| `test_story_branch_delete_with_children_or_story_rejected` | story branch delete with children or story rejected | Unit | none | ✅ Automated |
| `test_story_finalize_fake_provider_end_to_end` | story finalize fake provider end to end | Unit | none | ✅ Automated |
| `test_story_finalize_needs_strips_and_bible` | story finalize needs strips and bible | Unit | none | ✅ Automated |
| `test_story_strips_approve_requires_lettered_when_asked` | story strips approve requires lettered when asked | Unit | none | ✅ Automated |
| `test_story_strips_approve_runs_arc_and_locks_edits_until_unapprove` | story strips approve runs arc and locks edits until unapprove | Unit | none | ✅ Automated |
| `test_story_strips_approve_undo_returns_to_scripted` | story strips approve undo returns to scripted | Unit | none | ✅ Automated |
| `test_story_strips_create_is_undoable` | story strips create is undoable | Unit | none | ✅ Automated |
| `test_story_strips_create_stores_scripted_strip_and_panels` | story strips create stores scripted strip and panels | Unit | none | ✅ Automated |
| `test_story_strips_edit_is_undoable_and_restores_stale` | story strips edit is undoable and restores stale | Unit | none | ✅ Automated |
| `test_story_strips_edit_rejects_invalid_and_foreign_cast` | story strips edit rejects invalid and foreign cast | Unit | none | ✅ Automated |
| `test_story_strips_edit_visual_marks_stale_text_does_not` | story strips edit visual marks stale text does not | Unit | none | ✅ Automated |
| `test_story_strips_failed_generation_leaves_no_rows` | story strips failed generation leaves no rows | Unit | none | ✅ Automated |
| `test_story_strips_pick_recorded_and_undone` | story strips pick recorded and undone | Unit | none | ✅ Automated |
| `test_story_strips_resolve_by_index_or_id_and_errors` | story strips resolve by index or id and errors | Unit | none | ✅ Automated |
| `test_story_suggest_end_here_fallback_when_model_omits_it` | story suggest end here fallback when model omits it | Unit | none | ✅ Automated |
| `test_story_suggest_follows_branch_parent_chain` | story suggest follows branch parent chain | Unit | none | ✅ Automated |
| `test_story_suggest_missing_intent_rejected` | story suggest missing intent rejected | Unit | none | ✅ Automated |
| `test_story_suggest_preconditions_and_moderation` | story suggest preconditions and moderation | Unit | none | ✅ Automated |
| `test_story_suggest_unknown_ids_and_stage_are_corrected` | story suggest unknown ids and stage are corrected | Unit | none | ✅ Automated |
| `test_story_writer_fake_provider_end_to_end` | story writer fake provider end to end | Unit | none | ✅ Automated |
| `test_story_writer_panel_violations_cover_sfx_and_caption` | story writer panel violations cover sfx and caption | Unit | none | ✅ Automated |
| `test_story_writer_prompt_carries_cast_limits_audience_and_fences_beat` | story writer prompt carries cast limits audience and fences beat | Unit | none | ✅ Automated |
| `test_story_writer_requires_bible` | story writer requires bible | Unit | none | ✅ Automated |
| `test_suggest_then_pick_writes_a_script_only_strip` | suggest then pick writes a script only strip | Unit | none | ✅ Automated |
| `test_twist_policy_prefers_twist` | twist policy prefers twist | Unit | none | ✅ Automated |
| `test_undo_redo_history` | undo redo history | Unit | none | ✅ Automated |
| `test_undo_with_nothing_to_undo_returns_none` | undo with nothing to undo returns none | Unit | none | ✅ Automated |
| `test_unknown_policy_is_a_usage_error` | unknown policy is a usage error | Unit | none | ✅ Automated |
| `e2e_US002_empty_home_prompts_for_story_idea` | US002 empty home prompts for story idea | E2E | none | ✅ Automated |

---

## 6. Model evaluation protocol

Generation quality cannot be asserted with deterministic unit tests, so each release runs this protocol (Sprint 3 gate for the first measurement, Sprint 6 task S6-T04 for the release round). Results are recorded in `docs/EVALS.md`. The scripted part is automated (`it_eval_*` scenarios); the human part is the rubric below.

### 6.1 Fixture stories

| Story | Seed | Style and audience | Arc | Length |
|---|---|---|---|---|
| Duck (flagship) | `images/duck.jpg` plus `narratives/duck.txt` | picture-book-watercolor, kids-5-8 | problem-try-try-succeed | 8 strips |
| Robot | `narratives/robot.txt` (text only, no photo) | bold-cartoon, kids-9-12 | three-act | 8 strips |
| Newsletter GPU gag | `narratives/gpu-gag.txt` (recurring cast) | newspaper-strip, all-ages | gag-a-day | 8 strips |

Each story runs end to end in auto mode with the steer-heavy policy, then lettering and QA run as in production. Every story runs twice: once with the default local backend (ComfyUI, `qwen-image-edit`) on the GPU runner, and once with Gemini. Fixed seeds are recorded so a regression can be re-run.

### 6.2 Scripted metrics

| Metric | How it is measured | Threshold |
|---|---|---|
| Character consistency (NFR-004) | Vision QA score per character appearance across the 8 strips, after retakes | At least 90 percent of appearances score 4 or higher |
| Model-drawn text (NFR-005) | OCR pass over every approved panel before lettering | Zero panels with detected text |
| Lettering overflow | Placement engine report | Zero balloons outside their panel, zero overlaps |
| Retake rate | Auto retakes per panel | Reported, no threshold; trend tracked across releases |
| Suggestion distinctness | Pairwise embedding similarity of the three options | All pairs under 0.85 |
| Latency (NFR-003) | Wall time for text suggestions and a 4-panel strip | Suggestions under 10 s on a local 14B model; strip under 3 minutes on one 24 GB GPU (local) and under 90 s (cloud) |

### 6.3 Human rubric (each criterion scored 1 to 5)

| Criterion | 1 means | 5 means |
|---|---|---|
| Story coherence | Strips do not connect; threads dropped | Clear setup and payoff; threads resolved |
| Suggestion usefulness | Options repeat or ignore the story so far | Three options that feel different and worth picking |
| Character consistency | Character looks like a different one in several panels | Same character everywhere; only expression and pose change |
| Lettering readability | Balloons hide faces, wrong order, or clipped | Balloons crisp, in reading order, tails point at speakers |

### 6.4 Procedure

1. Build the release candidate and run the three stories per backend; save the exported PDFs and web pages.
2. Run the scripted metrics and write the table to `docs/EVALS.md` (`test_eval_script_writes_evals_md_table`).
3. At least three raters, one of them a parent or caregiver of the target age group, score each story on the rubric after reading it once, without seeing the scores of others.
4. Record each rater's scores, the average per criterion, and free-text notes.
5. Spot check 20 random panels per story against their character sheets and record disagreements with the vision QA scores.

### 6.5 Pass rule

- NFR-004 met for all three stories on the default local backend. A Gemini miss is recorded and investigated but blocks only the cloud badge claim.
- Zero model-drawn text in approved panels (NFR-005).
- Every rubric criterion averages at least 4 of 5 across raters and stories.
- Any miss blocks the release until fixed or the threshold change is argued in a spec change PR.

### 6.6 Scoring sheet template

| Story | Backend | Rater | Coherence | Suggestions | Consistency | Lettering | Notes |
|---|---|---|---|---|---|---|---|
| Duck | local | | | | | | |

---

## 7. Visual regression strategy

- **Surfaces covered:** balloon types (`vis_letter_*`), strips (`vis_strip_*`), layout templates (`vis_template_*`), pages by template and size (`vis_page_*`), and covers (`vis_cover_*`). Names follow `vis_{surface}_{template_or_state}`.
- **Deterministic art:** goldens use the mock image backend, which draws flat-color scenes with labeled shapes, so only the layout, lettering, and rendering code can change a golden.
- **Pinned environment:** bundled fonts only, the Chromium version pinned by Playwright, fixed device scale factor, and a fixed locale. The `visual-regression` CI job runs on ubuntu only.
- **Comparison:** SSIM via scikit-image plus a pixel threshold: a test fails when more than 0.1 percent of pixels differ. Anti-aliasing tolerance is applied per channel before counting.
- **Failure output:** diff images are written to `tests/visual/__diff__/` (gitignored) and uploaded as CI artifacts on failure.
- **Updating goldens:** `scripts/update-goldens.sh` regenerates them with the mock backend. A PR that changes goldens must attach before and after images and explain why; reviewers reject golden changes with no explanation.
- **Preview versus export:** `it_export_chromium_pixel_diff_vs_studio_preview_under_0_1_percent` checks that Studio preview and export use the same renderer (NFR-009).
- **Not covered by goldens:** real model output. Real backends are judged by the consistency QA and the evaluation protocol in section 6, never by pixel comparison.

---

## 8. Smoke checklist for staging

Run on the staging branch build before promoting to main. Automated items run in CI (`smoke`, `e2e-tests`, `gpu-integration`, and `harness-smoke-tests` jobs); manual items need a person.

| # | Check | How | Automated |
|---|---|---|---|
| 1 | Clean install works | `uv tool install .` in a fresh venv; `mr-comic-smith --version` prints the version from `pyproject.toml` | Yes |
| 2 | Doctor passes | `mr-comic-smith doctor` exits 0, `--json` parses | Yes |
| 3 | Mock end to end | `tests/smoke/smoke.sh` produces strips, pages, a PDF, and a web export | Yes |
| 4 | Versions agree | `scripts/check-versions.sh` exits 0 | Yes |
| 5 | Studio loads | Open Studio, create the duck project with mocks, approve the sheet | Yes (E2E) |
| 6 | Studio makes no external requests | Load a project; no network request leaves localhost | Yes (E2E) |
| 7 | Core loop | Pick a suggestion, render, retake one panel, approve, next suggestions appear | Yes (E2E) |
| 8 | Lettering edit | Drag a balloon, reload, position persists | Yes (E2E) |
| 9 | Undo and redo | Undo three edits and redo them | Yes (E2E) |
| 10 | Guards | A denylisted name and a person photo without attestation are both blocked | Yes |
| 11 | PDF quality | Embedded fonts, selectable balloon text, expected page count | Yes |
| 12 | Web export offline | Open the single-file export from `file://` with the network off | Yes |
| 13 | Child mode | Pick a choice, tap Make it, 64 px targets, long press exits | Yes (E2E) |
| 14 | Real LLM story | `suggest` and `strip` with Ollama yield distinct options and valid scripts | Manual (needs Ollama) |
| 15 | ComfyUI render | One panel with two references renders on the GPU machine | Manual (GPU) |
| 16 | Cloud render | One panel renders through Gemini (nightly job or manual with a key) | Manual or nightly |
| 17 | PDF viewers | Open the PDF in Preview, Acrobat, Chrome, and iOS Books | Manual (human) |
| 18 | Browser matrix | Studio and web export in Chrome, Safari, Firefox | Manual (human) |
| 19 | Narration | `mr-audio-smith` narrates the web export | Manual |
| 20 | Harness handshake | MCP stdio handshake and `tools/list` | Yes (staging and release) |
| 21 | Docs build | mkdocs build has no broken links; quickstart commands copy-paste cleanly | Yes |
| 22 | Security scans | gitleaks, pip-audit, npm audit report no high findings | Yes |

Sign-off: staging is promoted only when every automated item is green and every manual item is checked with initials and date in the release PR.

---

## 9. Regression policy and flake policy

### 9.1 Regression policy

- Every bug fixed gets exactly one new regression test in `tests/regression/` (or the matching vitest folder), named `regression_{gh_issue_number}_{what_was_broken}`.
- The test is written first, shown to fail on the buggy code, then the fix is made.
- Regression tests are never deleted. If a feature is removed, the test moves to `tests/regression/archived/` with a comment naming the removal PR, and keeps running if it is still meaningful.
- Generation-quality bugs get a regression test against the deterministic layer that caused them (compiler, QA threshold, placement), never against model output.
- A bug found by an evaluation round, a staging smoke run, or a user report follows the same path.
- A regression test must run in the default CI (unit or integration tier); a GPU-only bug gets a respx-mocked or stub-server reproduction plus a `gpu` marked confirmation test.

Lifecycle:

```
  bug reported / found
         |
         v
  GitHub issue opened (#N, label type: bug)
         |
         v
  failing test written:  regression_N_<what_was_broken>   (RED)
         |
         v
  fix implemented, test passes                            (GREEN)
         |
         v
  PR merged, issue closed with link to the test
         |
         v
  test lives in tests/regression/ forever, runs in every CI
```

### 9.2 Flake policy

- A flaky test is quarantined with `@pytest.mark.flaky_quarantine` and a linked issue within 24 hours, and fixed within the sprint. Never more than 5 tests are quarantined at once.
- Quarantined tests still run on a nightly job and report, but do not gate merges.
- Rerunning a failed CI job until it passes is not a fix; the first flaky failure is logged in the linked issue with the run URL.
- If quarantine would exceed 5 tests, new feature work stops until the count is back under the cap.
- Network, timing, and ordering flakes are fixed by injecting fakes (respx, fake clocks, the mock backend, the stub ComfyUI server), not by increasing timeouts.
- Visual flakes are fixed by pinning fonts, Chromium, and device scale factor, not by raising the pixel threshold.
- A test quarantined past the end of its sprint is escalated to p0 for the next sprint.

