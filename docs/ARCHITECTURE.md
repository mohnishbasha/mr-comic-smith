# mr-comic-smith Architecture

Version: 1.0 (specification for release 1.0.0)
Date: 2026-11-02
Owner: Serverless Ventures LLC
Repository: mohnishbasha/mr-comic-smith
Status: binding v1 specification

This document is the binding architecture for mr-comic-smith. It records the system shape, the decisions behind it, the module boundaries, the database schema, every data format and public contract, and the security and deployment model. Where this document and the PRD disagree on a technical matter, this document wins; where they disagree on product behavior, the PRD wins. Where this document and the original build prompt (`Prompt.md`) disagree, this document wins (ADR-018).

Conventions used throughout:

- "Prompt" means the Master Build Prompt this document was derived from. Names, ids, enums, defaults, ports, env vars, and schema ids are carried over from it unchanged.
- Items marked **(added)** are details this document specifies that the Prompt left implicit. They are binding once this document is committed, and each is traceable to an ADR or an open question in section 14.
- Items marked **verify at implementation time** concern external software whose names, licenses, or resource needs change quickly. See section 13.
- Ports: REST server `7350`, Studio `7351`.

Contents:

1. System overview
2. Decision log
3. Module map
4. Data model (SQLite) and asset store
5. Data formats
6. Pipelines
7. Contracts
8. Job system
9. Caching model
10. Error model
11. Security and safety model
12. Deployment topologies and configuration
13. Backend research notes
14. Open questions

---

## 1. System overview

mr-comic-smith is a local-first comic studio. A user starts from a sentence of narrative, a photo, or both. The system builds an original, consistent cast, writes the next strip with the user, offers three (sometimes four) choices for what happens next, renders panels through a pluggable image backend, letters them as vector SVG, and repeats until the story lands. Finished strips stitch into pages, pages bind into a book, and the book exports as PNG, JPG, WebP, PDF, CBZ, a long strip image, or a self-contained web page.

The library `comic_smith.api` is the core. The CLI, REST server, MCP server, Studio UI, and Pi extension (over REST) are thin front doors over it (ADR-015). Services are the only writers; every mutation is an event in an append-only log. Safety guards sit below every front door (ADR-013). One SVG pipeline renders both Studio preview and exports (ADR-008).

```
                 ┌───────────────────────────── Studio (React + TS) ──────────────────────────────┐
                 │  Story view │ Strip canvas │ Plot choices │ Lettering editor │ Pages │ Book │ Export│
                 └───────────────────────────────┬──────────────────────────────────────────────────┘
                                                 │ REST + WebSocket (events, progress)
 CLI (typer) ─────┐                              v
 MCP (stdio/HTTP)─┼──────────────>  comic_smith.api  (public Python API)
 REST clients ────┘                              │
            ┌──────────────┬─────────────────────┼─────────────────────┬──────────────────┐
            v              v                     v                     v                  v
      story/            cast/                panels/              letter/            layout/ + export/
   bible, arc,      reference ingest,    prompt compiler,     balloon placement,   page templates,
   suggestions,     vision describe,     render jobs,         SVG lettering,       book builder,
   strip writer,    character sheets,    consistency QA,      fonts                PNG/PDF/CBZ/web
   finalize,        originality guard    takes, inpaint                            via Chromium
   moderation
            │              │                     │
            v              v                     v
       LLMProvider    VisionProvider        ImageBackend
   ollama|anthropic| ollama-vl|anthropic| comfyui|gemini|openai|
   openai_compat|fake openai_compat|fake  mock
                                 \            /
                       project.db (SQLite, WAL)  +  assets/ (content-addressed)  +  jobs (SQLite queue)
```

Suggestion distinctness additionally uses an `EmbeddingsProvider` (default `ollama:nomic-embed-text`, `fake` in dev). It is omitted from the diagram above because the diagram is carried over verbatim; it is specified in section 7.8.

### 1.1 Layers

| Layer | Packages | Responsibility |
|---|---|---|
| Front doors | `cli.py`, `server/`, `mcp_server/`, `web/studio/`, `integrations/pi/` | Parse input, call `comic_smith.api`, format output. No business logic, no database access. |
| Facade | `api.py` | Typed public Python API. Wraps services, converts exceptions to `ComicSmithError`, emits events through services. |
| Services | `story/`, `cast/`, `panels/`, `letter/`, `layout/`, `book/`, `export/` | Domain logic. Only writers of project state. Every mutation appends an event. |
| Infrastructure | `db/`, `assets/`, `events.py`, `jobs/`, `config.py`, `errors.py` | SQLite, content-addressed assets, event log and undo, job queue, settings, errors. |
| Adapters | `backends/image/`, `backends/llm/`, `backends/vision/` (and embeddings, section 7.8) | Provider and backend implementations behind small Protocols. All quirks live here. |
| Data | `story/prompts/`, `story/schemas/`, `schemas/`, `cast/presets/`, `cast/denylist.yaml`, `layout/templates/`, `backends/image/workflows/` | Versioned prompts, JSON Schemas, styles, layouts, denylist, workflows. Data, not code. |

### 1.2 Stage responsibilities

| Pipeline | Entry point (`comic_smith.api`) | Core modules | Output |
|---|---|---|---|
| Seed to cast | `add_character`, `generate_sheet`, `approve_character` | `assets.images`, `cast.reference`, `cast.originality`, `cast.sheet`, `cast.dna` | Approved character with sheet assets and visual DNA |
| Beat to strip | `suggest_next`, `make_strip`, `render_strip`, `letter_strip`, `approve_strip` | `story.suggest`, `story.writer`, `story.moderation`, `panels.compiler`, `panels.render`, `panels.qa`, `letter.layout`, `letter.svg` | Approved, lettered strip; bible updated; next suggestions |
| Strip to page | `finalize_story`, `paginate_story` | `story.finalize`, `layout.paginate`, `layout.page` | Page rows and page SVG |
| Book to export | `build_book`, `export` | `book.builder`, `export.chromium`, `export.images`, `export.pdf`, `export.cbz`, `export.web` | PNG/JPG/WebP, PDF, CBZ, long strip, web folder or single file |

### 1.3 Design principles (Appendix I of the Prompt)

1. The story engine never sees pixels; the image layer never writes story. They meet only through Panel Specs and character references.
2. Interfaces are small and capability-flagged. `ImageBackend` has three methods plus capabilities; adding a backend is one adapter, one registry entry, and contract tests.
3. Workflows are data. ComfyUI workflow JSON with named slots lets a new model ship without code changes beyond its manifest.
4. Styles, layouts, arc templates, denylist, and prompts are data, versioned and validated.
5. One renderer. Preview and export share the SVG pipeline.
6. Services own mutations; events own history. No front door writes the database directly.
7. Front doors are thin. CLI, Studio routes, MCP, and Pi call `comic_smith.api` only (import-linter, ADR-015).
8. Safety in core. Guards sit below every front door.
9. Optional extras stay optional. The base install runs the Studio with the mock or a cloud backend; local GPU pieces are separate services.

---

## 2. Decision log

Each record uses Context / Decision / Consequences. ADR-001 to ADR-014 carry the Prompt's decisions verbatim in the Decision field (the Prompt's "Why" lines are preserved under Context). ADR-015 onward were added while writing this document.

### ADR-001: Core in Python 3.12; UI in TypeScript + React

- **Context:** Image generation clients (ComfyUI API, diffusers, cloud SDKs), vision tooling, and PDF and image processing are strongest in Python; the interactive canvas needs a modern web UI. The Serverless Ventures defaults are Tauri, Rust, and a bun-compiled TypeScript CLI. Rejected: a Rust core (would wrap Python model clients anyway).
- **Decision:** Core in Python 3.12; UI in TypeScript + React.
- **Consequences:** Python and TypeScript coding standards replace the Rust and Tauri standards. The CLI is Python plus typer, installed with `uv tool`, in the same process as the services. A bun-compiled TS binary is rejected because it cannot host the Python services. The supported interpreter window is refined in ADR-016.

### ADR-002: Local web app (Studio) served by the CLI, installable as a PWA; no Tauri shell in v1

- **Context:** The same UI works on a laptop, a LAN GPU box, and Kubernetes; classroom mode is free; it avoids bundling a Python sidecar inside a desktop shell.
- **Decision:** Local web app (Studio) served by the CLI, installable as a PWA; no Tauri shell in v1.
- **Consequences:** Rust/Tauri coding standards replaced by Python + TypeScript standards. Desktop app store distribution is deferred (Out of Scope for v1). The built Studio is bundled into the wheel under `comic_smith/server/static/`.

### ADR-003: Image models never draw text; all lettering is vector SVG from the lettering engine

- **Context:** Image models misspell; vector text is crisp, editable, translatable, searchable in PDF, and narratable.
- **Decision:** Image models never draw text. All lettering is vector SVG from the lettering engine.
- **Consequences:** Every compiled image prompt carries a "no text, no letters, no speech bubbles" constraint. An OCR pass (RapidOCR) detects text drawn in the image and flags the take (NFR-005). The compiler reserves balloon space with composition hints. Lettering JSON is the single source for balloons, captions, and SFX (section 5.8).

### ADR-004: Character consistency via approved sheet references, visual DNA, and vision QA with automatic retakes

- **Context:** No single technique is reliable; layered defenses are. Per-character LoRA is slow and deferred.
- **Decision:** Character consistency via an approved character sheet used as reference images on every panel, plus a visual DNA text block, plus a vision-model consistency check with automatic retakes.
- **Consequences:** None of the four layers (sheet references, visual DNA, QA scoring, retakes) may be removed to save time. Backends without reference-image support are degraded and flagged by capability flags. QA results are cached by `H(asset_sha, character_sheet_version, qa_prompt_version)` (section 9).

### ADR-005: Pluggable ImageBackend with capability flags

- **Context:** Local-first with an escape hatch for users without a large GPU; model choice changes fast, workflows absorb that churn. Rejected: direct diffusers pipelines (re-implements what ComfyUI maintains); cloud-only (privacy).
- **Decision:** Pluggable ImageBackend with capability flags (reference images, max references, edit/inpaint, seed control, sizes). Default local backend is ComfyUI driven by bundled workflow templates; default cloud backend is Gemini image generation; OpenAI images as a second cloud option; mock for tests.
- **Consequences:** The Studio disables features a backend lacks rather than failing. A new model ships as a workflow JSON plus manifest. Contract tests run against every backend, with `mock` as the reference implementation.

### ADR-006: Default local workflow is Qwen-Image-Edit; FLUX.1 Kontext [dev] is opt-in

- **Context:** Qwen-Image-Edit is expected to be Apache-2.0 and supports reference-conditioned editing. FLUX.1 Kontext [dev] weights are expected to be under a non-commercial license.
- **Decision:** Default local workflow uses Qwen-Image-Edit (Apache-2.0) for reference-conditioned panels. FLUX.1 Kontext [dev] workflow is shipped but opt-in because its weights are under a non-commercial license. Verify both licenses and VRAM needs at implementation time.
- **Consequences:** `COMIC_SMITH_ALLOW_NONCOMMERCIAL=false` gates `flux-kontext-dev`. Opting in is recorded in project metadata and in export metadata (NFR-011). Section 13 holds the verification checklist.

### ADR-007: Story engine writes structured JSON validated against JSON Schemas

- **Context:** Free prose parsed later is brittle and injectable.
- **Decision:** The story engine writes structured JSON (Panel Specs, Plot Suggestions) validated against JSON Schemas, never free-form prose that is parsed later.
- **Consequences:** `LLMProvider.complete_json` takes a schema. One corrective retry on validation failure, then `SchemaValidationError` (exit 5). Prompt-injected instructions cannot change output structure.

### ADR-008: One renderer for preview and export

- **Context:** Pixel parity between preview and export (NFR-009) is easiest to guarantee by construction.
- **Decision:** One renderer for preview and export: pages are SVG documents (panel art as images, lettering as text with embedded fonts) rendered by headless Chromium via Playwright for PNG and PDF. Studio preview uses the same SVG.
- **Consequences:** WYSIWYG fidelity (NFR-009) by construction. Chromium is a required runtime dependency for export, installed by `doctor --fix`. Fonts are embedded as data URIs in every SVG.

### ADR-009: SQLite per project plus a content-addressed asset store

- **Context:** Projects are portable folders; zip a folder to share it. Rejected: Postgres (overkill for local-first).
- **Decision:** SQLite (SQLAlchemy 2 + Alembic) per project plus a content-addressed asset store.
- **Consequences:** WAL mode, atomic asset writes, and a project lock file protect against corruption (NFR-006). Migrations ship with every schema change and run with a backup (section 4.3).

### ADR-010: Append-only event log per project

- **Context:** Undo, history, and an auto-mode audit trail all need the same record of what changed.
- **Decision:** Append-only event log per project powers undo/redo, history, and auto-mode audit.
- **Consequences:** Every mutation is an event with an `inverse_json`. An action that cannot be undone needs a confirmation and a reason in the spec. Event types are enumerated in section 4.4.

### ADR-011: Job queue in SQLite; one GPU worker plus text workers; Redis deferred

- **Context:** Single-machine and single-replica deployment is the v1 target; a broker adds operational weight.
- **Decision:** Job queue in SQLite with a single GPU worker and a pool of text workers; progress over WebSocket. Redis deferred.
- **Consequences:** The Helm chart runs `comic-smith` as a single-replica StatefulSet in v1. Details in section 8.

### ADR-012: Default LLM and vision via Ollama

- **Context:** Local-first default with optional cloud providers.
- **Decision:** LLM default Ollama (qwen3:14b class) for story; vision default Ollama with a Qwen2.5-VL class model; Anthropic and OpenAI-compatible optional for both.
- **Consequences:** Provider strings select implementations (ADR-017). Model tags are verified at implementation time (section 13). A 0.6B qwen3 is used in CI.

### ADR-013: Safety guards live in core services

- **Context:** A guard in the UI alone is bypassed by the CLI, REST, or an agent.
- **Decision:** Safety guards (originality, people attestation, audience) live in core services, so CLI, REST, MCP, and Studio inherit them.
- **Consequences:** No flag disables a guard in v1 (NFR-012). Blocked content is explained in plain words. Exit code 4 is reserved for safety blocks.

### ADR-014: Web export embeds data-narrate markup

- **Context:** mr-audio-smith can narrate a web page; a comic exported as web should be narratable with no integration layer.
- **Decision:** Web export embeds data-narrate markup so mr-audio-smith can narrate books without an integration layer.
- **Consequences:** Balloon, caption, and alt text are real DOM text in the reader with `data-narrate` attributes (order, speaker, kind). Changing those attributes is a MAJOR change (reader attributes are part of the public contract per Versioning).

### ADR-015: import-linter enforces thin front doors **(added)**

- **Context:** Appendix C of the Prompt makes `comic_smith.api` the core and the front doors thin, enforced in CI. Without enforcement the CLI and routes drift into calling services and the database directly, and guards and events get bypassed.
- **Decision:** An `import-linter` contract runs in CI. `comic_smith.cli`, `comic_smith.server`, and `comic_smith.mcp_server` may import only `comic_smith.api`, `comic_smith.errors`, and schema models (the pydantic models under `comic_smith.story.schemas` and the generated format models). Direct imports of `comic_smith.db`, `comic_smith.story`, `comic_smith.cast`, `comic_smith.panels`, `comic_smith.letter`, `comic_smith.layout`, `comic_smith.book`, `comic_smith.export`, `comic_smith.backends`, and `comic_smith.jobs` from those three packages fail the build. The Pi extension is TypeScript and reaches the system only over REST.
- **Consequences:** Anything a front door needs must be exposed through `api.py` first. `api.py` stays a facade of short functions; logic that creeps in moves to services. Layered contracts: `api` may import services; services may import infrastructure and adapters; adapters import nothing above themselves; no service imports `api`.

### ADR-016: Python 3.12 and 3.13 support window **(added)**

- **Context:** ADR-001 names Python 3.12; the dependency block in the Prompt sets `requires-python = ">=3.12,<3.14"`. Pillow, numpy, pikepdf, and Playwright publish wheels for both.
- **Decision:** The supported range is `>=3.12,<3.14`. Development targets 3.12; CI runs the unit and integration suites on 3.12 and 3.13. `mypy --strict` runs on 3.12. Python 3.14 is not supported until a release lifts the upper bound and CI passes.
- **Consequences:** No syntax or stdlib feature newer than 3.12 is used. Upper-bound lifts are a MINOR change when no behavior changes. Docker images use Python 3.12.

### ADR-017: Provider string format **(added)**

- **Context:** The Environment Model uses strings such as `ollama:qwen3:14b`, `ollama:qwen2.5vl:7b`, and `ollama:nomic-embed-text` for `COMIC_SMITH_LLM`, `COMIC_SMITH_VISION`, and `COMIC_SMITH_EMBEDDINGS`. Model tags themselves contain colons.
- **Decision:** A provider string is `<provider>[:<model>]`, split on the first colon only. The remainder is the model tag, passed verbatim. Valid provider ids: `ollama`, `anthropic`, `openai_compat`, `fake` for LLM and vision; `ollama`, `openai_compat`, `fake` for embeddings. `fake` takes no model. `openai_compat` reads its base URL from `COMIC_SMITH_OPENAI_COMPAT_URL` and its key from `OPENAI_API_KEY` **(added)**. An empty provider, an unknown provider id, or a missing model for a provider that requires one is a `UsageError` (exit 2) at config load. Image backends are selected by bare id (`COMIC_SMITH_IMAGE_BACKEND`, `--backend`): `comfyui`, `gemini`, `openai`, `mock`.
- **Consequences:** `parse_provider_string(s) -> ProviderRef(provider, model)` is the only parser. Example: `ollama:qwen3:14b` gives provider `ollama`, model `qwen3:14b`. Provider and model are both part of LLM cache keys.

### ADR-018: Spec documents supersede the build prompt **(added)**

- **Context:** The Prompt states that once `docs/PRD.md`, `docs/ARCHITECTURE.md`, and `docs/DESIGN.md` exist they are the source of truth.
- **Decision:** After the first commit of the five spec documents, `Prompt.md` is historical input. Disagreements resolve in favor of the spec documents. Changes to a spec document follow the Spec Change Protocol (a PR that labels its spec impact, updates the doc, and notes the change in CHANGELOG when user-visible). Items in this document marked **(added)** are binding; items in section 14 are not yet decided.
- **Consequences:** Implementers cite section numbers of this document, not the Prompt, in issues and PRs. Where the executing agent finds that a backend's real behavior differs from section 13, the finding is recorded in section 13 (Implementation Note 9) and the adapter changes, not the interface.

### ADR-019: Lettering geometry is panel-relative and normalized **(added)**

- **Context:** Panels render at different pixel sizes for preview, 300 dpi export, and web. Absolute pixel positions would break on resize or retake with a different size.
- **Decision:** Lettering JSON stores balloon, caption, and SFX geometry as fractions in `[0, 1]` of the panel's width and height, origin top-left. Rotation is degrees clockwise. Font size is stored as a fraction of panel height. The SVG renderer converts to units at render time.
- **Consequences:** Retakes keep the lettering valid. Placement can be re-run after a take change. Golden tests compare SVG text, not pixel-rounded values.

### ADR-020: Health endpoints are served at both `/healthz` and `/v1/healthz` **(added)**

- **Context:** The Prompt lists `GET /healthz | /readyz` unversioned in the REST table, but the version table says the Studio About dialog reads `/v1/healthz`, and S7-T01 publishes OpenAPI at `/v1/openapi.json`.
- **Decision:** `/healthz` and `/readyz` (for probes and Kubernetes) and `/v1/healthz` and `/v1/readyz` (for clients) both exist and return identical bodies. `/v1/healthz` includes `version`.
- **Consequences:** Probes stay stable if the API prefix changes. The OpenAPI document covers both.

### ADR-021: Single-writer SQLite and a project lock file **(added)**

- **Context:** ADR-009 and ADR-011 put project state and the queue in SQLite. Two processes opening the same project for writing (for example CLI `render` while the server runs) risks conflicting workers.
- **Decision:** Opening a project for write takes an advisory lock on `{project_dir}/project.lock`. If another process holds it, the CLI forwards the command to the running server when one is reachable, otherwise exits 8 ("project locked"). Read-only commands (`doctor`, `suggest --json` with a cached set, `export` of an existing book) do not need the lock except `export`, which writes assets.
- **Consequences:** Kubernetes runs a single replica of `comic-smith` in v1. Classroom mode (many users) runs inside one server process, with per-user workspaces in the same instance.

---

## 3. Module map

### 3.1 Python package `comic_smith/`

| Path | Responsibility |
|---|---|
| `__init__.py` | Exposes `__version__` via `importlib.metadata.version("mr-comic-smith")`. |
| `api.py` | Public Python API: thin typed facade over services; the only module front doors import. |
| `cli.py` | typer app; parses flags, calls `api`, prints output, the only module allowed to `sys.exit` or `print`. |
| `config.py` | pydantic-settings configuration with env prefix `COMIC_SMITH_`, TOML loading, provider-string parsing. |
| `doctor.py` | Environment checks (Python, GPU and VRAM, backends, providers, fonts, Chromium, disk) with fix hints and `--fix`. |
| `errors.py` | `ComicSmithError` hierarchy with `code`, `stage`, `message`, `hint`, `retryable`, exit-code mapping, RFC 9457 conversion. |
| `events.py` | Append-only event log, inverse events, undo and redo, history queries. |
| `db/models.py` | SQLAlchemy 2 typed mappings for every table in section 4. |
| `db/session.py` | Engine and session factory, WAL pragmas, project lock handling. |
| `db/migrations/` | Alembic environment and versioned revisions; backup-before-migrate hook. |
| `assets/store.py` | Content-addressed store: put, get, exists, atomic write, reference scan, garbage collection. |
| `assets/images.py` | Image ingest: magic-byte sniffing, HEIC conversion, EXIF and XMP strip, re-encode, downscale, pixel limit. |
| `story/bible.py` | Create, edit, and version the story bible; open-thread bookkeeping. |
| `story/arc.py` | Arc templates, stage tracking, arc progress computation. |
| `story/suggest.py` | Plot suggestions (continue, twist, steer, optional end here) plus distinctness check via embeddings. |
| `story/writer.py` | Beat to strip script: produces Panel Specs, one corrective retry on schema failure; normalizes custom beats. |
| `story/finalize.py` | Continuity review, title and blurb suggestions, story lock and reopen. |
| `story/moderation.py` | Audience guard for text (beats, scripts, compiled prompts). |
| `story/prompts/` | Versioned prompt templates (`*.md`); template version is part of cache keys. |
| `story/schemas/` | Packaged copies of `panel_spec.json`, `suggestion.json`, `bible.json` and generated pydantic models. |
| `cast/reference.py` | Vision describe of references, person detection, structured reference JSON. |
| `cast/sheet.py` | Character sheet generation (views and expressions), per-view regenerate, approval. |
| `cast/dna.py` | Visual DNA paragraph generation and validation. |
| `cast/originality.py` | Denylist check on text and compiled prompts; resemblance check on approved sheets. |
| `cast/styles.py` | Style preset loading, validation, custom preset creation, preview grid. |
| `cast/denylist.yaml` | Configurable starter denylist of copyrighted characters, franchises, and artist styles. |
| `cast/presets/*.yaml` | Built-in style presets (six). |
| `panels/compiler.py` | Deterministic Panel Spec to `ImageRequest` compilation with balloon-space hints. |
| `panels/render.py` | Render job orchestration, seeds, takes, QA-driven retakes, take selection. |
| `panels/qa.py` | Consistency scoring against the sheet checklist and OCR detection of drawn text. |
| `panels/edit.py` | Inpaint with mask, non-destructive crop and reframe. |
| `letter/layout.py` | Balloon placement algorithm (avoid character boxes, reading order, tail targets, auto font size). |
| `letter/svg.py` | Balloon shapes (speech, thought, shout, whisper), tails, captions, SFX as XML-escaped SVG. |
| `letter/fonts.py` | Font registry, subsetting, and data-URI embedding. |
| `letter/fonts/` | Bundled OFL fonts (Comic Neue, Bangers, Atkinson Hyperlegible, Inter). |
| `layout/templates.py` | Load and validate page and strip layout templates. |
| `layout/templates/*.yaml` | The six layout templates. |
| `layout/paginate.py` | Strips to pages, respecting strip boundaries unless allowed. |
| `layout/page.py` | Page SVG composition from slots, panels, lettering, borders, captions. |
| `book/builder.py` | Book model, cover, title page, dedication, chapters, table of contents, back cover. |
| `export/chromium.py` | Playwright lifecycle: offline, fresh profile, per-page timeout, route blocking. |
| `export/images.py` | PNG, JPG, WebP at 72, 150, 300 dpi; long strip; automatic upscale step. |
| `export/pdf.py` | Screen and print PDF, bleed, trim marks, metadata, selectable text (pikepdf post-processing). |
| `export/cbz.py` | CBZ packaging of page images with ComicInfo metadata. |
| `export/web.py` | Static web folder and single-file reader with base64 assets, `data-narrate` markup, alt text. |
| `backends/image/base.py` | `ImageBackend` Protocol, `ImageCapabilities`, `ImageRequest`, `GeneratedImage`. |
| `backends/image/registry.py` | Backend registry and lookup by id; capability queries. |
| `backends/image/comfyui.py` | ComfyUI HTTP and WebSocket client; workflow slot filling; interrupt. |
| `backends/image/gemini.py` | Gemini image generation adapter (multi-reference). |
| `backends/image/openai_images.py` | OpenAI image generation and masked edit adapter. |
| `backends/image/mock.py` | Deterministic mock backend for tests and dev. |
| `backends/image/workflows/` | `qwen-image-edit.json`, `flux-kontext-dev.json`, `sdxl-ipadapter.json` with manifests. |
| `backends/llm/base.py` | `LLMProvider` Protocol. |
| `backends/llm/ollama.py` | Ollama JSON-schema-constrained completion. |
| `backends/llm/anthropic.py` | Anthropic adapter (optional extra). |
| `backends/llm/openai_compat.py` | OpenAI-compatible adapter (vLLM, LM Studio, OpenAI). |
| `backends/llm/fake.py` | Deterministic fake for tests. |
| `backends/vision/base.py` | `VisionProvider` Protocol. |
| `backends/vision/ollama_vl.py` | Ollama vision adapter. |
| `backends/vision/anthropic.py` | Anthropic vision adapter. |
| `backends/vision/openai_compat.py` | OpenAI-compatible vision adapter. |
| `backends/vision/fake.py` | Deterministic fake. |
| `backends/embeddings/` **(added)** | `base.py` (`EmbeddingsProvider` Protocol), `ollama.py`, `openai_compat.py`, `fake.py`; used by suggestion distinctness. |
| `cache/keys.py` **(added)** | Canonical-JSON SHA-256 key functions for every cache (section 9.1). |
| `jobs/queue.py` | Enqueue, claim (`UPDATE ... RETURNING`), cancel, requeue on crash. |
| `jobs/worker.py` | Worker loops: one GPU worker, N text workers, cloud-image concurrency. |
| `jobs/progress.py` | Progress reporting that feeds `job.progress` events. |
| `server/app.py` | FastAPI application factory, middleware, static Studio mount. |
| `server/routes/` | One router module per resource group; calls `api` only. |
| `server/ws.py` | WebSocket `/v1/events` fan-out. |
| `server/auth.py` | Bearer token, access code, session cookie, CSRF token, Origin check, rate limits. |
| `server/static/` | Built Studio assets (copied in at build time). |
| `mcp_server/server.py` | MCP server bootstrap (stdio and streamable HTTP). |
| `mcp_server/tools.py` | The 12 MCP tools, calling `api` only. |

### 3.2 Repository structure (Appendix B)

| Path | Responsibility |
|---|---|
| `.agent/skills/run-tests/{SKILL.md,run.sh}` | Agent skill: run the test suite. |
| `.agent/skills/check-types/{SKILL.md,run.sh}` | Agent skill: run mypy and ruff. |
| `.agent/skills/make-fixture-comic/{SKILL.md,run.sh}` | Agent skill: build the fixture duck comic with the mock backend. |
| `.github/ISSUE_TEMPLATE/{task.yml,bug.yml,generation-quality.yml}` | Issue forms. |
| `.github/PULL_REQUEST_TEMPLATE.md` | PR template with spec-impact choice. |
| `.github/dependabot.yml` | Dependency update policy. |
| `.github/workflows/ci.yml` | Lint, typecheck, unit, integration, visual, e2e, smoke. |
| `.github/workflows/release.yml` | Tag-driven build, sign, SBOM, publish. |
| `.github/workflows/docs.yml` | mkdocs build and deploy. |
| `.github/workflows/gpu-integration.yml` | GPU-runner integration tests with ComfyUI and Ollama. |
| `.github/workflows/nightly-cloud.yml` | Nightly cloud-backend smoke tests. |
| `web/studio/` | React + TypeScript + Vite Studio. |
| `web/studio/package.json`, `vite.config.ts`, `index.html` | Studio build configuration. |
| `web/studio/src/app/` | App shell, routing, providers. |
| `web/studio/src/api/` | Generated OpenAPI types (committed) and the typed client. |
| `web/studio/src/stores/` | Zustand stores (`useProjectStore`, `useStripStore`, `useLetteringStore`). |
| `web/studio/src/views/{Home,Story,Cast,Strips,Pages,Book,Export}/` | One folder per Studio view. |
| `web/studio/src/components/` | Shared accessible components. |
| `web/studio/src/lettering/` | Pure SVG lettering components driven by lettering JSON. |
| `web/studio/src/kid/` | Child mode components. |
| `web/studio/src/styles/tokens.css` | Design tokens (`--cs-*`). |
| `reader/` | `@mr-comic-smith/reader` web component with zero runtime dependencies. |
| `reader/src/reader.ts` | Custom element, mode switching, keyboard handling. |
| `reader/src/flipbook.ts` | Flipbook mode (page or spread, swipe, counter). |
| `reader/src/scroll.ts` | Vertical scroll mode. |
| `reader/src/balloons.ts` | Balloon, caption, SFX DOM rendering with `data-narrate`. |
| `reader/src/styles.css` | Shadow DOM styles using CSS custom properties. |
| `integrations/pi/` | Pi extension (`package.json`, `src/{index,tools,commands}.ts`) over REST. |
| `integrations/goose/toolkit.yaml` | Goose toolkit config. |
| `integrations/opencode/opencode.json.example` | OpenCode MCP config example. |
| `integrations/claude-code/{README.md,skill/SKILL.md}` | Claude Code skill. |
| `charts/mr-comic-smith/{Chart.yaml,values.yaml,values-k3s-gpu.yaml,templates/}` | Helm chart. |
| `deploy/docker/{Dockerfile.cpu,Dockerfile.cuda,Dockerfile.comfyui}` | Container builds. |
| `deploy/docker-compose.local.yml`, `deploy/docker-compose.prod.yml` | Compose topologies. |
| `docs/{PRD,ARCHITECTURE,DESIGN,SPRINT_PLAN,TEST_PLAN}.md` | The five spec documents. |
| `docs/{RETROSPECTIVES,EVALS,SECURITY_REVIEW}.md` | Sprint retros, evaluation results, safety review. |
| `docs/guide/`, `docs/reference/` | User guide and reference for the docs site. |
| `examples/duck-book/` | Project made with mock art plus README. |
| `examples/newsletter-gag-a-day/` | Gag-a-day newsletter example. |
| `schemas/{bible,suggestions,panel,character,layout,book}.schema.json` | Published JSON Schemas (section 5.10). |
| `scripts/check-versions.sh`, `bump-version.sh`, `extract-changelog.sh` | Version and changelog tooling (Versioning section). |
| `scripts/create-issues.py`, `check-coverage.py`, `gen-api-types.sh`, `update-goldens.sh` | Issue creation, coverage thresholds, OpenAPI type generation, golden refresh. |
| `tests/{unit,integration,smoke,e2e,visual,regression,fixtures}/` | Test tree. |
| `.coverage-thresholds.toml` | Per-package coverage floors. |
| `.env.dev.example`, `.env.stage.example`, `.env.prod.example` | Environment examples (section 12.3). |
| `.gitignore`, `.gitattributes`, `.editorconfig`, `.pre-commit-config.yaml` | Repository hygiene. |
| `AGENTS.md`, `CLAUDE.md`, `SKILLS.md`, `SOUL.md` | Agent repository files. |
| `CHANGELOG.md`, `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, `SECURITY.md` | Project policy files. |
| `LICENSE`, `THIRD_PARTY_LICENSES.md`, `README.md` | MIT license, dependency/model/font licenses, readme. |
| `Makefile`, `mkdocs.yml`, `pyproject.toml`, `uv.lock` | Build and lock files. |
| `comic-smith.toml.example` | Example config file (section 12.2). |

### 3.3 Coding constraints that shape the map

- `mypy --strict` clean; pydantic v2 for every format, config, and API payload; SQLAlchemy 2 typed mappings.
- Functions under 50 lines, modules under 400 lines; `sys.exit` and `print` only in `cli.py`; structured logs via `structlog`.
- Subprocess with argument arrays and timeouts only; `shell=True` forbidden. Paths via `pathlib`; user-derived file names through `safe_slug()`; writes through `atomic_write()`.
- I/O boundaries (LLM, vision, embeddings, image backend, clock, filesystem, browser) are injectable so unit tests never touch network or GPU.
- Async only at the server and MCP edges and in streaming backends; core services are sync with executor bridging.
- Named constants for tunables, for example `DEFAULT_TAKES = 2`, `QA_MIN_SCORE = 4`.

---

## 4. Data model (SQLite) and asset store

Each project is a folder with its own `project.db` (SQLite in WAL mode) and an `assets/` directory (ADR-009). The tables below are the contract. Column names and the table list come from the Prompt; the full types, nullability, constraints, and indexes are specified here **(added)**. Columns the Prompt did not name are marked `-- added`.

General rules:

- Primary keys are text ids with a type prefix and a ULID body, for example `prj_01J...`, except `asset.id` (the SHA-256 hex digest) and `event.id` (integer). Characters and styles also accept human slugs as ids when created by a built-in or the library (`ch_puddle`, `st_picture_book_watercolor`).
- Timestamps are ISO 8601 UTC text (`2026-11-02T14:03:05Z`).
- Booleans are `INTEGER` with `CHECK (x IN (0,1))`.
- JSON columns are `TEXT` holding validated JSON (`CHECK (json_valid(col))`). The owning service validates the JSON against its JSON Schema before writing.
- Enums are `TEXT` with a `CHECK ... IN (...)` constraint. The enum lists are in section 4.2.
- Pragmas on every connection: `journal_mode=WAL`, `synchronous=NORMAL`, `foreign_keys=ON`, `busy_timeout=5000`.
- Services are the only writers; every write happens in a transaction that also appends an event row.

### 4.1 Schema

```sql
-- project: one row per project database (this db belongs to exactly one project)
CREATE TABLE project (
  id              TEXT PRIMARY KEY,                       -- prj_<ulid>
  name            TEXT NOT NULL,
  slug            TEXT NOT NULL,                          -- added; folder name via safe_slug()
  created_at      TEXT NOT NULL,
  updated_at      TEXT NOT NULL,
  audience        TEXT NOT NULL DEFAULT 'all-ages'
                  CHECK (audience IN ('all-ages','kids-5-8','kids-9-12','teen','adult')),
  style_id        TEXT NULL REFERENCES style(id) DEFERRABLE INITIALLY DEFERRED,
  schema_version  INTEGER NOT NULL,                       -- Alembic head number at last migration
  archived        INTEGER NOT NULL DEFAULT 0 CHECK (archived IN (0,1)),   -- added (FR-001)
  noncommercial_opt_in INTEGER NOT NULL DEFAULT 0 CHECK (noncommercial_opt_in IN (0,1)), -- added
  metadata_json   TEXT NOT NULL DEFAULT '{}' CHECK (json_valid(metadata_json))            -- added
);

-- bible: versioned story bible; highest version per project is current
CREATE TABLE bible (
  id          TEXT PRIMARY KEY,                           -- bib_<ulid>
  project_id  TEXT NOT NULL REFERENCES project(id) ON DELETE CASCADE,
  version     INTEGER NOT NULL CHECK (version >= 1),
  json        TEXT NOT NULL CHECK (json_valid(json)),     -- schema comic-smith/bible@1
  created_at  TEXT NOT NULL,
  UNIQUE (project_id, version)
);
CREATE INDEX ix_bible_project_version ON bible(project_id, version DESC);

CREATE TABLE character (
  id              TEXT PRIMARY KEY,                       -- ch_<slug or ulid>
  project_id      TEXT NOT NULL REFERENCES project(id) ON DELETE CASCADE,
  slug            TEXT NOT NULL,
  name            TEXT NOT NULL,
  source          TEXT NOT NULL CHECK (source IN ('photo','text','library')),
  reference_json  TEXT NULL CHECK (reference_json IS NULL OR json_valid(reference_json)),
  visual_dna      TEXT NULL,                              -- one paragraph; set when sheet approved
  sheet_asset_ids TEXT NOT NULL DEFAULT '{}' CHECK (json_valid(sheet_asset_ids)),
                                                          -- JSON object, see 5.4 (views and expressions)
  approved        INTEGER NOT NULL DEFAULT 0 CHECK (approved IN (0,1)),
  person_attested INTEGER NOT NULL DEFAULT 0 CHECK (person_attested IN (0,1)),
  library_ref     TEXT NULL,                              -- library item id + version, e.g. "lib_01J...@3"
  approved_at     TEXT NULL,                              -- added
  originality_json TEXT NULL CHECK (originality_json IS NULL OR json_valid(originality_json)), -- added
  sheet_version   INTEGER NOT NULL DEFAULT 0,             -- added; bumps on every approved-sheet change (QA cache key)
  UNIQUE (project_id, slug)
);
CREATE INDEX ix_character_project ON character(project_id);

CREATE TABLE style (
  id          TEXT PRIMARY KEY,                           -- st_<slug>
  project_id  TEXT NULL REFERENCES project(id) ON DELETE CASCADE,  -- NULL for built-ins
  name        TEXT NOT NULL,
  preset_json TEXT NOT NULL CHECK (json_valid(preset_json)),       -- schema comic-smith/style@1
  builtin     INTEGER NOT NULL DEFAULT 0 CHECK (builtin IN (0,1))
);
CREATE INDEX ix_style_project ON style(project_id);

CREATE TABLE branch (
  id               TEXT PRIMARY KEY,                      -- br_<ulid>
  project_id       TEXT NOT NULL REFERENCES project(id) ON DELETE CASCADE,
  name             TEXT NOT NULL,
  parent_branch_id TEXT NULL REFERENCES branch(id),
  fork_strip_id    TEXT NULL REFERENCES strip(id) DEFERRABLE INITIALLY DEFERRED,
  active           INTEGER NOT NULL DEFAULT 0 CHECK (active IN (0,1)),
  UNIQUE (project_id, name)
);
-- exactly one active branch per project
CREATE UNIQUE INDEX ux_branch_one_active ON branch(project_id) WHERE active = 1;

CREATE TABLE strip (
  id          TEXT PRIMARY KEY,                           -- sp_<ulid>
  project_id  TEXT NOT NULL REFERENCES project(id) ON DELETE CASCADE,
  branch_id   TEXT NOT NULL REFERENCES branch(id) ON DELETE CASCADE,
  idx         INTEGER NOT NULL CHECK (idx >= 1),          -- 1-based position within the branch
  beat_json   TEXT NOT NULL CHECK (json_valid(beat_json)),         -- see 5.6 Beat
  arc_stage   TEXT NOT NULL,                              -- one of the template's stages
  status      TEXT NOT NULL DEFAULT 'scripted'
              CHECK (status IN ('scripted','rendering','rendered','lettered','approved')),
  created_at  TEXT NOT NULL,
  approved_at TEXT NULL,                                  -- added
  UNIQUE (branch_id, idx)
);
CREATE INDEX ix_strip_project_branch ON strip(project_id, branch_id, idx);
CREATE INDEX ix_strip_status ON strip(status);

CREATE TABLE panel (
  id               TEXT PRIMARY KEY,                      -- pn_<ulid>
  strip_id         TEXT NOT NULL REFERENCES strip(id) ON DELETE CASCADE,
  idx              INTEGER NOT NULL CHECK (idx >= 1 AND idx <= 6),
  spec_json        TEXT NOT NULL CHECK (json_valid(spec_json)),    -- schema comic-smith/panel@1
  selected_take_id TEXT NULL REFERENCES take(id) DEFERRABLE INITIALLY DEFERRED,
  stale            INTEGER NOT NULL DEFAULT 0 CHECK (stale IN (0,1)),
  lettering_json   TEXT NULL CHECK (lettering_json IS NULL OR json_valid(lettering_json)), -- see 5.8
  crop_json        TEXT NULL CHECK (crop_json IS NULL OR json_valid(crop_json)),           -- {x,y,w,h} fractions
  UNIQUE (strip_id, idx)
);
CREATE INDEX ix_panel_strip ON panel(strip_id, idx);

CREATE TABLE take (
  id          TEXT PRIMARY KEY,                           -- tk_<ulid>
  panel_id    TEXT NOT NULL REFERENCES panel(id) ON DELETE CASCADE,
  asset_id    TEXT NOT NULL REFERENCES asset(id),
  seed        INTEGER NULL,
  backend     TEXT NOT NULL,                              -- image backend id
  model       TEXT NOT NULL,                              -- workflow or model id
  prompt_json TEXT NOT NULL CHECK (json_valid(prompt_json)),       -- compiled ImageRequest, secrets excluded
  qa_json     TEXT NULL CHECK (qa_json IS NULL OR json_valid(qa_json)),
  created_at  TEXT NOT NULL
);
CREATE INDEX ix_take_panel ON take(panel_id, created_at);
CREATE INDEX ix_take_asset ON take(asset_id);

CREATE TABLE suggestion_set (
  id                TEXT PRIMARY KEY,                     -- ss_<ulid>
  project_id        TEXT NOT NULL REFERENCES project(id) ON DELETE CASCADE,
  branch_id         TEXT NOT NULL REFERENCES branch(id) ON DELETE CASCADE,
  after_strip_id    TEXT NULL REFERENCES strip(id),       -- NULL means "after the bible"
  json              TEXT NOT NULL CHECK (json_valid(json)),        -- schema comic-smith/suggestions@1
  chosen_idx        INTEGER NULL CHECK (chosen_idx IS NULL OR chosen_idx BETWEEN 0 AND 3),
  custom_beat_json  TEXT NULL CHECK (custom_beat_json IS NULL OR json_valid(custom_beat_json)),
  created_at        TEXT NOT NULL
);
CREATE INDEX ix_suggestion_branch ON suggestion_set(project_id, branch_id, created_at DESC);

CREATE TABLE story (
  id              TEXT PRIMARY KEY,                       -- sy_<ulid>
  project_id      TEXT NOT NULL REFERENCES project(id) ON DELETE CASCADE,
  branch_id       TEXT NOT NULL REFERENCES branch(id),
  title           TEXT NOT NULL,
  blurb           TEXT NOT NULL DEFAULT '',
  finalized_at    TEXT NULL,
  continuity_json TEXT NULL CHECK (continuity_json IS NULL OR json_valid(continuity_json)),  -- see 5.7
  version         INTEGER NOT NULL DEFAULT 1 CHECK (version >= 1),
  UNIQUE (branch_id, version)
);
CREATE INDEX ix_story_project ON story(project_id);

CREATE TABLE book (
  id            TEXT PRIMARY KEY,                         -- bk_<ulid>
  project_id    TEXT NOT NULL REFERENCES project(id) ON DELETE CASCADE,
  title         TEXT NOT NULL,
  subtitle      TEXT NULL,
  author        TEXT NULL,
  year          INTEGER NULL,
  language      TEXT NOT NULL DEFAULT 'en',               -- BCP 47
  settings_json TEXT NOT NULL DEFAULT '{}' CHECK (json_valid(settings_json))  -- see 5.9
);
CREATE INDEX ix_book_project ON book(project_id);

CREATE TABLE page (
  id            TEXT PRIMARY KEY,                         -- pg_<ulid>
  project_id    TEXT NOT NULL REFERENCES project(id) ON DELETE CASCADE,
  book_id       TEXT NULL REFERENCES book(id) ON DELETE SET NULL,
  idx           INTEGER NOT NULL CHECK (idx >= 1),
  kind          TEXT NOT NULL CHECK (kind IN ('story','cover','title','dedication','cast','back','custom')),
  layout_id     TEXT NOT NULL,                            -- layout template id (see 5.5)
  size          TEXT NOT NULL,                            -- page size key (see 5.5)
  slots_json    TEXT NOT NULL CHECK (json_valid(slots_json)),      -- [{slot_id, ref_type, ref_id, crop?}]
  captions_json TEXT NOT NULL DEFAULT '[]' CHECK (json_valid(captions_json)),
  story_id      TEXT NULL REFERENCES story(id)            -- added; chapter membership for kind='story'
);
CREATE INDEX ix_page_book_idx ON page(book_id, idx);
CREATE INDEX ix_page_project ON page(project_id);

CREATE TABLE export (
  id           TEXT PRIMARY KEY,                          -- ex_<ulid>
  project_id   TEXT NOT NULL REFERENCES project(id) ON DELETE CASCADE,
  target       TEXT NOT NULL CHECK (target IN ('page','story','book')),
  format       TEXT NOT NULL CHECK (format IN ('png','jpg','webp','pdf','cbz','web','strip')),
  options_json TEXT NOT NULL DEFAULT '{}' CHECK (json_valid(options_json)),
  asset_ids    TEXT NOT NULL DEFAULT '[]' CHECK (json_valid(asset_ids)),
  created_at   TEXT NOT NULL,
  target_id    TEXT NULL,                                 -- added; page, story, or book id
  job_id       TEXT NULL REFERENCES job(id)               -- added
);
CREATE INDEX ix_export_project ON export(project_id, created_at DESC);

CREATE TABLE event (
  id           INTEGER PRIMARY KEY AUTOINCREMENT,
  project_id   TEXT NOT NULL,
  ts           TEXT NOT NULL,
  actor        TEXT NOT NULL CHECK (actor IN ('user','auto','agent')),
  type         TEXT NOT NULL,                             -- dotted name, see 4.4
  payload_json TEXT NOT NULL CHECK (json_valid(payload_json)),
  inverse_json TEXT NULL CHECK (inverse_json IS NULL OR json_valid(inverse_json)),
  undone       INTEGER NOT NULL DEFAULT 0 CHECK (undone IN (0,1)),    -- added; redo/undo cursor
  discarded    INTEGER NOT NULL DEFAULT 0 CHECK (discarded IN (0,1)),  -- added (Sprint 0); redo tail dropped by a newer mutation
  workspace_id TEXT NULL                                  -- added; classroom mode user attribution
);
CREATE INDEX ix_event_project_id ON event(project_id, id);
CREATE INDEX ix_event_type ON event(project_id, type);

CREATE TABLE job (
  id            TEXT PRIMARY KEY,                         -- jb_<ulid>
  project_id    TEXT NOT NULL,
  kind          TEXT NOT NULL,                            -- see 8.2
  status        TEXT NOT NULL DEFAULT 'queued'
                CHECK (status IN ('queued','running','done','failed','cancelled')),
  priority      INTEGER NOT NULL DEFAULT 0 CHECK (priority BETWEEN 0 AND 9),
  payload_json  TEXT NOT NULL CHECK (json_valid(payload_json)),
  progress      REAL NOT NULL DEFAULT 0 CHECK (progress >= 0 AND progress <= 1),
  error_json    TEXT NULL CHECK (error_json IS NULL OR json_valid(error_json)),  -- ComicSmithError dict
  created_at    TEXT NOT NULL,
  started_at    TEXT NULL,
  finished_at   TEXT NULL,
  attempts      INTEGER NOT NULL DEFAULT 0,               -- added; retry counter (max 2 retries)
  worker_class  TEXT NOT NULL DEFAULT 'text'              -- added: 'gpu' | 'text' | 'cloud_image' | 'export'
                CHECK (worker_class IN ('gpu','text','cloud_image','export')),
  cancel_requested INTEGER NOT NULL DEFAULT 0 CHECK (cancel_requested IN (0,1)), -- added
  workspace_id  TEXT NULL                                 -- added; fairness key in classroom mode
);
CREATE INDEX ix_job_claim ON job(status, worker_class, priority, created_at);
CREATE INDEX ix_job_project ON job(project_id, created_at DESC);

CREATE TABLE asset (
  id         TEXT PRIMARY KEY,                            -- sha256 hex of stored bytes
  mime       TEXT NOT NULL,                               -- image/png, image/jpeg, image/webp, application/pdf, application/zip, text/html
  width      INTEGER NULL,                                -- NULL for non-image assets
  height     INTEGER NULL,
  bytes      INTEGER NOT NULL CHECK (bytes >= 0),
  origin     TEXT NOT NULL CHECK (origin IN ('upload','render','export','derived')),
  created_at TEXT NOT NULL
);
CREATE INDEX ix_asset_origin ON asset(origin);
```

#### Additional tables **(added)**

These support features the Prompt names (classroom mode in S7-T02, caching in the Caching model) without listing the tables.

```sql
-- workspace: per-user workspace in classroom (LAN) mode; absent rows mean single-user
CREATE TABLE workspace (
  id         TEXT PRIMARY KEY,                            -- ws_<ulid>
  name       TEXT NOT NULL,                               -- chosen at join
  created_at TEXT NOT NULL,
  last_seen  TEXT NOT NULL,
  UNIQUE (name)
);
-- (in classroom mode project ownership is project.metadata_json.workspace_id; sharing is
--  metadata_json.shared_with = [workspace_id...])

-- cache_entry: JSON result cache for LLM and vision-QA outputs (section 9)
CREATE TABLE cache_entry (
  key        TEXT PRIMARY KEY,                            -- sha256 hex, see 9.1
  kind       TEXT NOT NULL CHECK (kind IN ('llm','vision_qa','embedding','compiled_prompt')),
  value_json TEXT NOT NULL CHECK (json_valid(value_json)),
  created_at TEXT NOT NULL,
  hits       INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX ix_cache_kind ON cache_entry(kind, created_at);

-- alembic_version is created and managed by Alembic.
```

The user library (cast and style library, FR-027) lives outside any project in `{COMIC_SMITH_DATA_DIR}/library/library.db` with tables `library_item(id, kind ENUM('character','style'), name, version INTEGER, payload_json, created_at)` and its own assets directory. Importing copies the character or style (and its sheet assets by hash) into the project and records `character.library_ref = "<id>@<version>"`.

### 4.2 Enums

| Enum | Values | Where |
|---|---|---|
| audience | `all-ages`, `kids-5-8`, `kids-9-12`, `teen`, `adult` | `project.audience`, bible, style filters |
| character.source | `photo`, `text`, `library` | `character.source` |
| strip.status | `scripted`, `rendering`, `rendered`, `lettered`, `approved` | `strip.status` |
| page.kind | `story`, `cover`, `title`, `dedication`, `cast`, `back`, `custom` | `page.kind` |
| export.target | `page`, `story`, `book` | `export.target` |
| export.format | `png`, `jpg`, `webp`, `pdf`, `cbz`, `web`, `strip` | `export.format` |
| event.actor | `user`, `auto`, `agent` | `event.actor` |
| job.status | `queued`, `running`, `done`, `failed`, `cancelled` | `job.status` (the Prompt names `queued`; the rest are added) |
| asset.origin | `upload`, `render`, `export`, `derived` | `asset.origin` |
| arc template | `three-act`, `heros-journey-lite` **(Sprint 1)**, `problem-try-try-succeed`, `gag-a-day`, `mystery` | bible `arc.template` |
| suggestion intent | `continue`, `twist`, `steer`, `end` | suggestion option `intent` (the fourth option is `end`, section 5.2) |
| auto policy | `balanced`, `steer`, `twist` | `auto --policy` |
| style preset (builtin) | `picture-book-watercolor`, `bold-cartoon`, `manga-ink`, `newspaper-strip`, `soft-3d-clay`, `pixel-art` | `style.id` suffix, `st_<slug with underscores>` |
| layout template | `strip-stack`, `classic-three-tier`, `grid-2x2`, `grid-3x3`, `splash-plus-two`, `vertical-scroll` | `page.layout_id` |
| page size key | `us-comic` (6.625 x 10.25 in), `us-letter`, `a4`, `square` (8.5 x 8.5 in), `web` | `page.size`, `--size` |

### 4.3 Asset store, migration, and backup policy

#### Project folder layout

```
{COMIC_SMITH_DATA_DIR}/
  projects/
    {slug}/
      project.db            SQLite database (WAL)
      project.db-wal        WAL file (transient)
      project.db-shm        shared memory file (transient)
      project.db.bak-{version}   pre-migration backups (kept until the user deletes them)
      project.lock          advisory lock file (ADR-021)
      assets/
        ab/
          abcdef...{64 hex}.png        {sha256[0:2]}/{sha256}.{ext}
      exports/              user-facing export copies (also stored as assets with origin='export')
      .trash/               deleted-project staging when no OS trash is available
  library/
    library.db
    assets/
  workspaces/               classroom mode metadata (added)
```

#### Asset rules

- Path: `assets/{sha256[0:2]}/{sha256}.{ext}` where `ext` is derived from `mime` (`png`, `jpg`, `webp`, `pdf`, `zip`, `html`). The `asset` row id equals the digest of the stored bytes.
- Assets are immutable and never overwritten. A `put` of existing bytes is a no-op that returns the existing row. Writes go to a temporary file in `assets/.tmp/` and move into place with `os.replace` (`atomic_write()`).
- Uploads are re-encoded before hashing (EXIF and XMP stripped, HEIC converted, images over 4096 px on the long edge downscaled), so the stored hash is of re-encoded pixels, not the original upload.
- Duplicating a project copies `project.db` and hard-links or copies assets by hash (content-addressed, FR-001).
- Garbage collection (`mr-comic-smith gc <project>`): the set of live ids is the union of `character.sheet_asset_ids`, `take.asset_id`, `export.asset_ids`, style reference images in `style.preset_json`, `book.settings_json` cover asset, and `page.slots_json` crops. Unreferenced assets whose `created_at` is older than 24 hours are removed (the grace period protects in-flight jobs). `gc --dry-run` lists what would be removed **(added)**. Takes that are not selected are kept so users can switch takes; they are not garbage.
- HTTP serving: `GET /v1/assets/{sha}` is immutable (`Cache-Control: public, max-age=31536000, immutable`), served with `Content-Type` from the asset row and `X-Content-Type-Options: nosniff`.

#### Migration policy

1. `project.schema_version` is the Alembic revision number at the last successful migration. Every release that changes the database ships an Alembic revision (Versioning).
2. Opening a project whose `schema_version` is below the code's head: acquire the project lock, run `PRAGMA wal_checkpoint(TRUNCATE)`, make a consistent copy with the SQLite online backup API to `project.db.bak-{version}` where `{version}` is the project's pre-migration `schema_version` **(added; see section 14 question 1)**, then run Alembic upgrade in one transaction. On failure, restore from the backup and fail with `ProjectMigrationError` (exit 8).
3. Opening a project whose `schema_version` is above the code's head is refused (`ProjectMigrationError`, exit 8, hint: upgrade mr-comic-smith). Downgrade is not supported; the backup file is the downgrade path.
4. Migration tests: each release's CI migrates a fixture project created by the previous release (release checklist item) and compares row counts and a content hash of asset references.
5. Prompt templates carry their own versions and are not part of the schema; changing them is a PATCH.
6. Backups are not auto-deleted. `doctor` warns when more than three backups exist or they exceed 1 GB.

### 4.4 Event types **(added)**

Event `type` strings are dotted names. `payload_json` holds the new state or a diff; `inverse_json` holds what is needed to reverse it (absent for non-undoable events such as `job.finished`).

| Group | Types |
|---|---|
| project | `project.created`, `project.renamed`, `project.archived`, `project.settings_changed` |
| bible | `bible.created`, `bible.edited` (new version), `bible.thread_opened`, `bible.thread_closed`, `bible.arc_advanced`; **(Sprint 1)** `bible.updated` (sets one version's JSON, or deletes that version when `json` is null; replaces the five types above), `strip.arc_tagged` (sets `strip.arc_stage`) |
| cast | `character.added`, `character.reference_edited`, `character.sheet_generated`, `character.view_regenerated`, `character.approved`, `character.unapproved`, `character.imported`, `style.created`, `style.selected` |
| story | `suggestions.generated` **(Sprint 1: implemented as `suggestions.created`, inverse `suggestions.discarded`)**, `beat.chosen`, `beat.custom`, `strip.scripted`, `strip.edited`, `strip.approved`, `strip.unapproved`, `branch.created`, `branch.switched`, `branch.deleted`, `story.finalized`, `story.reopened` |
| panels | `panel.spec_edited`, `panel.marked_stale`, `panel.take_added`, `panel.take_selected`, `panel.edited` (inpaint), `panel.cropped`, `panel.qa_flagged`, `panel.lettering_edited` |
| pages | `pages.paginated`, `page.layout_changed`, `page.slot_moved`, `page.caption_edited`, `book.page_added`, `book.page_moved`, `book.page_removed`, `book.cover_set`, `book.settings_edited` |
| export | `export.created` |
| jobs | `job.enqueued`, `job.finished`, `job.failed`, `job.cancelled` |
| auto | `auto.started`, `auto.pick`, `auto.stopped` |

**Story core deviations (Sprint 1):**
- Bible versions use one event, `bible.updated`, payload `{id, project_id, version, json, created_at}`. Saving version N has the inverse "same payload with `json: null`", which deletes version N, so the previous version becomes current again; redo re-inserts it. Threads opened or closed by a strip approval are stored by saving a new bible version (no separate thread events). A bible version is only saved on approval when the thread list changed.
- The current arc stage is not stored on the bible: it is the `arc_stage` of the latest approved strip on the branch (`story/arc.py: arc_state`). `arc_progress(bible, strips_count, stage=None)` is strips over target without a stage (and always for `gag-a-day`), otherwise the mean of `(stage index + 1) / stage count` and strips over target, clamped to 0..1. Closed threads stay in `open_threads` with `closed_in_strip` set; "open" means `closed_in_strip is null`.
- `generate_bible` asks the LLM for a `BibleDraft` (no character ids, no arc, no style). Without `cast_hints` it derives provisional ids `ch_<slug of name>`; they are reconciled with the `character` table when characters are created (Sprint 2). The `style_id` comes from project metadata.
- Suggestion options are normalized after the model answers: options are put in continue, twist, steer order, unknown character ids are dropped (the first cast member is the fallback), and an unlisted `arc_stage` is replaced by the current stage. When the model omits `end_here` at the final stage, a default end option is built. A still-similar set after one regeneration is returned and logged as `distinctness_warning` (the `SuggestionSet` model has no warning field).
- Temperature 0 calls (arc update, beat normalization, moderation) are not yet cached in `cache_entry` (section 9); no cache module exists yet.
- Moderation (`story/moderation.py`) runs the denylist first (`cast/denylist.yaml`, `version: 1`, rules `{id, kind, patterns}`, case-insensitive whole-word matching, no override), then the `moderation` prompt. A verdict the model cannot produce in valid form blocks the text (fail closed). Audience rule text lives in `story/prompts/audience_rules.yaml`.
- Offline answers for `COMIC_SMITH_LLM=fake` are in `story/fake_responses.py`; importing `comic_smith.story` registers them. `clear_fake_responders()` also removes them, so tests call `fake_responses.register_all()` again.

Undo and redo operate on the most recent event with a non-null `inverse_json` whose `undone` flag is 0 (undo) or 1 (redo), restricted to the actor's workspace in classroom mode. A new undoable mutation after an undo discards the redo tail by setting `discarded = 1` on those events **(Sprint 0)**; non-undoable events such as `job.finished` leave the redo tail alone. Redo re-applies the oldest undone event (undo walks newest to oldest). Each undo and redo also appends a marker event, `event.undone` or `event.redone`, with payload `{event_id, via}` and no inverse **(Sprint 0)**. An `inverse_json` is `{"type": <event type>, "payload": {...}}`, an event of a known type applied through the same handler registry **(Sprint 0)**. Undo never deletes assets; it only changes references.

---

## 5. Data formats

All formats are pydantic v2 models in the code with JSON Schemas generated from them and published under `schemas/` (section 5.10). Every document carries a `schema` field with its id; readers reject unknown major versions. Field-table conventions: `T` is the JSON type, "Req" is required.

### 5.1 Story Bible (`comic-smith/bible@1`)

```json
{
  "schema": "comic-smith/bible@1",
  "working_title": "Puddle, the Duck Who Would Not Swim",
  "logline": "A little rubber duck who is afraid of water must cross the bathtub to save a friend.",
  "premise": "Puddle lives on the edge of a bathtub and watches the bath toys play...",
  "audience": "kids-5-8",
  "tone": ["gentle", "funny", "brave"],
  "setting": {"world": "a family bathroom at bath time", "rules": ["toys come alive when no adult looks"]},
  "cast": [
    {"character_id": "ch_puddle", "role": "protagonist", "want": "stay dry", "need": "trust friends"},
    {"character_id": "ch_sub", "role": "friend", "want": "explore the drain", "need": "listen"}
  ],
  "themes": ["courage", "friendship"],
  "arc": {"template": "problem-try-try-succeed", "target_strips": 8,
          "stages": ["setup", "problem", "try-1", "try-2", "dark-moment", "success", "home"]},
  "open_threads": [{"id": "t1", "text": "Sub drifts toward the drain", "opened_in_strip": 2}],
  "style_id": "st_picture_book_watercolor"
}
```

| Field | T | Req | Constraints |
|---|---|---|---|
| `schema` | string | yes | Const `comic-smith/bible@1`. |
| `working_title` | string | yes | 1 to 120 chars. |
| `logline` | string | yes | 1 to 300 chars; one sentence. |
| `premise` | string | yes | 1 to 2000 chars. |
| `audience` | string enum | yes | `all-ages`, `kids-5-8`, `kids-9-12`, `teen`, `adult`. |
| `tone` | string[] | yes | 1 to 6 items, each 1 to 30 chars. |
| `setting` | object | yes | `world` (string, 1 to 300), `rules` (string[], 0 to 10). |
| `cast` | object[] | yes | 1 to 12 items; each: `character_id` (string, must exist in `character` table), `role` (string: `protagonist`, `friend`, `antagonist`, `mentor`, `supporting`; open set allowed), `want` (string, 0 to 200), `need` (string, 0 to 200). |
| `themes` | string[] | no, default `[]` | 0 to 8 items. |
| `arc` | object | yes | `template` (enum, see 4.2), `target_strips` (integer 1 to 40), `stages` (string[], 1 to 12; must equal the template's stage list unless template is `gag-a-day`, whose list is empty). |
| `open_threads` | object[] | no, default `[]` | Each: `id` (string, unique), `text` (string, 1 to 200), `opened_in_strip` (integer >= 1), `closed_in_strip` (integer or null, default null) **(added)**. |
| `style_id` | string | yes | Must exist in `style` (built-in or project). |

Arc templates and stages **(added)**: `problem-try-try-succeed` = setup, problem, try-1, try-2, dark-moment, success, home; `three-act` = act1-setup, act1-turn, act2-rise, midpoint, act2-fall, act3-climax, resolution; `heros-journey-lite` **(Sprint 1: apostrophe dropped)** = ordinary-world, call, threshold, trials, ordeal, return; `mystery` = hook, clue-1, clue-2, red-herring, reveal, resolution; `gag-a-day` = no stages. Stage lists live in `story/arc.py` data and are validated.

### 5.2 Plot Suggestion set (`comic-smith/suggestions@1`)

```json
{
  "schema": "comic-smith/suggestions@1",
  "after_strip": 3,
  "arc_progress": 0.42,
  "options": [
    {"intent": "continue", "beat": "Puddle builds a raft from a soap dish",
     "description": "Puddle refuses to swim but has an idea. The raft wobbles.",
     "arc_stage": "try-1", "characters": ["ch_puddle"], "thumbnail_prompt": "..."},
    {"intent": "twist", "beat": "The bathtub plug is pulled",
     "description": "A whirlpool forms. Sub is pulled toward the drain.",
     "arc_stage": "problem", "characters": ["ch_puddle", "ch_sub"], "thumbnail_prompt": "..."},
    {"intent": "steer", "beat": "Grandma Sponge teaches Puddle to float",
     "description": "An old sponge shows Puddle that ducks are made to float.",
     "arc_stage": "try-2", "characters": ["ch_puddle", "ch_sponge"], "thumbnail_prompt": "..."}
  ],
  "end_here": null
}
```

| Field | T | Req | Constraints |
|---|---|---|---|
| `schema` | string | yes | Const `comic-smith/suggestions@1`. |
| `after_strip` | integer or null | yes | Strip `idx` the set follows; `0` or null means "after the bible". |
| `arc_progress` | number | yes | 0.0 to 1.0 inclusive (UI shows percent). |
| `options` | object[] | yes | Exactly 3, with intents `continue`, `twist`, `steer` in that order. |
| `options[].intent` | string enum | yes | `continue`, `twist`, `steer`. |
| `options[].beat` | string | yes | One line, 1 to 100 chars. |
| `options[].description` | string | yes | Two sentences, 1 to 300 chars. |
| `options[].arc_stage` | string | yes | A stage of the bible's arc template. |
| `options[].characters` | string[] | yes | 1 to 6 character ids, each in the cast. |
| `options[].thumbnail_prompt` | string | yes | 1 to 400 chars; no dialogue text. |
| `end_here` | object or null | yes | Null unless the arc is in its final stage or the target length is reached; then an option object with `intent: "end"` and `arc_stage` of the final stage (the "fourth option"). |

Distinctness rule (FR-011): embeddings of `beat + " " + description` for the three options must have pairwise cosine similarity below 0.85 (`SUGGESTION_MAX_SIMILARITY = 0.85`); on failure the LLM is called once more, and the second result is used with a `distinctness_warning` logged if it still fails. `chosen_idx` in `suggestion_set` is 0 to 2 for options and 3 for `end_here`.

### 5.3 Panel Spec (`comic-smith/panel@1`)

```json
{
  "schema": "comic-smith/panel@1",
  "idx": 2,
  "shot": "medium",
  "angle": "eye-level",
  "setting": "bathtub edge, warm evening light, bubbles",
  "characters": [
    {"id": "ch_puddle", "position": "left", "pose": "leaning over the edge",
     "expression": "scared", "facing": "right"},
    {"id": "ch_sub", "position": "right", "pose": "waving from the water",
     "expression": "happy", "facing": "left"}
  ],
  "action": "Sub waves Puddle into the water; Puddle clutches the tub edge.",
  "dialogue": [
    {"speaker": "ch_sub", "type": "speech", "text": "Jump in! It's warm!"},
    {"speaker": "ch_puddle", "type": "whisper", "text": "Ducks don't do deep."}
  ],
  "caption": null,
  "sfx": [{"text": "SPLISH", "near": "ch_sub"}],
  "continuity": ["Puddle wears the red bandana from strip 1"],
  "mood": "playful tension",
  "balloon_space": "top"
}
```

| Field | T | Req | Constraints |
|---|---|---|---|
| `schema` | string | yes | Const `comic-smith/panel@1`. |
| `idx` | integer | yes | 1 to 6; matches `panel.idx`. |
| `shot` | string enum | yes | `extreme-wide`, `wide`, `medium`, `close-up`, `extreme-close-up` **(enum added; Prompt shows `medium`)**. |
| `angle` | string enum | yes | `eye-level`, `high`, `low`, `birds-eye`, `dutch` **(enum added; Prompt shows `eye-level`)**. |
| `setting` | string | yes | 1 to 300 chars. |
| `characters` | object[] | yes | 0 to 5 items. Each: `id` (cast id), `position` (`left`, `center`, `right`, `foreground`, `background`), `pose` (1 to 120), `expression` (`neutral`, `happy`, `sad`, `surprised`, `angry`, `scared`, plus free text up to 30 chars), `facing` (`left`, `right`, `camera`). |
| `action` | string | yes | 1 to 300 chars; also the web export alt text source (FR-025). |
| `dialogue` | object[] | yes (may be empty) | Each: `speaker` (cast id; must exist), `type` (`speech`, `thought`, `shout`, `whisper`), `text` (1 to 200 chars). Per-audience limits (FR-013): `kids-5-8` max 10 words per balloon, max 2 balloons per panel. |
| `caption` | string or null | yes | Narration box text, 1 to 160 chars, or null. |
| `sfx` | object[] | yes (may be empty) | Each: `text` (1 to 20 chars), `near` (cast id or null). |
| `continuity` | string[] | yes (may be empty) | 0 to 8 notes, each 1 to 160 chars. |
| `mood` | string | yes | 1 to 60 chars. |
| `balloon_space` | string enum | yes | `top`, `bottom`, `left`, `right`, `none`. |

Validation also checks: every speaker and `near` id is in the bible cast; total words per strip within the audience limit (limits table in `story/moderation.py` data); panels per strip 1 to 6.

### 5.4 Character (`comic-smith/character@1`)

```json
{
  "schema": "comic-smith/character@1",
  "id": "ch_puddle",
  "slug": "puddle",
  "name": "Puddle",
  "source": "photo",
  "reference": {
    "subject": "rubber duck",
    "palette": ["#F5D547", "#E8622C", "#FFFFFF"],
    "features": ["round body", "orange beak", "painted black eyes"],
    "accessories": ["red bandana"]
  },
  "visual_dna": "A small round yellow rubber duck with a bright orange beak, ...",
  "sheet": {
    "views": {"front": "<sha256>", "side": "<sha256>", "three_quarter": "<sha256>"},
    "expressions": {"neutral": "<sha256>", "happy": "<sha256>", "sad": "<sha256>",
                    "surprised": "<sha256>", "angry": "<sha256>", "scared": "<sha256>"},
    "composed": "<sha256>"
  },
  "approved_at": "2026-11-02T15:10:00Z",
  "attestation": null,
  "originality": {"denylist": "pass", "resemblance": "pass", "checked_at": "2026-11-02T15:10:30Z"}
}
```

| Field | T | Req | Constraints |
|---|---|---|---|
| `schema` | string | yes | Const `comic-smith/character@1`. |
| `id` | string | yes | Prefix `ch_`; unique in project. |
| `slug` | string | yes | Output of `safe_slug()`. |
| `name` | string | yes | 1 to 60 chars. |
| `source` | string enum | yes | `photo`, `text`, `library`. |
| `reference` | object or null | yes | Null for text-only characters. Fields: `subject` (string), `palette` (hex string[], 1 to 8, pattern `^#[0-9A-Fa-f]{6}$`), `features` (string[], 1 to 12), `accessories` (string[], 0 to 8). All user-editable (FR-003). |
| `visual_dna` | string or null | yes | One paragraph (50 to 800 chars) of invariant features; null until the sheet is approved. |
| `sheet.views` | object | yes | Keys `front`, `side`, `three_quarter`; values asset ids (sha256). |
| `sheet.expressions` | object | yes | Keys `neutral`, `happy`, `sad`, `surprised`, `angry`, `scared`. |
| `sheet.composed` | string or null | yes | Asset id of the composed sheet. |
| `approved_at` | string (date-time) or null | yes | Null until approved. |
| `attestation` | object or null | yes | Required (non-null) when the reference contains a person: `{"person_detected": true, "right_to_use_likeness": true, "attested_at": "..."}`. |
| `originality` | object | yes | `denylist` and `resemblance` each `pass`, `blocked`, or `pending`; `rule` (string, the triggering rule when blocked); `checked_at` (date-time). |

### 5.5 Style preset, Layout template

#### Style preset (`comic-smith/style@1`) **(added schema id)**

```yaml
schema: comic-smith/style@1
id: st_picture_book_watercolor
name: Picture book watercolor
description: Soft washes, gentle outlines, warm paper tones.
audiences: [all-ages, kids-5-8, kids-9-12]
positive_tokens: ["children's picture book illustration", "watercolor", "soft edges"]
negative_tokens: ["photorealistic", "text", "letters", "watermark"]
palette_hints: ["#F5E9D4", "#8FB8DE", "#E8A87C"]
line_weight: medium            # thin | medium | bold | none
photoreal: false               # photoreal presets are disabled for characters derived from people
lettering: {case: mixed, font: comic-neue, caption_font: atkinson-hyperlegible}
backend_params:
  comfyui: {cfg: 4.0, steps: 28}
  gemini: {}
  openai: {}
reference_assets: []           # 0 to 2 asset ids of user-owned style references (custom presets only)
```

| Field | T | Req | Constraints |
|---|---|---|---|
| `schema`, `id`, `name` | string | yes | Const id; id prefix `st_`; name 1 to 60. |
| `description` | string | no | 0 to 200. |
| `audiences` | string[] | no, default all | Subset of audience enum. |
| `positive_tokens`, `negative_tokens` | string[] | yes | 1 to 20 items each. Negative tokens always include the no-text constraint (ADR-003). |
| `palette_hints` | hex string[] | no | 0 to 8. |
| `line_weight` | string enum | yes | `thin`, `medium`, `bold`, `none`. |
| `photoreal` | boolean | yes | When true, unavailable for person-derived characters (FR-007). |
| `lettering` | object | yes | `case`: `upper` or `mixed` (upper for `bold-cartoon` and `newspaper-strip`); `font`, `caption_font`: font registry ids. |
| `backend_params` | object | no | Per-backend parameter overrides; unknown keys are ignored by other backends. |
| `reference_assets` | string[] | no | 0 to 2 asset ids. |

#### Layout template (`comic-smith/layout@1`)

```yaml
schema: comic-smith/layout@1
id: strip-stack
name: Strip stack
sizes: [us-comic, us-letter, a4, square]
margins: {top: 0.5, right: 0.5, bottom: 0.5, left: 0.5}     # units: inches
gutter: 0.125
bleed: 0.125
reading_order: [s1, s2, s3]
slots:
  - {id: s1, x: 0.5, y: 0.5,  w: 5.625, h: 2.9, accepts: strip, border: {style: solid, width_pt: 2}}
  - {id: s2, x: 0.5, y: 3.5,  w: 5.625, h: 2.9, accepts: strip}
  - {id: s3, x: 0.5, y: 6.5,  w: 5.625, h: 2.9, accepts: strip}
```

| Field | T | Req | Constraints |
|---|---|---|---|
| `schema`, `id`, `name` | string | yes | Const `comic-smith/layout@1`; id one of the six built-ins or a user id. |
| `sizes` | string[] | yes | Subset of page size keys; slot geometry is expressed for the first listed size and scaled for the others by the template's `scale` rule (default: uniform fit). |
| `page_size` | object | no | Overrides for custom sizes: `{w, h, unit: "in"}`. |
| `margins` | object | yes | `top`, `right`, `bottom`, `left` numbers >= 0 in `unit` (default inches). |
| `gutter` | number | yes | >= 0. |
| `bleed` | number | yes | >= 0; print export default 0.125 in. |
| `slots` | object[] | yes | 1 to 12. Each: `id` (unique), `x`, `y`, `w`, `h` (numbers in page units, within the page minus margins), `accepts` (`panel`, `strip`), `border` (optional `{style: solid|none|dashed, width_pt}`). |
| `reading_order` | string[] | yes | Permutation of slot ids; left to right, top to bottom unless the template says otherwise. |

Page size table **(added)**: `us-comic` 6.625 x 10.25 in; `us-letter` 8.5 x 11 in; `a4` 8.27 x 11.69 in; `square` 8.5 x 8.5 in; `web` unitless fluid width with `vertical-scroll` only.

### 5.6 Beat

A beat is the unit chosen from suggestions or normalized from free text. It is stored in `strip.beat_json` and `suggestion_set.custom_beat_json`.

```json
{
  "schema": "comic-smith/beat@1",
  "source": "suggestion",
  "intent": "continue",
  "beat": "Puddle builds a raft from a soap dish",
  "description": "Puddle refuses to swim but has an idea. The raft wobbles.",
  "arc_stage": "try-1",
  "characters": ["ch_puddle"],
  "panels": 4,
  "original_text": null
}
```

| Field | T | Req | Constraints |
|---|---|---|---|
| `schema` | string | yes | Const `comic-smith/beat@1` **(added schema id)**. |
| `source` | string enum | yes | `suggestion`, `custom`, `auto`. |
| `intent` | string enum | yes | `continue`, `twist`, `steer`, `end`, `custom`. |
| `beat` | string | yes | 1 to 100 chars. |
| `description` | string | yes | 1 to 300 chars. |
| `arc_stage` | string | yes | A stage of the bible's template. |
| `characters` | string[] | yes | Cast ids. |
| `panels` | integer | yes | 1 to 6; default 4. |
| `original_text` | string or null | yes | The user's raw text when `source` is `custom` (treated as untrusted when quoted into prompts). |

### 5.7 Continuity report

Produced by `story/finalize.py` and stored in `story.continuity_json` (FR-022).

```json
{
  "schema": "comic-smith/continuity@1",
  "story_id": "sy_01J...",
  "checked_at": "2026-11-02T16:00:00Z",
  "issues": [
    {"id": "c1", "kind": "unresolved_thread", "severity": "warn", "strip": 2,
     "text": "Sub drifts toward the drain is never resolved.", "thread_id": "t1"},
    {"id": "c2", "kind": "vanished_character", "severity": "warn", "strip": 6,
     "text": "Grandma Sponge appears in strip 4 and never returns.", "character_id": "ch_sponge"}
  ],
  "titles": ["Puddle Takes the Plunge", "The Duck Who Would Not Swim", "Puddle and the Drain"],
  "blurb": "A rubber duck conquers the bathtub, one wobbly raft at a time."
}
```

| Field | T | Req | Constraints |
|---|---|---|---|
| `schema` | string | yes | Const `comic-smith/continuity@1` **(added schema id)**. |
| `story_id` | string | yes | `sy_` id. |
| `checked_at` | date-time | yes | |
| `issues[]` | object[] | yes (may be empty) | `id` (string), `kind` (`unresolved_thread`, `vanished_character`, `inconsistent_prop`, `tone_break`), `severity` (`info`, `warn`, `error`), `strip` (integer or null), `text` (1 to 300), optional `thread_id`, `character_id`, `panel_idx`. |
| `titles` | string[] | yes | Exactly 3 title suggestions, 1 to 80 chars each. |
| `blurb` | string | yes | One line, 1 to 160 chars. |

A story can be finalized with open issues ("finalize anyway"); the issues remain in the report.

### 5.8 Lettering JSON

Stored in `panel.lettering_json`; rendered by `letter/svg.py` and by the Studio's pure lettering components; consumed by the reader. Geometry follows ADR-019: fractions of the panel, origin top-left.

```json
{
  "schema": "comic-smith/lettering@1",
  "panel_id": "pn_01J...",
  "balloons": [
    {"id": "b1", "type": "speech", "text": "Jump in! It's warm!",
     "x": 0.58, "y": 0.06, "w": 0.34, "h": 0.2,
     "tail": {"tip_x": 0.72, "tip_y": 0.46, "speaker": "ch_sub"},
     "font": "comic-neue", "size": 0.045, "order": 1, "locked": false},
    {"id": "b2", "type": "whisper", "text": "Ducks don't do deep.",
     "x": 0.08, "y": 0.26, "w": 0.3, "h": 0.16,
     "tail": {"tip_x": 0.22, "tip_y": 0.52, "speaker": "ch_puddle"},
     "font": "comic-neue", "size": 0.04, "order": 2, "locked": false}
  ],
  "captions": [
    {"id": "c1", "text": "Meanwhile, at the edge of the tub...",
     "x": 0.02, "y": 0.02, "w": 0.5, "h": 0.1,
     "font": "atkinson-hyperlegible", "size": 0.04, "order": 0}
  ],
  "sfx": [
    {"id": "f1", "text": "SPLISH", "x": 0.7, "y": 0.62, "w": 0.25, "h": 0.14,
     "rotation": -6, "font": "bangers", "size": 0.09, "fill": "#2E86DE", "outline": "#1B1B3A",
     "near": "ch_sub", "order": 3}
  ],
  "character_boxes": [
    {"character_id": "ch_puddle", "x": 0.05, "y": 0.3, "w": 0.3, "h": 0.6,
     "head": {"x": 0.12, "y": 0.3, "w": 0.14, "h": 0.14}}
  ]
}
```

| Field | T | Req | Constraints |
|---|---|---|---|
| `schema` | string | yes | Const `comic-smith/lettering@1` **(added schema id)**. |
| `balloons[].id` | string | yes | Unique within the panel. |
| `balloons[].type` | string enum | yes | `speech`, `thought`, `shout`, `whisper`. Shapes per the Design spec: rounded ellipse or rounded rectangle (speech), cloud with three trailing circles (thought), spiky burst (shout), dashed outline (whisper). |
| `balloons[].text` | string | yes | 1 to 200 chars; XML-escaped on output; mirrors `dialogue[].text` unless edited. |
| `balloons[].x`, `y`, `w`, `h` | number | yes | Fractions in [0, 1]; the box must stay inside the panel (`x+w <= 1`, `y+h <= 1`). |
| `balloons[].tail` | object or null | yes | `tip_x`, `tip_y` in [0, 1] (the tail tip, normally the speaker head box); `speaker` (cast id or null). Thought balloons use the tip for the trailing circles. Null for tail-less balloons. |
| `balloons[].font` | string | yes | Registry id: `comic-neue`, `bangers`, `atkinson-hyperlegible`. |
| `balloons[].size` | number | yes | Fraction of panel height; clamped so that rendered size is not below 9 pt at print size and 14 px on web (Design: lettering visual spec). |
| `balloons[].order` | integer | yes | Reading order (top-left to bottom-right by default); also the `data-narrate` order. |
| `balloons[].locked` | boolean | no, default false | User-placed balloons are not moved by auto placement. |
| `captions[]` | object[] | yes (may be empty) | Rectangle boxes, pale yellow fill (`--cs-caption`), default top-left. Fields: `id`, `text` (1 to 160), geometry as above, `font`, `size`, `order`. |
| `sfx[]` | object[] | yes (may be empty) | Fields: `id`, `text` (1 to 20), geometry, `rotation` (degrees clockwise, -8 to 8 for auto placement; user range -45 to 45), `font`, `size`, `fill` (hex), `outline` (hex), `near` (cast id or null), `order`. |
| `character_boxes[]` | object[] | yes (may be empty) | Output of `VisionProvider.locate`: `character_id`, body box, and `head` box. Placement avoids these boxes; tails point to `head`. |

Text is uppercase for styles with `lettering.case = upper`; mixed case otherwise. Line height 1.15 and padding 0.6 em are renderer constants.

### 5.9 Book manifest (`comic-smith/book@1`)

```json
{
  "schema": "comic-smith/book@1",
  "id": "bk_01J...",
  "metadata": {"title": "Puddle, the Duck Who Would Not Swim", "subtitle": "A bath time adventure",
               "author": "Mina and Dad", "year": 2026, "language": "en",
               "noncommercial_models_used": false},
  "page_size": "us-comic",
  "pages": [
    {"id": "pg_01J...", "idx": 1, "kind": "cover", "layout_id": "cover-full"},
    {"id": "pg_01K...", "idx": 2, "kind": "title", "layout_id": "title-center"},
    {"id": "pg_01L...", "idx": 3, "kind": "story", "layout_id": "strip-stack", "story_id": "sy_01J..."}
  ],
  "chapters": [{"story_id": "sy_01J...", "title": "Puddle Takes the Plunge", "start_page": 3}],
  "export_defaults": {"dpi": 300, "pdf_mode": "print", "bleed_in": 0.125, "trim_marks": false,
                      "single_file_web": true}
}
```

| Field | T | Req | Constraints |
|---|---|---|---|
| `schema`, `id` | string | yes | Const `comic-smith/book@1`; `bk_` id. |
| `metadata.title` | string | yes | 1 to 120. |
| `metadata.subtitle`, `author` | string or null | yes | 0 to 120. |
| `metadata.year` | integer or null | yes | 1900 to 2200. |
| `metadata.language` | string | yes | BCP 47 tag; default `en`. |
| `metadata.noncommercial_models_used` | boolean | yes | True if any asset in the book came from an opted-in non-commercial model (NFR-011); also written into export file metadata. |
| `page_size` | string enum | yes | Page size key. |
| `pages[]` | object[] | yes | Ordered; each: `id`, `idx` (consecutive from 1), `kind` (page.kind enum), `layout_id`, optional `story_id` (kind `story`). Cover, title, dedication, cast, and back pages use internal layouts `cover-full`, `title-center`, `dedication-center`, `cast-grid`, `back-simple` **(added; layout ids to be confirmed, section 14)**. |
| `chapters[]` | object[] | yes (may be empty) | `story_id`, `title`, `start_page` (integer >= 1); a table of contents is generated when 2 or more chapters exist. |
| `export_defaults` | object | yes | `dpi` (72, 150, 300), `pdf_mode` (`screen`, `print`), `bleed_in` (number, 0.125 default for print), `trim_marks` (boolean), `single_file_web` (boolean). This object is also stored in `book.settings_json`. |

### 5.10 Published JSON Schemas

The Prompt's repository layout publishes six schema files under `schemas/`, generated from the pydantic models in CI and checked for drift:

| File | Schema id |
|---|---|
| `schemas/bible.schema.json` | `comic-smith/bible@1` |
| `schemas/suggestions.schema.json` | `comic-smith/suggestions@1` |
| `schemas/panel.schema.json` | `comic-smith/panel@1` |
| `schemas/character.schema.json` | `comic-smith/character@1` |
| `schemas/layout.schema.json` | `comic-smith/layout@1` |
| `schemas/book.schema.json` | `comic-smith/book@1` |

This document **adds** four more schemas for formats that cross module or process boundaries and therefore need validation: `schemas/style.schema.json` (`comic-smith/style@1`), `schemas/beat.schema.json` (`comic-smith/beat@1`), `schemas/continuity.schema.json` (`comic-smith/continuity@1`), and `schemas/lettering.schema.json` (`comic-smith/lettering@1`). The packaged copies used for LLM output validation live in `comic_smith/story/schemas/` (`panel_spec.json`, `suggestion.json`, `bible.json`) and are generated from the same models.

Versioning rules for schemas (Versioning section): a breaking change (removing or retyping a field, tightening an enum) is a MAJOR release and bumps the `@N` suffix; adding an optional field with a default is a MINOR change. Readers accept the current and previous `@N` through a migration function until the next MAJOR.


#### Implementation notes **(Sprint 1)**

- Python models live in the package `comic_smith/models/`; the `schema` marker is the attribute `schema_id` (alias `schema`) because `BaseModel.schema` is a deprecated pydantic method. Models forbid unknown keys.
- `Arc.stages` is optional on input; when omitted it is filled from the template (`ARC_STAGES`), and a list that differs from the template is rejected.
- `StripScript` (1 to 6 `PanelSpec`, `idx` 1..n) and `ArcDiff` (`threads_opened` texts, `threads_closed` ids, `stage`) and `ModerationVerdict` are LLM-facing helper models without a `schema` field and are not published.
- `comic_smith.models.llm_schema(Model)` inlines `$ref`/`$defs`, drops `title`/`default`, turns `const` into a one-value `enum`, and removes the `schema` property for Ollama and OpenAI structured outputs.
- `Beat.original_text`, `Character.reference`, `SuggestionOption` fields marked "required" with null allowed keep a `None` default where noted in the model; `SuggestionSet.after_strip` and `end_here` have no default.
- Layout `reading_order` must be a permutation of slot ids; balloon, caption, sfx, and character boxes must fit inside the panel.
- Id prefixes follow the comments in section 4.1 (`sp_` strip, `pn_` panel, `ss_` suggestion set, `sy_` story, `ex_` export, `jb_` job, `st_` style); see `comic_smith/ids.py`.
- `project.style_id` stays NULL until the style row exists (built-in styles are seeded later); the requested id is kept in `metadata_json.style_id`. `project.renamed` changes the display name only; the folder slug is stable. New events: `project.settings_changed` payload `{project_id, set, unset}`.
- **(Sprint 1) Writer, strips, branches, finalize** (`comic_smith/story/{writer,strips,branches,finalize}.py`):
  - Audience limits (words per balloon, balloons per panel, words per strip counting dialogue and captions): `kids-5-8` 10/2/60, `kids-9-12` 18/3/110, `all-ages` 20/3/130, `teen` 25/4/170, `adult` 30/4/220. A script must have exactly the requested panel count, cast-only speakers, characters and sfx `near`, no run of three equal shots, and a non-`none` `balloon_space` on any panel with text. One corrective retry lists the violations; the second failure raises `GenerationInvalidError` (exit 5).
  - New or changed event types (all undoable): `strip.created` (inverse `strip.removed`), `panel.spec_edited` (payload carries the new `stale` flag, so `panel.marked_stale` is not a separate event), `strip.approved` / `strip.unapproved`, `branch.created`, `branch.deleted` (inverse `branch.restored`, which rebuilds the branch with its own strips and panels), `branch.switched`, `branch.renamed`, `story.finalized` (upsert of the story row; inverse restores the previous state or `story.removed`), `story.reopened`. `strip.scripted` and `strip.edited` from the table are replaced by `strip.created` and `panel.spec_edited`.
  - `strip.idx` is the strip's 1-based position in any branch listing containing it; a branch lists its parent's strips up to `fork_strip_id` and then its own. A branch that still has child branches, is active, or has a story cannot be deleted. Unapproving returns a strip to `scripted`.
  - Finalize: `finalize.review` makes two LLM calls (continuity at temperature 0, titles at 0.8); issues pointing at a missing strip or unknown character are dropped. A story is locked when the latest `story.version` of a branch has `finalized_at`; any strip on a locked branch (including strips a locked branch inherits) rejects edits with `ImmutableEntityError`. Reopen inserts version n+1 (unlocked, same title and blurb); finalizing again updates that row.
  - `create_strip` calls the LLM before opening its write transaction, so a generation failure leaves no rows.

---

## 6. Pipelines

Four pipelines, each a numbered sequence. "Fn" names are the service functions that do the work (module-qualified); the `comic_smith.api` entry points call them. "Events" lists event-log types (section 4.4) followed by WebSocket events (section 7.5) in braces. FR numbers refer to the PRD.

### 6.1 Seed to cast

Entry: `api.create_project(...)`, `api.add_character(...)`, `api.generate_sheet(...)`, `api.approve_character(...)`.

| # | Step | Module and function | Events |
|---|---|---|---|
| 1 | Create the project folder, `project.db`, default branch `main`; select style and audience | `db.session.create_project`, `cast.styles.select` | `project.created`, `style.selected` |
| 2 | Moderate the seed narrative (audience guard) and run the denylist check on it | `story.moderation.check_text`, `cast.originality.check_text` | none; blocks with `AudienceBlockedError` or `OriginalityBlockedError` (exit 4) |
| 3 | Ingest each reference image (FR-002): magic-byte sniff, type and size checks (20 MB), decompression-bomb guard, HEIC convert, EXIF and XMP strip, downscale over 4096 px, re-encode, hash, store | `assets.images.ingest`, `assets.store.put` | none (asset rows only) |
| 4 | Vision describe (FR-003): structured JSON of subject, palette, features, accessories, suggested name, and a `person_detected` flag | `cast.reference.describe` via `VisionProvider.describe` | `character.added` |
| 5 | Person check (FR-007): if a person is detected, require attestation; photoreal presets disabled for this character; reject if attestation is missing | `cast.reference.check_person` | blocks with `PersonAttestationRequiredError` (exit 4) |
| 6 | Originality check on the description (FR-006): denylist over description, name, and style text | `cast.originality.check_text` | `character.reference_edited` if the user edits after a block |
| 7 | Generate the story bible from the narrative and cast descriptions (FR-009): LLM call with `bible` schema, cache when temperature 0 | `story.bible.generate` via `LLMProvider.complete_json` | `bible.created` |
| 8 | Generate the sheet (FR-004): front, side, three-quarter views and six expressions, with style tokens and the reference image when `max_reference_images >= 1`; each view is a render job | `cast.sheet.generate` enqueues `sheet.generate` jobs; `panels.compiler.compile_sheet_view` | `character.sheet_generated`, `job.enqueued`, `job.finished` {`job.progress`, `job.done`, `entity.changed`} |
| 9 | User approves or regenerates per view (FR-004) | `cast.sheet.regenerate_view`, `cast.sheet.approve` | `character.view_regenerated`, `character.approved` |
| 10 | Originality resemblance check on the approved sheet (FR-006): vision question "does this resemble a well-known copyrighted character?"; on a match, approval is reverted and the triggering rule reported | `cast.originality.check_sheet` via `VisionProvider.describe` | `character.unapproved` on a match; blocks with `OriginalityBlockedError` (exit 4) |
| 11 | Finalize visual DNA (one paragraph of invariant features) and bump `character.sheet_version` | `cast.dna.finalize` | `character.approved` (payload includes `sheet_version`) |
| 12 | Save to library (optional) | `api.library_add` | `character.imported` on import |

### 6.2 Beat to strip

Entry: `api.suggest_next`, `api.make_strip`, `api.render_strip`, `api.letter_strip`, `api.approve_strip`. This is the core loop (the product).

| # | Step | Module and function | Events |
|---|---|---|---|
| 1 | Suggestions (FR-011): LLM returns exactly three options; distinctness via `EmbeddingsProvider` (pairwise cosine < 0.85, one regenerate); add the `end` option when the arc is in its final stage or the target length is reached | `story.suggest.suggest`, `story.arc.progress` | `suggestions.generated` {`suggestions.ready`} |
| 2 | Optional thumbnails at low step count, or skipped when the backend is slow | `story.suggest.enqueue_thumbnails` -> `suggestion.thumbnail` jobs, priority 5 | `job.enqueued`, `job.finished` {`job.progress`, `job.done`} |
| 3 | Chosen or custom beat (FR-012): a pick records `chosen_idx`; free text is normalized by the LLM into a Beat and shown to the user for acceptance | `story.writer.normalize_beat` | `beat.chosen` or `beat.custom` |
| 4 | Writer (FR-013): beat to 1 to 6 Panel Specs, schema-validated, one corrective retry on failure, audience limits applied | `story.writer.write_strip` via `LLMProvider.complete_json` | `strip.scripted` {`entity.changed`} |
| 5 | Moderation of the beat and the script (FR-028) | `story.moderation.check_strip` | blocks with `AudienceBlockedError` (exit 4) |
| 6 | User edits any panel field (FR-014); visual edits mark the panel stale, text-only edits do not | `story.writer.edit_panel_spec` (applied through `api.edit_panel`) | `panel.spec_edited`, `panel.marked_stale` {`entity.changed`} |
| 7 | Compile each panel (FR-015): deterministic Panel Spec to `ImageRequest` (style tokens, visual DNA, reference assets from approved sheets, composition and balloon-space hints, continuity notes, the no-text constraint); denylist and moderation run on the compiled prompt | `panels.compiler.compile` | none (compiled prompt stored on the take) |
| 8 | Render jobs (FR-016): `takes` per panel (default `DEFAULT_TAKES = 2`), per-panel seed recorded, backend progress forwarded; failures retried twice | `panels.render.render_panel` enqueues `panel.render` jobs, priority 0 | `panel.take_added`, `job.enqueued`, `job.finished` {`job.progress`, `job.done`, `entity.changed`} |
| 9 | QA and retakes (FR-017): vision scores each character 1 to 5 against the sheet checklist; RapidOCR detects drawn text; any score below `QA_MIN_SCORE = 4` or detected text triggers up to `QA_MAX_RETAKES = 2` retakes with new seeds; the best take is selected | `panels.qa.score`, `panels.render.select_best_take` | `panel.qa_flagged` {`qa.flagged`}, `panel.take_added`, `panel.take_selected` |
| 10 | Image audience check (S3-T13): vision check of the rendered image against the audience setting | `story.moderation.check_image` | `panel.qa_flagged` with reason `audience` |
| 11 | Character boxes from the vision model (`VisionProvider.locate`) | `letter.layout.locate_characters` | `panel.lettering_edited` (initial) |
| 12 | Auto-lettering (FR-019): place balloons avoiding character boxes, reading order, tails to head boxes, auto-fit font within min and max, never overflow | `letter.layout.place`, `letter.svg.render` | `panel.lettering_edited` |
| 13 | User adjusts take selection, panel edits (inpaint, crop), and lettering (drag, resize, retype, change type) | `panels.edit.inpaint`, `panels.edit.crop`, `api.update_lettering` | `panel.edited`, `panel.cropped`, `panel.take_selected`, `panel.lettering_edited` |
| 14 | Approve (FR-020): requires every panel rendered and lettered; strip becomes immutable until unapprove | `story.writer.approve_strip` | `strip.approved` {`entity.changed`} |
| 15 | Bible update: open threads and arc stage updated from the approved strip | `story.bible.apply_strip`, `story.arc.advance` | `bible.edited`, `bible.thread_opened`, `bible.thread_closed`, `bible.arc_advanced` |
| 16 | Next suggestions are generated (back to step 1), or the user picks `end` and moves to finalize | `story.suggest.suggest` | `suggestions.generated` {`suggestions.ready`} |

Auto mode (`api.run_auto`) repeats steps 1 to 16 with a policy picking each option, recording `auto.pick` events (actor `auto`), stopping at the target length before finalize (FR-026). Every auto pick is reversible with undo.

### 6.3 Strip to page

Entry: `api.finalize_story`, `api.paginate_story`.

| # | Step | Module and function | Events |
|---|---|---|---|
| 1 | Finalize (FR-022): continuity review via LLM producing a Continuity report (unresolved threads, vanished characters, inconsistent props, tone breaks), three titles and a blurb | `story.finalize.review` | none (the review result is returned and stored in `story.continuity_json`) |
| 2 | User fixes issues (jump to strip) or finalizes anyway; story is locked, `finalized_at` set, `version` recorded | `story.finalize.lock` | `story.finalized` |
| 3 | Paginate with the chosen template and size (FR-023): never split a strip across pages unless allowed; 3 strips per page by default for `strip-stack` | `layout.paginate.paginate`, `layout.templates.load` | `pages.paginated` |
| 4 | Compose page SVG: panels as images with crops, lettering as SVG text with embedded fonts, borders, page captions | `layout.page.compose` | none (pure function of rows and assets) |
| 5 | Preview in Studio (same SVG as export) | `api.get_page_svg` | none |
| 6 | User edits: drag panels between slots, change layout per page, add page captions | `layout.page.move_slot`, `layout.page.set_layout`, `layout.page.set_caption` | `page.slot_moved`, `page.layout_changed`, `page.caption_edited` |

Reopening a finalized story (`api.reopen_story`) creates a new `story.version` and emits `story.reopened`; prior pages that reference the old version stay until repaginated.

### 6.4 Book to export

Entry: `api.build_book`, `api.export`.

| # | Step | Module and function | Events |
|---|---|---|---|
| 1 | Book builder (FR-024): create the book, cover (art generated from the story or picked from panels), title page, optional dedication, story pages as chapters, optional cast page from sheets, back cover; page numbers; table of contents for multi-story books | `book.builder.build`, `book.builder.make_cover` (a `cover.generate` job when generating art) | `book.cover_set`, `book.page_added`, `book.settings_edited` |
| 2 | Enqueue the export job (priority 7): `export.created` row plus `export` job | `export.*` via `jobs.queue.enqueue` | `export.created`, `job.enqueued` |
| 3 | For image formats: for each page, render the page SVG in Chromium to PNG at target dpi (72, 150, 300); JPG and WebP are encoded from the PNG; a long strip stacks story strips into one image | `export.chromium.render_png`, `export.images.export_pages`, `export.images.long_strip` | {`job.progress` per page} |
| 4 | Upscale step when source art is below target dpi (NFR-010), via Real-ESRGAN workflow when configured, else Lanczos | `export.images.ensure_resolution` (calls `ImageBackend.generate` with an upscale workflow, or Pillow) | none |
| 5 | For PDF: print the whole book HTML to PDF in Chromium (screen mode: web size; print mode: bleed 0.125 in, optional trim marks); post-process metadata and marks with pikepdf; verify selectable text | `export.pdf.render`, `export.pdf.postprocess` | {`job.progress`} |
| 6 | For CBZ: zip page PNGs in order with ComicInfo metadata | `export.cbz.package` | none |
| 7 | For web: static folder (reader bundle, page SVGs, assets) or single-file HTML with base64 assets; `data-narrate` markup; alt text from `action`; works from `file://` | `export.web.build` | none |
| 8 | Store outputs as assets (origin `export`), copy to `--out` directory, write export metadata including non-commercial model usage | `assets.store.put`, `export.*.finish` | `job.finished` {`job.done`, `entity.changed`} |

Chromium runs with network blocked, a fresh profile per job, no extensions, and a timeout per page (section 11.4).

---

## 7. Contracts

### 7.1 CLI

Binary: `mr-comic-smith` (console script of the `mr-comic-smith` package). All commands operate on the same project files as the Studio and, when `--server` is given, on a remote server (S7-T04).

#### Global flags **(added)**

| Flag | Default | Meaning |
|---|---|---|
| `--json` | off | Machine-readable output where the command supports it (FR-030). Errors are emitted as the problem object (section 10.3). |
| `--data-dir PATH` | `COMIC_SMITH_DATA_DIR` | Override the data directory. |
| `--config PATH` | `./comic-smith.toml` then the user config dir | Config file (section 12.2). |
| `--server URL` | unset | Run the command against a remote server; requires `--token` (S7-T04). |
| `--token TOKEN` | `COMIC_SMITH_SERVER_TOKEN` | Bearer token for `--server`. |
| `-v`, `--verbose` | off | Raise log level one step. |
| `-q`, `--quiet` | off | Suppress progress output. |
| `--version` | | Print version and exit 0. |
| `--help` | | Print help and exit 0. |

#### Commands

`<project>` is a project slug, id, or path.

| Command | Flags (default) | Notes |
|---|---|---|
| `new <name>` | `--narrative "..."` (none; 1 to 5,000 chars), `--image FILE` (repeatable, 0 to 4; none), `--style ID` (`picture-book-watercolor`), `--audience AUD` (`COMIC_SMITH_DEFAULT_AUDIENCE`, `all-ages`), `--strips N` (`8`; 1 to 40), `--arc TEMPLATE` (`problem-try-try-succeed` for `kids-*` audiences, else `three-act`) | At least one of `--narrative` or `--image` is required (else exit 2). Runs seed to cast steps 1 to 7 and leaves characters awaiting approval. **(Sprint 1: only `--narrative` works; it generates and saves the bible. `--image` exits 2 with a hint until Sprint 2. `--json` prints the project record.)** |
| `cast add <project>` | `--image FILE` (required unless `--description`), `--description TEXT` (none) **(added, FR-005)**, `--name NAME` (vision-suggested), `--attest-person` (off) | Without `--attest-person`, a person in the image blocks with exit 4. |
| `cast sheet <project> <character>` | `--regenerate views` (off; value is a comma list of `front,side,three_quarter,neutral,happy,sad,surprised,angry,scared`, or `all`) | Generates or regenerates sheet views; `cast approve <project> <character>` **(added)** approves. |
| `bible <project>` | `--set KEY=VALUE` (repeatable; dotted keys nest, e.g. `arc.target_strips=6`; VALUE is parsed as JSON, else kept as text) **(Sprint 1; replaces the `$EDITOR` flow, which stays planned)**, `--json` (off) | Without `--set`, prints the bible (JSON with `--json`). Each `--set` run saves one new, undoable version. |
| `suggest <project>` | `--branch NAME` (the active branch, `main` by default), `--json` (off) | Prints the three options (plus `end`). |
| `strip <project>` | `--pick 1\|2\|3\|end` or `--beat "free text"` (exactly one required), `--panels N` (`4`; 1 to 6), `--branch NAME` (the active branch) **(added)**, `--set ID` (latest suggestion set) **(added)**, `--json` (off) | Writes the strip script only; use `render` next. Prints the panel specs; a pick made after a strip was approved needs a fresh `suggest` (exit 5). |
| `strips <project>` **(added)** | `--branch NAME` (active), `--json` | Lists the branch's strips. |
| `render <project>` | `--strip N` (latest unapproved strip), `--panel M` (all stale or unrendered panels in the strip), `--takes N` (`2`), `--backend ID` (`COMIC_SMITH_IMAGE_BACKEND`) | Blocks until jobs finish; progress to stderr. |
| `letter <project>` | `--strip N` (required), `--auto` (off; run auto placement and overwrite non-locked lettering) | Without `--auto`, opens the JSON for edit like `bible --edit`. |
| `approve <project>` | `--strip N` (required), `--branch NAME` (active) **(added)**, `--json` | From Sprint 3 fails if any panel is unrendered or unlettered (exit 5 for missing prerequisites); in Sprint 1 a scripted strip can be approved. |
| `branch <project> create\|switch\|list\|delete\|rename` | `create NAME [--from-strip N] [--switch]`, `switch NAME`, `list`, `delete NAME [--yes]`, `rename OLD NEW` **(rename, --switch added)**, `--json` | `create` defaults to forking from the latest approved strip. `delete` asks unless `--yes`; with `--json` it requires `--yes`. |
| `auto <project>` | `--policy balanced\|steer\|twist` (`balanced`), `--until-target/--one-step` (`--until-target`; stop when the bible's `target_strips` is reached, never finalize; `--one-step` writes one strip), `--branch NAME` (active), `--json` | Never finalizes; every pick is an `auto.pick` event. Script-only until Sprint 3. Picks are deterministic: balanced rotates continue, steer, twist; steer and twist repeat their intent twice per three strips with a continue between; the end option is taken when offered and the strip reaches the target. All calls run at temperature 0 with actor `auto`. Refuses (exit 5) if the branch has strips waiting for approval. |
| `finalize <project>` | `--branch NAME` (active branch), `--title "..."` (chosen from suggestions), `--force` or `--yes` (off; finalize despite open issues) **(added)**, `--json` | Open issues without `--force` exit 5 with the report in the error detail. |
| `undo <project>`, `redo <project>`, `history <project> [--limit N]` **(added)** | `--json` | Undo or redo the latest change (prints nothing to do when empty); history lists recent events. |
| `pages <project>` | `--layout ID` (`strip-stack`), `--size KEY` (`us-comic`), `--allow-split` (off) **(added)** | Paginates the finalized story. |
| `book <project> add-page\|move\|remove\|cover\|show ...` | `add-page --kind KIND [--layout ID]`, `move PAGE --to N`, `remove PAGE [--yes]`, `cover [--from-panel ID] [--generate]`, `show` | `show` prints the book manifest (`comic-smith/book@1`). |
| `export <project>` | `--target page\|story\|book` (required), `--format png\|jpg\|webp\|pdf\|cbz\|web\|strip` (required), `--dpi 72\|150\|300` (`150`), `--print` (off; PDF with bleed and optional trim marks), `--single-file` (off; web), `--out DIR` (`./exports`), `--id ID` (required when target is `page`) **(added)** | Format and target compatibility: `strip` applies to `story`; `cbz` and `web` to `story` or `book`. |
| `library add\|list\|import` | `add <project> <character\|style>`, `list [--kind character\|style]`, `import <project> <item>` | FR-027. |
| `studio` | `--port N` (`7351`), `--host H` (`127.0.0.1`) **(added; used by Compose)**, `--lan` (off), `--access-code CODE` (none; min 8 chars; required with `--lan`) | Serves the Studio (and the REST API). |
| `serve` | `--host H` (`127.0.0.1`), `--port N` (`7350`), `--no-studio` (off) **(added)** | REST server; non-localhost binding requires `COMIC_SMITH_SERVER_TOKEN`. |
| `mcp` | `--transport stdio\|http` (`stdio`) | MCP server. |
| `doctor` | `--json` (off), `--fix` (off; installs Chromium and fixes what it safely can) | Exit 0 when required checks pass, else 3. |
| `gc <project>` | `--dry-run` (off) **(added)** | Removes unreferenced assets (section 4.3). |
| `models pull <name>` | `--comfyui-models DIR` (`./models`) | Fetches workflow models with pinned revisions and SHA-256 verification **(Appendix G; flags beyond `--comfyui-models` added)**. |

#### Exit codes

| Code | Name | Meaning | Error classes (section 10) |
|---|---|---|---|
| 0 | ok | Success | none |
| 2 | usage | Bad flags, unknown ids, invalid provider string, invalid config | `UsageError` |
| 3 | preflight failed | A required backend, provider, model, license gate, font, Chromium, or disk check failed | `PreflightError` family |
| 4 | safety blocked | Originality, people attestation, audience, or upload policy blocked the request | `SafetyError` family |
| 5 | generation invalid | The LLM or vision output failed validation after retry, or an operation's prerequisites are not met | `GenerationInvalidError` family |
| 6 | render failed | Image generation, QA retake exhaustion that blocks approval, or lettering failed | `RenderError` family |
| 7 | export failed | Chromium, PDF, packaging, or web build failed | `ExportError` family |
| 8 | project locked or not found | Project missing, locked by another process, migration failed, or entity immutable | `ProjectError` family |

Exit code 1 is reserved for unexpected internal errors (uncaught exceptions are converted by `cli.py` to a `ComicSmithError` with code `internal_error` and printed with a bug-report hint). It is not part of the documented contract table; see section 14 question 2.

### 7.2 Python API (`comic_smith.api`)

The facade. All functions are synchronous, typed, and raise `ComicSmithError` subclasses only. Ids are strings. Long-running operations return a `JobRef` and accept `wait: bool = True` **(added)**; with `wait=False` they return immediately and progress arrives through events.

```python
from __future__ import annotations
from pathlib import Path
from typing import Any, Callable, Literal
from comic_smith.models import (  # pydantic models generated from section 5
    Project, Bible, Character, StylePreset, Beat, SuggestionSet, Strip, Panel, PanelSpec,
    Take, LetteringDoc, ContinuityReport, Story, Page, Book, ExportRecord, JobRef, Job,
    DoctorReport, Event, AssetRef, BackendInfo, Recommendation,
)

Audience = Literal["all-ages", "kids-5-8", "kids-9-12", "teen", "adult"]
ProgressCb = Callable[[dict[str, Any]], None] | None

# --- projects
def create_project(name: str, *, narrative: str | None = None, image_paths: list[Path] | None = None,
                   style: str = "picture-book-watercolor", audience: Audience | None = None,
                   target_strips: int = 8, arc: str | None = None) -> Project: ...
def open_project(project: str) -> Project: ...
def list_projects(*, include_archived: bool = False) -> list[Project]: ...
def rename_project(project: str, name: str) -> Project: ...
def duplicate_project(project: str, name: str) -> Project: ...
def archive_project(project: str, archived: bool = True) -> Project: ...
def delete_project(project: str) -> None: ...

# --- cast
def add_character(project: str, *, image_path: Path | None = None, description: str | None = None,
                 name: str | None = None, attest_person: bool = False) -> Character: ...
def edit_character_reference(project: str, character_id: str, changes: dict[str, Any]) -> Character: ...
def generate_sheet(project: str, character_id: str, *, regenerate: list[str] | None = None,
                   wait: bool = True, progress: ProgressCb = None) -> Character | JobRef: ...
def approve_character(project: str, character_id: str) -> Character: ...
def list_styles(project: str | None = None) -> list[StylePreset]: ...
def create_style(project: str, name: str, *, description: str,
                 reference_images: list[Path] | None = None) -> StylePreset: ...
def set_style(project: str, style_id: str) -> Project: ...

# --- story
def get_bible(project: str) -> Bible: ...
def edit_bible(project: str, changes: dict[str, Any]) -> Bible: ...
def suggest_next(project: str, *, branch: str = "main") -> SuggestionSet: ...
def make_strip(project: str, *, set_id: str | None = None, pick: int | Literal["end"] | None = None,
               beat: str | None = None, panels: int = 4, branch: str = "main") -> Strip: ...
def edit_panel(project: str, panel_id: str, changes: dict[str, Any]) -> Panel: ...
def render_strip(project: str, strip: int | str | None = None, *, panel: int | None = None,
                 takes: int = 2, backend: str | None = None, wait: bool = True,
                 progress: ProgressCb = None) -> Strip | JobRef: ...
def retake_panel(project: str, panel_id: str, *, backend: str | None = None, wait: bool = True) -> Panel | JobRef: ...
def select_take(project: str, panel_id: str, take_id: str) -> Panel: ...
def inpaint_panel(project: str, panel_id: str, *, mask_png: bytes, instruction: str,
                  wait: bool = True) -> Panel | JobRef: ...
def crop_panel(project: str, panel_id: str, crop: dict[str, float]) -> Panel: ...
def letter_strip(project: str, strip: int | str, *, auto: bool = True) -> Strip: ...
def update_lettering(project: str, panel_id: str, lettering: LetteringDoc) -> Panel: ...
def approve_strip(project: str, strip: int | str) -> Strip: ...
def unapprove_strip(project: str, strip: int | str) -> Strip: ...
def run_auto(project: str, *, policy: Literal["balanced", "steer", "twist"] = "balanced",
             until_target: bool = True, wait: bool = True) -> list[Strip] | JobRef: ...

# --- branches and finalize
def create_branch(project: str, name: str, *, from_strip: int | None = None) -> str: ...
def switch_branch(project: str, name: str) -> str: ...
def list_branches(project: str) -> list[dict[str, Any]]: ...
def delete_branch(project: str, name: str) -> None: ...
def finalize_story(project: str, *, branch: str | None = None, title: str | None = None,
                   force: bool = False) -> Story: ...
def reopen_story(project: str, story_id: str) -> Story: ...

# --- pages and book
def paginate_story(project: str, story_id: str | None = None, *, layout: str = "strip-stack",
                   size: str = "us-comic", allow_split: bool = False) -> list[Page]: ...
def update_page(project: str, page_id: str, changes: dict[str, Any]) -> Page: ...
def get_page_svg(project: str, page_id: str) -> str: ...
def build_book(project: str, *, layout: str | None = None, size: str | None = None,
               cover: bool = True) -> Book: ...
def book_add_page(project: str, kind: str, *, layout: str | None = None) -> Page: ...
def book_move_page(project: str, page_id: str, to_idx: int) -> Book: ...
def book_remove_page(project: str, page_id: str) -> Book: ...
def book_set_cover(project: str, *, from_panel: str | None = None, generate: bool = False) -> Book: ...

# --- export
def export(project: str, *, target: Literal["page", "story", "book"],
           formats: list[Literal["png", "jpg", "webp", "pdf", "cbz", "web", "strip"]],
           target_id: str | None = None, dpi: int = 150, print_mode: bool = False,
           single_file: bool = False, out_dir: Path | None = None, wait: bool = True,
           progress: ProgressCb = None) -> list[Path] | JobRef: ...

# --- library, history, jobs, system
def library_add(project: str, kind: Literal["character", "style"], item_id: str) -> str: ...
def library_list(kind: Literal["character", "style"] | None = None) -> list[dict[str, Any]]: ...
def library_import(project: str, item_id: str) -> Character | StylePreset: ...
def undo(project: str) -> Event | None: ...
def redo(project: str) -> Event | None: ...
def history(project: str, *, limit: int = 100) -> list[Event]: ...
def get_job(job_id: str) -> Job: ...
def cancel_job(job_id: str) -> Job: ...
def list_backends() -> list[BackendInfo]: ...
def recommend(description: str) -> Recommendation: ...
def doctor(*, fix: bool = False) -> DoctorReport: ...
def gc(project: str, *, dry_run: bool = False) -> dict[str, int]: ...
def models_pull(name: str, *, comfyui_models: Path) -> None: ...
```

Sprint 1 notes: story functions take keyword-only `settings`, `llm`, and `embeddings` (tests inject fakes) and return pydantic models (`Bible`, `SuggestionSet`, `StripDetail`, `BranchInfo`, `StoryInfo`, `EventInfo`). `branch` defaults to the active branch (`None`), which is `main` until a switch. `make_strip` picks `1|2|3|"end"` from the newest suggestion set on the branch (it must follow the last approved strip) or normalizes free text. `create_project` requires a narrative until Sprint 2 and removes the new folder if the bible fails. `run_auto` takes an optional `on_strip` callback and returns the strips it wrote.

Rules: functions never print or exit; raise `ComicSmithError`; accept ids or human references (strip index, slug); mutations are atomic with their event.

### 7.3 REST API (prefix `/v1`)

The server is FastAPI on port `7350` (Studio on `7351` proxies `/v1` to it, or serves both when started with `studio`). All bodies are JSON unless noted; errors are `application/problem+json` (section 10.3). State-changing requests carry the CSRF header token in cookie-authenticated sessions; bearer-token requests do not need CSRF.

| Method and path | Purpose | Body or query | Success |
|---|---|---|---|
| `GET /v1/projects` | List projects | `?archived=false` | 200 `Project[]` |
| `POST /v1/projects` | Create | `{name, narrative?, image_asset_ids?, style?, audience?, target_strips?, arc?}`; multipart variant accepts image parts | 201 `Project` |
| `GET /v1/projects/{p}` | Get | | 200 |
| `PATCH /v1/projects/{p}` | Rename, archive, change audience or style | `{name?, archived?, audience?, style_id?}` | 200 |
| `DELETE /v1/projects/{p}` | Delete (to trash) | | 204 |
| `POST /v1/projects/{p}/duplicate` | Duplicate | `{name}` | 201 |
| `GET /v1/projects/{p}/characters` | List characters | | 200 |
| `POST /v1/projects/{p}/characters` | Add from image or text | multipart `image` or JSON `{description, name?, attest_person?}` | 201 `Character` |
| `GET /v1/projects/{p}/characters/{c}` | Get | | 200 |
| `PATCH /v1/projects/{p}/characters/{c}` | Edit reference fields | partial `reference` | 200 |
| `POST /v1/projects/{p}/characters/{c}/sheet` | Generate or regenerate views | `{regenerate?: string[]}` | 202 `JobRef` |
| `POST /v1/projects/{p}/characters/{c}/approve` | Approve | | 200 `Character` |
| `GET /v1/projects/{p}/bible` | Current bible | `?version=` | 200 `Bible` |
| `PUT /v1/projects/{p}/bible` | Replace (new version) | `Bible` | 200 |
| `POST /v1/projects/{p}/suggestions` | Generate a suggestion set | `{branch?}` | 201 `SuggestionSet` |
| `GET /v1/projects/{p}/suggestions/{id}` | Get a set | | 200 |
| `POST /v1/projects/{p}/strips` | Make a strip | `{suggestion_set_id, pick}` or `{suggestion_set_id?, custom_beat, panels?}` | 201 `Strip` |
| `GET /v1/projects/{p}/strips` | List strips | `?branch=` | 200 |
| `GET /v1/projects/{p}/strips/{id}` | Get a strip with panels | | 200 |
| `POST /v1/projects/{p}/strips/{id}/render` | Render panels | `{takes?, backend?, panel_ids?}` | 202 `JobRef` |
| `POST /v1/projects/{p}/strips/{id}/letter` | Auto-letter | `{auto: true}` | 200 `Strip` |
| `POST /v1/projects/{p}/strips/{id}/approve` | Approve | | 200 |
| `POST /v1/projects/{p}/strips/{id}/unapprove` | Unapprove | | 200 |
| `PATCH /v1/projects/{p}/panels/{id}` | Edit spec or lettering | `{spec?: PanelSpec, lettering?: LetteringDoc, selected_take_id?, crop?}` | 200 `Panel` |
| `POST /v1/projects/{p}/panels/{id}/render` | Render | `{backend?}` | 202 `JobRef` |
| `POST /v1/projects/{p}/panels/{id}/retake` | New take | `{backend?, seed?}` | 202 `JobRef` |
| `POST /v1/projects/{p}/panels/{id}/edit` | Inpaint | multipart `mask` + `{instruction}` | 202 `JobRef` |
| `GET /v1/projects/{p}/branches` | List | | 200 |
| `POST /v1/projects/{p}/branches` | Create | `{name, from_strip?}` | 201 |
| `PATCH /v1/projects/{p}/branches/{b}` | Rename or activate | `{name?, active?}` | 200 |
| `DELETE /v1/projects/{p}/branches/{b}` | Delete | | 204 |
| `POST /v1/projects/{p}/auto` | Run auto mode | `{policy?, until_target?}` | 202 `JobRef` |
| `POST /v1/projects/{p}/finalize` | Finalize a branch | `{branch?, title?, force?}` | 200 `Story` (with `ContinuityReport`) |
| `POST /v1/projects/{p}/stories/{s}/reopen` | Reopen | | 200 |
| `POST /v1/projects/{p}/pages` | Paginate | `{story_id?, layout?, size?, allow_split?}` | 201 `Page[]` |
| `GET /v1/projects/{p}/pages/{id}` | Get | | 200 |
| `PATCH /v1/projects/{p}/pages/{id}` | Layout, slots, captions | partial | 200 |
| `GET /v1/projects/{p}/pages/{id}/svg` | Page SVG (same renderer as export) | | 200 `image/svg+xml` |
| `GET /v1/projects/{p}/book` | Get the book manifest | | 200 `comic-smith/book@1` |
| `POST /v1/projects/{p}/book/pages` | Add a page | `{kind, layout?}` | 201 |
| `PATCH /v1/projects/{p}/book/pages/{id}` | Move or edit | `{idx?}` | 200 |
| `DELETE /v1/projects/{p}/book/pages/{id}` | Remove | | 204 |
| `POST /v1/projects/{p}/book/cover` | Set or generate cover | `{from_panel?, generate?}` | 200 or 202 |
| `POST /v1/projects/{p}/exports` | Export | `{target, target_id?, format, dpi?, print?, single_file?}` | 202 `JobRef` |
| `GET /v1/projects/{p}/exports` | List exports | | 200 |
| `GET /v1/jobs/{id}` | Job status | | 200 `Job` |
| `POST /v1/jobs/{id}/cancel` | Cancel | | 200 `Job` |
| `GET /v1/assets/{sha}` | Fetch an asset (immutable, long cache) | | 200 bytes |
| `POST /v1/projects/{p}/assets` | Upload an image (ingest rules apply) | multipart `file` | 201 `AssetRef` |
| `POST /v1/projects/{p}/undo` | Undo | | 200 `Event` or 204 |
| `POST /v1/projects/{p}/redo` | Redo | | 200 or 204 |
| `GET /v1/projects/{p}/history` | Event history | `?limit=&after=` | 200 `Event[]` |
| `GET /v1/styles` | Built-in and library styles | | 200 |
| `GET /v1/library` | Library items | `?kind=` | 200 |
| `POST /v1/library` | Add item from project | `{project, kind, item_id}` | 201 |
| `POST /v1/projects/{p}/library/import` | Import | `{item_id}` | 201 |
| `GET /v1/backends` | Image backends and capabilities | | 200 `BackendInfo[]` |
| `POST /v1/recommend` | Style, audience, arc suggestion | `{description}` | 200 `Recommendation` |
| `GET /v1/doctor` | Doctor report | | 200 `DoctorReport` |
| `POST /v1/session` | Join with access code (LAN mode) | `{access_code, name}` | 200, sets session cookie, returns CSRF token |
| `GET /v1/workspaces` | Teacher view | | 200 (classroom mode) |
| `GET /v1/openapi.json` | OpenAPI document | | 200 |
| `GET /healthz`, `GET /readyz` | Liveness and readiness probes (ADR-020) | | 200 or 503 |
| `GET /v1/healthz`, `GET /v1/readyz` | Same bodies, includes `version` | | 200 or 503 |
| `WS /v1/events?project={p}` | Job progress and entity changes | | upgrade |

`/readyz` reflects backend, LLM, vision, embeddings, and Chromium readiness (S7-T01) and returns 503 with the failing checks when any required dependency is down. Rate limits (per session) apply to generation endpoints: suggestions, strip creation, render, retake, edit, auto, export.

### 7.4 Authentication summary for REST **(added)**

| Mode | Credential | Notes |
|---|---|---|
| Localhost (default) | None | Bind `127.0.0.1`; Origin check still applies. |
| LAN studio | Access code exchanged at `POST /v1/session` for a session cookie (`HttpOnly`, `SameSite=Strict`) plus CSRF token | Code min 8 chars. |
| Server on non-localhost | `Authorization: Bearer <COMIC_SMITH_SERVER_TOKEN>` | Required; server refuses to start on a non-localhost bind without a token. |

### 7.5 WebSocket events

Endpoint: `WS /v1/events?project={p}`. Messages are JSON text frames. Every message has the envelope `{event, project_id, ts, data}`.

| Event | `data` payload | Sent when |
|---|---|---|
| `job.progress` | `{job_id: str, kind: str, stage: str, pct: number}` (`pct` 0 to 100) | A job advances (per panel, per backend step) |
| `job.done` | `{job_id: str, kind: str, result: object}` (result holds ids of created entities or asset ids) | Job finished successfully |
| `job.failed` | `{job_id: str, kind: str, error: Problem}` (Problem is the RFC 9457 object, section 10.3) | Job failed or was cancelled (`error.code = "job_cancelled"`) |
| `entity.changed` | `{type: str, id: str}` (`type` one of `project`, `bible`, `character`, `style`, `branch`, `strip`, `panel`, `take`, `suggestion_set`, `story`, `page`, `book`, `export`) | Any committed mutation; Studio invalidates TanStack Query caches |
| `qa.flagged` | `{panel_id: str, reasons: str[]}` (reasons such as `character_score_low:ch_puddle:3`, `text_detected`, `audience`) | QA flagged a take |
| `suggestions.ready` | `{set_id: str}` | A suggestion set is stored |

WebSocket events update query caches, never ad hoc state (TypeScript standards). Delivery is at-most-once; clients reconcile with `GET /v1/jobs/{id}` after reconnect. The server sends a ping every 20 seconds.

### 7.6 MCP tools

Server: official Python MCP SDK (`mcp>=1.2`), `mr-comic-smith mcp [--transport stdio|http]` (stdio and streamable HTTP). Tools call `comic_smith.api` only (ADR-015). Tool descriptions state the originality and people rules so agents do not attempt to bypass them. Tool names, argument names, and return shapes below are exactly as in the Prompt (Appendix E). Types: `?` marks optional; paths are absolute filesystem paths on the machine running the server.

| Tool | Input | Output | Notes |
|---|---|---|---|
| `mr_comic_smith_create_project` | `{name: str, narrative?: str, image_paths?: str[], style?: str, audience?: str, target_strips?: int}` | `{project_id: str, characters: [{id: str, name: str, needs_approval: bool}], bible_summary: str}` | Fails with the safety errors when the seed or an image is blocked. |
| `mr_comic_smith_approve_character` | `{project_id: str, character_id: str}` | `{approved: bool, originality_ok: bool}` | If `originality_ok` is false, the character is not approved and the reason is in the error hint. |
| `mr_comic_smith_suggest_next` | `{project_id: str, branch?: str}` | `{options: [{idx: int, intent: str, beat: str, description: str}], end_here?: object}` | `idx` is 1 to 3; `end_here` present when applicable. |
| `mr_comic_smith_make_strip` | `{project_id: str, pick?: int \| "end", beat?: str, panels?: int, render?: bool = true}` | `{strip_id: str, panels: [{idx: int, image_path: str, qa: object}], strip_image_path: str}` | Exactly one of `pick` or `beat`. Long-running: emits MCP progress notifications per panel (`progress`, `total`, `message`). |
| `mr_comic_smith_edit_panel` | `{project_id: str, panel_id: str, changes: object}` | `{panel_id: str, image_path: str}` | `changes` is a partial Panel Spec and optional `lettering`; visual changes trigger a retake. |
| `mr_comic_smith_finalize` | `{project_id: str, title?: str}` | `{story_id: str, continuity_issues: object[], titles: str[]}` | |
| `mr_comic_smith_build_book` | `{project_id: str, layout?: str, size?: str, cover?: bool = true}` | `{book_id: str, pages: object[]}` | |
| `mr_comic_smith_export` | `{project_id: str, target: "page" \| "story" \| "book", formats: str[]}` | `{files: str[]}` | `files` are absolute paths. |
| `mr_comic_smith_list_styles` | `{}` | `[{id: str, name: str, description: str}]` | |
| `mr_comic_smith_list_backends` | `{}` | `[{id: str, available: bool, local: bool, references: int, edit: bool, license: str}]` | From `ImageCapabilities`; `references` is `max_reference_images`; `edit` is `supports_edit`. |
| `mr_comic_smith_status` | `{}` | doctor report JSON | |
| `mr_comic_smith_recommend` | `{description: str}` | `{style: str, audience: str, arc_template: str, target_strips: int, reason: str}` | |

Example JSON Schema for `mr_comic_smith_make_strip` input (all tool inputs are generated from pydantic models in `mcp_server/tools.py` in the same way):

```json
{
  "type": "object",
  "properties": {
    "project_id": {"type": "string"},
    "pick": {"oneOf": [{"type": "integer", "minimum": 1, "maximum": 3}, {"const": "end"}]},
    "beat": {"type": "string", "minLength": 1, "maxLength": 500},
    "panels": {"type": "integer", "minimum": 1, "maximum": 6, "default": 4},
    "render": {"type": "boolean", "default": true}
  },
  "required": ["project_id"],
  "oneOf": [{"required": ["pick"]}, {"required": ["beat"]}],
  "additionalProperties": false
}
```

Error mapping: MCP tool errors return `isError: true` with a text block containing `code`, `message`, and `hint` from the `ComicSmithError`; no stack traces. Tools never expose a bypass for originality, people attestation, or audience guards (ADR-013).

### 7.7 ImageBackend, ImageCapabilities, ImageRequest, GeneratedImage

```python
from typing import Callable, Protocol
from pydantic import BaseModel, Field

class AssetRef(BaseModel):
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    mime: str
    width: int | None = None
    height: int | None = None

class PreflightIssue(BaseModel):
    severity: Literal["error", "warning", "info"]
    code: str                    # e.g. "comfyui_unreachable", "model_missing", "noncommercial_gate"
    message: str
    hint: str | None = None      # actionable fix, shown by doctor

class ProgressEvent(BaseModel):
    stage: str                   # e.g. "queued", "sampling", "decoding"
    pct: float                   # 0 to 100
    message: str | None = None

ProgressFn = Callable[[ProgressEvent], None]

class ImageCapabilities(BaseModel):
    max_reference_images: int
    supports_edit: bool          # inpaint / instruction edit
    supports_seed: bool
    sizes: list[tuple[int, int]]
    aspect_ratios: list[str]
    license: str
    commercial_ok: bool
    local: bool

class ImageRequest(BaseModel):
    prompt: str
    negative_prompt: str | None
    reference_assets: list[AssetRef]
    width: int
    height: int
    seed: int | None
    steps: int | None
    edit_of: AssetRef | None = None
    mask: AssetRef | None = None

class GeneratedImage(BaseModel):          # added: the Prompt names the type but not its fields
    data: bytes                           # encoded PNG; the caller stores it via assets.store
    mime: str = "image/png"
    width: int
    height: int
    seed: int | None                      # the seed actually used, when the backend reports it
    backend: str                          # backend id
    model: str                            # workflow or model id
    metadata: dict[str, str] = {}         # non-secret provenance (workflow name, node versions)

class ImageBackend(Protocol):
    id: str
    def capabilities(self) -> ImageCapabilities: ...
    def preflight(self) -> list[PreflightIssue]: ...
    def generate(self, req: ImageRequest, progress: ProgressFn) -> GeneratedImage: ...
```

Contract rules **(added)**:

- `generate` is synchronous from the caller's view; backends that stream (ComfyUI WebSocket) bridge internally. It must call `progress` at least at start and end, and honor cancellation through a `threading.Event` exposed by the job runner (ComfyUI: `POST /interrupt`).
- The compiler never exceeds `max_reference_images` and picks `width` x `height` from `sizes` closest to the panel aspect ratio; unsupported features raise `PreflightError` with code `capability_missing`, not a silent drop. The Studio disables UI affordances using `capabilities()`.
- `supports_edit` gates `inpaint_panel`; without it, inpaint falls back to retake with the instruction appended and a notice.
- A backend with `commercial_ok = false` is unavailable unless `COMIC_SMITH_ALLOW_NONCOMMERCIAL=true` (the registry marks it with a `noncommercial_gate` preflight error). Opt-in is stored in `project.noncommercial_opt_in` and export metadata.
- Cloud backends (`local = false`) send prompts and reference images off-machine; the first use shows a notice listing what is sent; the Studio shows a persistent "cloud" badge.
- `ImageRequest` objects are stored in `take.prompt_json` with secrets excluded; request hashing for caching uses a canonical form (section 9.1).
- Registry: `backends.image.registry.get(id) -> ImageBackend` and `available() -> list[BackendInfo]`. Ids: `comfyui`, `gemini`, `openai`, `mock`.

### 7.8 LLMProvider, VisionProvider, EmbeddingsProvider

```python
from typing import Any, Protocol
from pydantic import BaseModel

class BoundingBox(BaseModel):
    label: str                   # target text, e.g. "ch_puddle" or "ch_puddle:head"
    x: float                     # fractions of image width/height in [0, 1], origin top-left
    y: float
    w: float
    h: float
    confidence: float            # 0.0 to 1.0

class LLMProvider(Protocol):
    id: str                      # "ollama", "anthropic", "openai_compat", "fake"
    def preflight(self) -> list[PreflightIssue]: ...
    def complete_json(self, system: str, user: str, schema: dict[str, Any], *,
                      temperature: float, seed: int | None) -> dict[str, Any]: ...

class VisionProvider(Protocol):
    id: str
    def preflight(self) -> list[PreflightIssue]: ...
    def describe(self, image: AssetRef, instruction: str, schema: dict[str, Any]) -> dict[str, Any]: ...
    def locate(self, image: AssetRef, targets: list[str]) -> list[BoundingBox]: ...

class EmbeddingsProvider(Protocol):      # added: needed by the suggestion distinctness check (FR-011)
    id: str                              # "ollama", "openai_compat", "fake"
    dimensions: int | None               # None until first call when unknown
    def preflight(self) -> list[PreflightIssue]: ...
    def embed(self, texts: list[str]) -> list[list[float]]: ...   # one L2-normalized vector per text
```

Contract rules **(added)**:

- `complete_json` returns a dict that validates against `schema` (the provider enforces constrained decoding where supported, such as Ollama structured outputs; otherwise it validates and retries once internally). On final failure it raises `LLMOutputInvalidError` (exit 5). `temperature` is explicit at every call site: 0.8 for interactive suggestions, 0 for auto mode, tests, and normalization.
- Prompt hygiene: untrusted text (story text, user beats, reference descriptions) is wrapped in delimiters with explicit instructions and passed in `user`; `system` contains only templates from `story/prompts/` (versioned). Providers never receive secrets.
- `describe` returns JSON validated against the supplied schema; images are passed as stored asset bytes.
- `locate` returns boxes for each target found; a target not found is absent from the list (not an error).
- `EmbeddingsProvider.embed` is called with the three option texts. Default `ollama:nomic-embed-text`; `fake` returns deterministic hash-based vectors so distinctness tests are stable. Cosine similarity of the L2-normalized vectors is the dot product.
- `fake` providers return canned or schema-synthesized output and never touch network (unit-test requirement).
- Timeouts: every provider call has a timeout (default 120 s text, 300 s image) and a retry policy of two attempts with backoff for transient transport errors; non-retryable errors surface immediately.

---

## 8. Job system

### 8.1 Queue and claiming

Jobs live in the `job` table of the project database (ADR-011). A worker claims a job atomically:

```sql
UPDATE job
SET status = 'running', started_at = :now, attempts = attempts + 1
WHERE id = (
  SELECT id FROM job
  WHERE status = 'queued' AND worker_class = :class AND cancel_requested = 0
  ORDER BY priority ASC, created_at ASC
  LIMIT 1
)
RETURNING *;
```

(Lower priority numbers run first.) In classroom mode the inner SELECT adds round-robin fairness: it prefers the `workspace_id` with the oldest `started_at` among running or recently finished jobs, then falls back to `priority, created_at` (S7-T02).

### 8.2 Worker classes, kinds, priorities

| Worker class | Count | Handles |
|---|---|---|
| `gpu` | 1 | `panel.render`, `panel.retake`, `panel.edit`, `sheet.generate`, `suggestion.thumbnail`, `cover.generate` when the image backend is local |
| `cloud_image` | 2 (concurrency, configurable) | Same kinds when the image backend is a cloud backend |
| `text` | N (default 2) | `suggestions.generate`, `strip.write`, `vision.describe`, `qa.check`, `finalize.review`, `auto.run` |
| `export` | 1 (default) | `export` (Chromium); scales out as stateless pods in Kubernetes |

Priorities (lower runs first), from the Prompt:

| Priority | Jobs |
|---|---|
| 0 | Interactive panel render (`panel.render`, `panel.retake`, `panel.edit`, `sheet.generate`) |
| 5 | Suggestion thumbnails (`suggestion.thumbnail`) |
| 7 | Exports (`export`) |
| 9 | Auto mode (`auto.run` and the jobs it spawns) |

Other text jobs default to priority 1 **(added)**.

### 8.3 Lifecycle

`queued` -> `running` -> `done` | `failed` | `cancelled`.

- Progress: workers call `jobs.progress.report(job_id, stage, pct)`, which updates `job.progress` and publishes `job.progress` on the event bus (WebSocket). Final states publish `job.done` or `job.failed`.
- Retries: failures retried twice for transient backend errors (FR-016) with exponential backoff (2 s, 8 s); `attempts` counts claims. After the second retry the job is `failed` with `error_json` set.
- Cancellation: setting `cancel_requested = 1` (and `status = 'cancelled'` for queued jobs). Running jobs poll the flag between steps; ComfyUI jobs also call `POST /interrupt`. A cancelled render discards the partial take.
- Crash recovery: on server start, jobs left `running` whose worker is gone are re-queued if idempotent (renders are, because takes are only recorded on completion) or marked `failed` with `error.code = "worker_lost"` (NFR-006).
- Idempotency: a job's effects are applied in one transaction with its completion event; a repeated claim cannot double-create takes because take ids derive from `(job_id, attempt)`.
- Auto mode runs as a parent `auto.run` job that enqueues child jobs at priority 9.

### 8.4 Concurrency invariants

- Only one GPU worker per project database (ADR-021) so a single local GPU is never oversubscribed.
- Text workers do not hold write transactions across LLM calls; they write results in short transactions.
- SQLite WAL permits concurrent readers (Studio queries) during worker writes.

---

## 9. Caching model

### 9.1 Keys

`H(...)` is SHA-256 over canonical JSON: UTF-8, object keys sorted, no insignificant whitespace, floats formatted with `repr`, with a leading namespace string. One module (`comic_smith.cache.keys` **(added)**, under infrastructure) computes all keys; no stage builds ad hoc keys.

| Cache | Key | Value location | When used |
|---|---|---|---|
| Compiled prompts and generated images | `H("img", compiled_request, backend, model, seed)` | asset in the store (via `take` lookup by the key stored in `take.prompt_json.cache_key`) | Identical requests reuse the asset; applies only when `seed` is not null |
| LLM outputs | `H("llm", prompt_template_version, inputs, provider, model, seed)` | `cache_entry(kind='llm')` | Only when `temperature == 0` (auto mode, normalization, tests). Interactive suggestions use temperature 0.8 and are not cached |
| Vision QA results | `H("qa", asset_sha, character_sheet_version, qa_prompt_version)` | `cache_entry(kind='vision_qa')` | Every QA pass |
| Embeddings **(added)** | `H("emb", provider, model, text)` | `cache_entry(kind='embedding')` | Suggestion distinctness |

### 9.2 Rules

- Prompt templates carry versions that are part of the keys; changing a template changes the keys and is at least a PATCH release noted under "Changed" in the changelog.
- Image cache hits still create a new `take` row pointing at the existing asset (so history stays honest) and record `qa_json` from the QA cache.
- A retake always uses a new seed, so it never hits the image cache.
- No cache stores secrets. Cloud backend responses are cached only as image assets.
- Invalidation: bumping `character.sheet_version` changes QA keys; editing a style or the Panel Spec changes the compiled request and so the image key. No time-based expiry; `gc` prunes `cache_entry` rows older than 90 days **(added)**.

---

## 10. Error model

All errors raised by core code are `ComicSmithError` subclasses (`errors.py`). Bare `except Exception` without conversion is forbidden; `sys.exit` happens only in `cli.py`.

```python
class ComicSmithError(Exception):
    code: str                  # stable snake_case id, part of the public contract
    stage: str                 # pipeline stage: cli, config, preflight, ingest, cast, story, render, qa, letter, layout, book, export, job, server, mcp
    message: str               # plain words for the user
    hint: str | None           # next action in plain words
    retryable: bool
    exit_code: int             # CLI mapping
    http_status: int           # REST mapping
    detail: str | None         # technical detail; Studio shows it behind a "details" toggle
```

### 10.1 Hierarchy

| Class | `code` | `stage` | Exit | HTTP | `retryable` |
|---|---|---|---|---|---|
| `ComicSmithError` (base) | `internal_error` | any | 1 (reserved) | 500 | false |
| `UsageError` | `usage_invalid` | cli | 2 | 400 | false |
| `ConfigError` (subclass of `UsageError`) | `config_invalid` | config | 2 | 400 | false |
| `ProviderStringError` (subclass of `ConfigError`) | `provider_string_invalid` | config | 2 | 400 | false |
| `PreflightError` | `preflight_failed` | preflight | 3 | 503 | true (after the hint is applied) |
| `BackendUnavailableError` (subclass of `PreflightError`) | `backend_unavailable` | preflight | 3 | 503 | true |
| `ModelMissingError` (subclass of `PreflightError`) | `model_missing` | preflight | 3 | 503 | true |
| `ChromiumUnavailableError` (subclass of `PreflightError`) | `chromium_unavailable` | preflight | 3 | 503 | true |
| `NoncommercialGateError` (subclass of `PreflightError`) | `noncommercial_not_allowed` | preflight | 3 | 403 | false |
| `CapabilityMissingError` (subclass of `PreflightError`) | `capability_missing` | preflight | 3 | 422 | false |
| `SafetyError` | `safety_blocked` | story, cast, ingest | 4 | 422 | false |
| `OriginalityBlockedError` (subclass of `SafetyError`) | `originality_blocked` | cast | 4 | 422 | false |
| `PersonAttestationRequiredError` (subclass of `SafetyError`) | `person_attestation_required` | cast | 4 | 422 | false |
| `AudienceBlockedError` (subclass of `SafetyError`) | `audience_blocked` | story | 4 | 422 | false |
| `UploadRejectedError` (subclass of `SafetyError`) | `upload_rejected` | ingest | 4 | 415 or 413 | false |
| `GenerationInvalidError` | `generation_invalid` | story | 5 | 502 | true |
| `SchemaValidationError` (subclass of `GenerationInvalidError`) | `schema_invalid` | story | 5 | 502 | true |
| `LLMOutputInvalidError` (subclass of `GenerationInvalidError`) | `llm_output_invalid` | story | 5 | 502 | true |
| `PrerequisiteError` (subclass of `GenerationInvalidError`) | `prerequisite_unmet` | story, panels, layout | 5 | 409 | false |
| `RenderError` | `render_failed` | render | 6 | 502 | true |
| `ImageGenerationError` (subclass of `RenderError`) | `image_generation_failed` | render | 6 | 502 | true |
| `QaBlockedError` (subclass of `RenderError`) | `qa_blocked` | qa | 6 | 422 | false |
| `LetteringError` (subclass of `RenderError`) | `lettering_failed` | letter | 6 | 422 | false |
| `JobCancelledError` (subclass of `RenderError`) | `job_cancelled` | job | 6 | 409 | false |
| `ExportError` | `export_failed` | export | 7 | 500 | true |
| `PdfPostprocessError` (subclass of `ExportError`) | `pdf_postprocess_failed` | export | 7 | 500 | true |
| `PackagingError` (subclass of `ExportError`) | `packaging_failed` | export | 7 | 500 | true |
| `ProjectError` | `project_error` | server, cli | 8 | 409 | false |
| `ProjectNotFoundError` | `project_not_found` | cli, server | 8 | 404 | false |
| `ProjectLockedError` | `project_locked` | cli, server | 8 | 423 | true |
| `ProjectMigrationError` | `project_migration_failed` | cli, server | 8 | 500 | false |
| `ImmutableEntityError` | `entity_immutable` | story | 8 | 409 | false |
| `AuthError` (REST and MCP only) | `unauthorized` | server | 3 (remote CLI) | 401 or 403 | false |
| `RateLimitError` (REST only) | `rate_limited` | server | 3 (remote CLI) | 429 | true |

`QaBlockedError` is raised when a panel stays below `QA_MIN_SCORE` after `QA_MAX_RETAKES` and the user tries to approve without overriding the QA flag; normally QA failures are flags, not errors (the best take is kept and the panel is marked). The `stage` values listed are the defaults; a subclass may carry a more specific stage. Several classes outside the safety family (`UploadRejectedError`) map to 4 by design: blocked by safety policy.

### 10.2 User-facing behavior

- Studio shows `message` and `hint` in plain words; `detail` appears behind a "details" toggle. No stack traces reach the UI, logs at `info` level, or MCP responses.
- Logs (structlog) record `code`, `stage`, and `retryable`; secrets are redacted by key pattern (`*key*`, `*token*`, `*secret*`).
- `retryable` is advisory: `true` means a retry or a fix of the stated hint may succeed. Workers retry only transient classes (`ImageGenerationError`, transport errors).

### 10.3 RFC 9457 mapping

REST errors use `application/problem+json`. A `ComicSmithError` maps to:

```json
{
  "type": "https://getcomicsmith.com/problems/originality_blocked",
  "title": "Originality check blocked this request",
  "status": 422,
  "detail": "The description names a copyrighted character (denylist rule: franchise-names).",
  "instance": "/v1/projects/prj_01J.../characters",
  "code": "originality_blocked",
  "stage": "cast",
  "hint": "Describe an original character instead, without naming an existing one.",
  "retryable": false
}
```

Rules: `type` is `https://getcomicsmith.com/problems/{code}` (resolvable docs page per code); `title` is a short fixed summary per class; `status` is the HTTP status in the table; `detail` is `message` (plain words), with technical detail only under an extension member `technical` when the request carries `X-Debug: 1` and the caller is authorized; `instance` is the request path; `code`, `stage`, `hint`, `retryable` are extension members. Validation errors on request bodies use `type = .../usage_invalid` with an `errors` array of `{pointer, message}` (JSON Pointer, per RFC 9457 guidance). The CLI with `--json` prints the same object; without it prints `message` and `hint`. The same object is the `error` field of `job.failed` and `job.error_json`.

---

## 11. Security and safety model

This section expands the Security Guidelines. Safety guards live in core services (ADR-013): the CLI, REST, MCP, and Studio inherit them, and no flag disables them in v1.

### 11.1 Trust boundaries

| Boundary | Untrusted input | Control |
|---|---|---|
| Upload | Image files, filenames | Magic-byte sniffing, allowlist, size and pixel limits, re-encode, EXIF strip |
| Narrative and beats | Free text from users and agents | Delimited insertion into prompts, JSON Schema constrained output, denylist and audience moderation |
| Model output | LLM, vision, image outputs | Schema validation, XML escaping, QA, audience check on images |
| HTTP clients | Requests to the server | Bind address, auth, CSRF, Origin, rate limits, CSP, path confinement |
| Renderer | Chromium loading generated SVG/HTML | No network, fresh profile, timeouts, no user-supplied markup |
| Supply chain | Dependencies, model weights, ComfyUI nodes | Locked installs, audits, pinned revisions, SHA-256 verification, signed images |

### 11.2 Uploads and assets

- Sniff types by magic bytes; allow PNG, JPEG, WebP, and HEIC only; maximum 20 MB per file; reject decompression bombs with `Image.MAX_IMAGE_PIXELS` set explicitly (constant `MAX_IMAGE_PIXELS = 100_000_000` **(added)**). Failures raise `UploadRejectedError`.
- Strip all EXIF and XMP (location, device) on ingest; store only re-encoded pixels (FR-002).
- Assets are immutable and served with `Content-Type` from the asset table, `X-Content-Type-Options: nosniff`, and `Content-Disposition` for downloads. Asset ids are content hashes; there is no user-controlled path component.
- No user-uploaded SVG is accepted anywhere. All SVG is generated by the lettering and layout engines from typed data; text content is XML-escaped (`xml.sax.saxutils.escape` plus attribute quoting) and fonts are embedded from the bundled registry only.
- All user-derived file names go through `safe_slug()`; all writes through `atomic_write()`; paths are confined to the data directory and checked with `Path.resolve()` against the root before use.
- Fixture photos in the repository are the maintainer's own; real photos of people and generated images of real people are never committed.

### 11.3 Studio and server

- Default bind `127.0.0.1`. LAN mode (`studio --lan`) requires `--access-code` (minimum 8 characters) and issues a session cookie (`HttpOnly`, `SameSite=Strict`, `Secure` when served over TLS). Server mode on a non-localhost bind requires `COMIC_SMITH_SERVER_TOKEN` and refuses to start without it.
- Access code and token comparison use constant-time comparison; failed attempts are rate limited and logged without the submitted value.
- CSRF: state-changing requests require a per-session header token (`X-CSRF-Token`); `Origin` is checked against the served origin; WebSocket upgrades check `Origin` and the session.
- CSP for Studio (set by the server on HTML responses):

```
default-src 'self'; img-src 'self' blob: data:; font-src 'self' data:; connect-src 'self' ws: wss:; script-src 'self'; style-src 'self' 'unsafe-inline'; frame-ancestors 'none'
```

- Additional headers **(added)**: `X-Content-Type-Options: nosniff`, `Referrer-Policy: no-referrer`, `Cross-Origin-Opener-Policy: same-origin`.
- Rate limits per session on generation endpoints (suggestions, strips, render, retake, edit, auto, export); exceeded limits return 429 `rate_limited` with `Retry-After`.
- Path traversal guards on every file operation; project paths are confined to the data directory.
- Classroom mode: users see only their projects unless shared; the teacher view lists all; job fairness is round-robin by workspace.

### 11.4 Export renderer

- Chromium is launched per job with the network blocked (Playwright route abort for anything not `data:` or the local file root), no extensions, a fresh profile, and a timeout per page (`EXPORT_PAGE_TIMEOUT_S = 60` **(added)**).
- JavaScript in the export context is limited to the bundled reader; page SVGs are static documents with embedded fonts and images as data URIs or local files under the job's temp root.
- The web export reader has no network calls, no `eval`, and no third-party scripts, works from `file://`, and respects `prefers-reduced-motion`.
- Exports embed metadata (title, author, year, language, and `noncommercial_models_used`) and never embed API keys, absolute local paths, or EXIF-like device data.

### 11.5 Model and prompt safety

- Story text, user beats, and reference descriptions are untrusted when inserted into prompts: wrapped in delimiters with explicit instructions; outputs constrained by JSON Schema, so injected instructions cannot change structure.
- Originality guard (FR-006): a denylist (`cast/denylist.yaml`, configurable, starter set shipped) applied to all user text and compiled prompts, plus a vision-model resemblance question on each approved sheet. A match names the rule that triggered and asks for a design change. No override flag in v1. Style transfer from copyrighted artists is blocked by design.
- People attestation (FR-007): a person detected in a reference requires an attestation of the right to use the likeness; the character is stylized (never photoreal); photoreal presets are disabled for it; requests to depict public figures are declined by the story and prompt layers.
- Audience guard (FR-028): audience rules in system prompts; moderation passes on every generated beat, script, and compiled image prompt; image outputs checked by the vision model for suitability; blocked content explained in plain words. Per-audience reading-level limits are enforced by validation (for example `kids-5-8`: 10 words per balloon, 2 balloons per panel).
- Non-commercial model weights require explicit opt-in (`COMIC_SMITH_ALLOW_NONCOMMERCIAL`); the choice is recorded in project metadata and in export metadata (NFR-011).
- Guards are tested as part of the safety review (S6-T03) and results recorded in `docs/SECURITY_REVIEW.md`.

### 11.6 Dependencies and supply chain

- `uv.lock` and `bun.lockb` are committed; CI installs frozen.
- `pip-audit`, `npm audit --audit-level=high`, `gitleaks`, and Dependabot run in CI.
- Model downloads happen over HTTPS with pinned revisions and SHA-256 verification (`models pull`). ComfyUI custom nodes required by workflows are pinned by commit hash and listed in `THIRD_PARTY_LICENSES.md`.
- Docker images run as non-root with a read-only root filesystem and are signed with cosign (keyless); releases ship CycloneDX SBOMs, npm provenance, and PyPI attestations.
- Licenses of dependencies, models, and fonts are recorded in `THIRD_PARTY_LICENSES.md` and checked by `pip-licenses` and `license-checker` (NFR-011).

### 11.7 Privacy

- Zero telemetry; no analytics in Studio or reader (NFR-002).
- Local-first defaults (Ollama plus ComfyUI): with default config no text or image leaves the machine (NFR-001). Cloud backends show a persistent "cloud" badge and a first-use notice listing what is sent (prompts and reference images).
- API keys come from the environment or the OS keyring only (`keyring`); they are never written to project files, exports, or logs. Logs redact values for keys matching `*key*`, `*token*`, `*secret*`.
- Deleting a project moves it to the OS trash (or `.trash/`); `gc` removes unreferenced assets.

---

## 12. Deployment topologies and configuration

### 12.1 Topologies

| # | Topology | Components | Notes |
|---|---|---|---|
| 1 | Laptop with cloud image backend | `uv tool install mr-comic-smith[gemini]`; `studio` on `127.0.0.1:7351`; Ollama local or `anthropic`/`openai_compat` LLM; `gemini` or `openai` image backend | No GPU needed. Cloud badge and notice shown. Chromium installed by `doctor --fix`. |
| 2 | Workstation or GPU box, fully local | ComfyUI (pinned commit, `qwen-image-edit` workflow) + Ollama (`qwen3:14b`, `qwen2.5vl:7b`, `nomic-embed-text`) + `mr-comic-smith` | 24 GB VRAM recommended for default workflow at full precision; quantized variants for smaller cards (verify at implementation time). No data leaves the machine. |
| 3 | LAN classroom | One GPU box running `mr-comic-smith studio --lan --access-code CODE` (Compose tier 2 or local install) | Per-user workspaces in one instance, teacher view, GPU job fairness. Studio on port `7351`. |
| 4 | Kubernetes | Helm chart `charts/mr-comic-smith`; 2-node GPU cluster supported (`values-k3s-gpu.yaml`) | Single replica for `comic-smith` in v1 (SQLite job queue and project databases on one volume). |

Tiers (Appendix G): Tier 1 local install (`uv tool install`, `pipx`, `doctor --fix`; ComfyUI and Ollama installed by the user via their official installers; `models pull` fetches workflow models), Tier 2 Docker Compose, Tier 3 Kubernetes via Helm.

#### Docker Compose (tier 2)

`deploy/docker-compose.local.yml` runs `ollama` (GPU), `ollama-pull` (pulls `qwen3:14b`, `qwen2.5vl:7b`, `nomic-embed-text`), `comfyui` (image `ghcr.io/serverless-ventures/mr-comic-smith-comfyui`, health check on `/system_stats`, models volume), `models-pull` (runs `mr-comic-smith models pull qwen-image-edit --comfyui-models /models`), and `comic-smith` (runs `studio --host 0.0.0.0 --lan --access-code "${COMIC_SMITH_ACCESS_CODE:?set an access code}"`, publishes `7351:7351`, data volume `/var/lib/comic-smith`, env `COMIC_SMITH_IMAGE_BACKEND=comfyui`, `COMIC_SMITH_COMFYUI_URL=http://comfyui:8188`, `COMIC_SMITH_LLM=ollama:qwen3:14b`, `COMIC_SMITH_VISION=ollama:qwen2.5vl:7b`, `OLLAMA_HOST=http://ollama:11434`). It depends on healthy `comfyui` and completed `models-pull` and `ollama-pull`.

`deploy/docker-compose.prod.yml`: images pinned by digest, resource limits, read-only root filesystems with writable volumes only, internal network for ollama and comfyui (no published ports), comic-smith behind a TLS reverse proxy, restart policies, log rotation, server token and access code from secrets.

Images: `Dockerfile.cpu` (python slim, Chromium deps, non-root, Studio bundled, under 1.5 GB), `Dockerfile.cuda` (CUDA runtime base for future in-process backends; same app), `Dockerfile.comfyui` (pinned ComfyUI commit, custom nodes pinned by commit, no weights baked in); multi-arch amd64 and arm64; published to `ghcr.io/serverless-ventures/mr-comic-smith:{version, version-cuda, latest}` and signed.

#### Kubernetes via Helm (tier 3)

- StatefulSet `comfyui`: `nvidia.com/gpu: 1` via the NVIDIA device plugin; PVC `comfy-models` (100Gi); init container runs `models pull` with checksum verification; readiness on `/system_stats`.
- StatefulSet `ollama` (optional): PVC 50Gi; init job pulls story, vision, and embedding models. Alternatively configure an existing OpenAI-compatible vLLM endpoint (on NVIDIA Grace arm64 nodes, `nvcr.io/nvidia/vllm-openai:latest`).
- StatefulSet `comic-smith` (single replica in v1): PVC `data` (50Gi); Secret for server token and access code; liveness `/healthz`, readiness `/readyz`.
- Deployment `comic-smith-export` (optional, HPA on CPU): stateless Chromium export workers reading shared storage via ReadWriteMany PVC.
- Ingress: TLS, `proxy-read-timeout: 900`, `proxy-body-size: 25m` (uploads), WebSocket upgrade enabled.
- NetworkPolicy: only comic-smith pods reach comfyui and ollama.
- `values-k3s-gpu.yaml` for a 2-node k3s + Cilium GPU cluster: comfyui on node A, ollama on node B, comic-smith on either.
- Chart `version` and `appVersion` are kept in sync with `pyproject.toml` by `scripts/bump-version.sh`.

### 12.2 Configuration precedence

Order, highest first: **flags > environment variables > `comic-smith.toml` > built-in defaults.**

- Environment variables use the prefix `COMIC_SMITH_`; the provider keys `GEMINI_API_KEY`, `OPENAI_API_KEY`, `ANTHROPIC_API_KEY` and `OLLAMA_HOST` keep their conventional names.
- `comic-smith.toml` is searched in the order: `--config PATH`, `./comic-smith.toml`, the user config directory (`~/.config/comic-smith/comic-smith.toml` on Linux and macOS) **(added)**. `comic-smith.toml.example` documents every key. Secrets are never read from the TOML file; a key named like a secret in the file is a `ConfigError`.
- Configuration is a `pydantic-settings` model validated at startup; invalid values raise `ConfigError` (exit 2) naming the key and source.

Example `comic-smith.toml` **(added key layout; keys mirror env var names without the prefix, lower case)**:

```toml
env = "prod"
data_dir = "~/ComicSmith"
log_level = "info"
log_format = "pretty"
image_backend = "comfyui"
comfyui_url = "http://127.0.0.1:8188"
comfyui_workflow = "qwen-image-edit"
allow_noncommercial = false
llm = "ollama:qwen3:14b"
vision = "ollama:qwen2.5vl:7b"
embeddings = "ollama:nomic-embed-text"
qa_min_score = 4
qa_max_retakes = 2
studio_port = 7351
server_host = "127.0.0.1"
server_port = 7350
default_audience = "all-ages"
```

### 12.3 Environment model and variables

Environments: **dev** (laptop; mock image backend or a cloud key; fake provider or a small Ollama model; everything on localhost), **stage** (GPU box or GPU runner with ComfyUI and Ollama; `studio --lan` for team testing; TestPyPI rc builds), **prod** (released packages on user machines; optional shared server or Kubernetes). The built-in defaults equal the prod column. `.env.dev.example`, `.env.stage.example`, `.env.prod.example` are provided.

| Variable | dev | stage | prod | Notes |
|---|---|---|---|---|
| `COMIC_SMITH_ENV` | `dev` | `stage` | `prod` | |
| `COMIC_SMITH_DATA_DIR` | `./.comic-smith` | `/var/lib/comic-smith` | `~/ComicSmith` | projects, library, exports |
| `COMIC_SMITH_LOG_LEVEL` | `debug` | `info` | `info` | |
| `COMIC_SMITH_LOG_FORMAT` | `pretty` | `json` | `pretty` (CLI) / `json` (server) | |
| `COMIC_SMITH_IMAGE_BACKEND` | `mock` | `comfyui` | `comfyui` (or `gemini`) | |
| `COMIC_SMITH_COMFYUI_URL` | `http://127.0.0.1:8188` | `http://comfyui:8188` | `http://127.0.0.1:8188` | |
| `COMIC_SMITH_COMFYUI_WORKFLOW` | `qwen-image-edit` | `qwen-image-edit` | `qwen-image-edit` | |
| `COMIC_SMITH_ALLOW_NONCOMMERCIAL` | `false` | `false` | `false` | gates flux-kontext-dev |
| `COMIC_SMITH_LLM` | `fake` | `ollama:qwen3:14b` | `ollama:qwen3:14b` | provider string (ADR-017) |
| `COMIC_SMITH_VISION` | `fake` | `ollama:qwen2.5vl:7b` | `ollama:qwen2.5vl:7b` | verify tag at implementation |
| `COMIC_SMITH_EMBEDDINGS` | `fake` | `ollama:nomic-embed-text` | `ollama:nomic-embed-text` | |
| `OLLAMA_HOST` | `http://127.0.0.1:11434` | `http://ollama:11434` | `http://127.0.0.1:11434` | |
| `GEMINI_API_KEY` | unset | optional | optional | cloud image backend |
| `OPENAI_API_KEY` | unset | optional | optional | |
| `ANTHROPIC_API_KEY` | unset | optional | optional | |
| `COMIC_SMITH_QA_MIN_SCORE` | `4` | `4` | `4` | |
| `COMIC_SMITH_QA_MAX_RETAKES` | `2` | `2` | `2` | |
| `COMIC_SMITH_STUDIO_PORT` | `7351` | `7351` | `7351` | |
| `COMIC_SMITH_SERVER_HOST` | `127.0.0.1` | `0.0.0.0` | `127.0.0.1` | non-localhost needs token |
| `COMIC_SMITH_SERVER_PORT` | `7350` | `7350` | `7350` | |
| `COMIC_SMITH_SERVER_TOKEN` | unset | secret | set if exposed | |
| `COMIC_SMITH_DEFAULT_AUDIENCE` | `all-ages` | `all-ages` | `all-ages` | |
| `COMIC_SMITH_ACCESS_CODE` **(added; used by the Compose file)** | unset | secret | secret when LAN | min 8 chars; passed to `studio --access-code` |
| `COMIC_SMITH_OPENAI_COMPAT_URL` **(added)** | unset | optional | optional | base URL for `openai_compat` providers (ADR-017) |

### 12.4 Release and versioning pointers

`pyproject.toml` `[project].version` is the single human-edited version; `scripts/bump-version.sh` propagates it to `web/studio/package.json`, `reader/package.json`, `integrations/pi/package.json`, and the Helm chart; `scripts/check-versions.sh` runs in CI on every PR to `staging` and `main`. The Studio About dialog reads `/v1/healthz` at runtime. Releases are annotated tags on `main` that trigger the release workflow (verify, full CI, build wheel with Studio static assets and fonts, build reader and Pi extension, multi-arch images, cosign signing, SBOMs, publish to PyPI/npm/GHCR/Helm OCI, GitHub Release, docs deploy). MAJOR changes include any change to CLI flags or exit codes, the Python API, REST, WebSocket events, MCP tools, the JSON Schemas, the project database without automatic migration, or reader attributes.

---

## 13. Backend research notes

The Prompt (Implementation Note 9) requires that before each backend is written, its current documentation is read and the findings recorded here, adapting the adapter and not the interface. Everything in this section is an **expectation from the Prompt, not a verified fact**. The status column reads "not yet verified" for every row until the implementing engineer completes the checklist and updates this document in the same PR. Licenses in particular must be confirmed from the model card or license file at the pinned revision, then copied into `THIRD_PARTY_LICENSES.md`.

### 13.1 Image backends and workflows

#### Qwen-Image-Edit via ComfyUI (default local)

| Attribute | Expected | Verify at implementation time | Status |
|---|---|---|---|
| Role | Default local panel and sheet generation with reference conditioning (ADR-006) | Workflow actually accepts multiple reference images, or document the real limit and set `max_reference_images` | Not yet verified |
| License | Apache-2.0 | License text at the pinned revision; any restrictions on outputs | Not yet verified |
| Resources | 24 GB VRAM class at bf16; quantized variants for smaller cards | Real peak VRAM, time per 1024-class panel, quantized options and their quality | Not yet verified |
| ComfyUI integration | Bundled `qwen-image-edit.json` with named slots (prompt, negative, reference, seed, size) | Required custom nodes (pinned by commit), node names, API-format export | Not yet verified |
| Capabilities | `supports_edit` true (instruction edit); seed control; sizes list | Fill `ImageCapabilities` from observed behavior | Not yet verified |

#### FLUX.1 Kontext [dev] via ComfyUI (opt-in)

| Attribute | Expected | Verify at implementation time | Status |
|---|---|---|---|
| Role | Optional reference-editing workflow shipped but gated (ADR-006) | Workflow quality for multi-reference consistency vs the default | Not yet verified |
| License | Non-commercial | Exact license name, scope (weights vs outputs), any output restrictions; gate wording in Studio and docs | Not yet verified |
| Resources | Not stated in the Prompt | VRAM and speed; quantized options | Not yet verified |
| Gate | `COMIC_SMITH_ALLOW_NONCOMMERCIAL=true` required; recorded in project and export metadata | Registry marks `commercial_ok = false` | Not yet verified |

#### SDXL + IP-Adapter via ComfyUI (fallback for smaller GPUs)

| Attribute | Expected | Verify at implementation time | Status |
|---|---|---|---|
| Role | Fallback for smaller GPUs; weaker consistency | Whether QA pass rates can reach NFR-004 with retakes; document the gap | Not yet verified |
| License | OpenRAIL++ for SDXL / Apache-2.0 for IP-Adapter (per the Prompt's table) | License of the exact SDXL checkpoint and IP-Adapter weights used; use-restriction clauses of OpenRAIL++ | Not yet verified |
| Resources | Smaller than the default | Minimum VRAM | Not yet verified |
| Integration | `sdxl-ipadapter.json`; IP-Adapter custom nodes pinned by commit | Node names and versions | Not yet verified |

#### Gemini image generation (default cloud)

| Attribute | Expected | Verify at implementation time | Status |
|---|---|---|---|
| Role | Default cloud backend; multiple reference images | Current model id, max reference images, size and aspect options, seed support | Not yet verified |
| License / terms | Google API terms | Terms for generated image use, content policy limits for stylized people, data handling | Not yet verified |
| SDK | `google-genai>=1.0` (optional extra `gemini`) | Current client API for image output and references | Not yet verified |
| Cost and limits | Not stated in the Prompt | Per-image cost, rate limits, quota behavior for `nightly-cloud.yml` | Not yet verified |

#### OpenAI image generation (second cloud)

| Attribute | Expected | Verify at implementation time | Status |
|---|---|---|---|
| Role | Second cloud backend; edit with masks | Current model id, mask edit support, reference image handling, size options | Not yet verified |
| License / terms | OpenAI API terms | Terms for generated images; content policy | Not yet verified |
| SDK | `openai>=1.40` (optional extra `openai`) | Current images and edits endpoints | Not yet verified |
| Cost and limits | Not stated in the Prompt | Per-image cost, rate limits | Not yet verified |

### 13.2 Models for story, vision, and utilities

#### qwen3 14B via Ollama (story engine)

**Ollama API (verified Sprint 1, 2026-11-02, Ollama 0.18.2):**
- Structured output: `POST /api/chat` with `"format": <JSON schema>`, `"stream": false`, and `options.temperature` / `options.seed`. The reply is JSON text in `message.content`; token counts are `prompt_eval_count` and `eval_count`.
- `"think": false` (top-level field, not inside `options`) disables qwen3 reasoning and is accepted by 0.18; the adapter also strips any `<think>` block defensively.
- Embeddings: `POST /api/embed` with `{"model", "input": [..]}` returns `{"embeddings": [[..]]}` (the older `/api/embeddings` takes a single `prompt` and is not used). Vectors are L2-normalized by the adapter.
- An unknown model returns HTTP 404 with `model "<tag>" not found`; the adapter maps it to `ModelMissingError`. Preflight uses `GET /api/tags`; a bare name matches `name:latest`.
- Integration test `it_ollama_tiny_model_returns_schema_valid_json` passed with `qwen3:0.6b`. `nomic-embed-text` was not installed on the verification machine, so its embedding path is covered by respx tests only.

| Attribute | Expected | Verify at implementation time | Status |
|---|---|---|---|
| Role | Story engine (bible, suggestions, writer, finalize) | Structured-output quality on the schemas; "thinking" mode behavior; suggestions under 10 s on a local 14B model (NFR-003) | Not yet verified |
| License | Apache-2.0 | License on the Ollama library tag | Not yet verified |
| Variants | 0.6B for CI | Smallest tag that passes integration tests | Not yet verified |
| Tag | `qwen3:14b` | Tag still exists and is the intended build | Not yet verified |

#### Qwen2.5-VL 7B via Ollama (vision)

| Attribute | Expected | Verify at implementation time | Status |
|---|---|---|---|
| Role | Describe, locate (bounding boxes), QA scoring, people detection, audience check | Tag `qwen2.5vl:7b`, grounding output format for `locate`, accuracy on cartoon art | Not yet verified |
| License | Apache-2.0 (check per size) | License for the 7B variant specifically | Not yet verified |

#### nomic-embed-text via Ollama (embeddings)

| Attribute | Expected | Verify at implementation time | Status |
|---|---|---|---|
| Role | Suggestion distinctness (cosine < 0.85) | Threshold calibration on real suggestion sets; vector dimensions | Not yet verified |
| License | Apache-2.0 | License on the Ollama library tag | Not yet verified |

### 13.3 Post-processing models

#### RapidOCR (ONNX)

| Attribute | Expected | Verify at implementation time | Status |
|---|---|---|---|
| Role | Detect text drawn in panel images (NFR-005) | Detection recall on stylized "fake text" glyphs; false-positive rate on signs and patterns | Not yet verified |
| License | Apache-2.0 (package); check bundled model licenses | Licenses of the ONNX detection and recognition models | Not yet verified |
| Runtime | CPU; optional extra `ocr` (`rapidocr-onnxruntime>=1.3`) | Package and model availability on Python 3.12 and 3.13, arm64 | Not yet verified |

#### Real-ESRGAN via ComfyUI (print upscale)

| Attribute | Expected | Verify at implementation time | Status |
|---|---|---|---|
| Role | Optional upscale for print PDF when source art is below 300 dpi effective (NFR-010) | Which Real-ESRGAN weights (general vs anime), quality on cartoon art, node names | Not yet verified |
| License | BSD-3-Clause | License of code and of the specific weights file | Not yet verified |
| Fallback | Lanczos resize with a warning if the workflow is unavailable | Visual comparison | Not yet verified |

### 13.4 Fonts (bundled)

| Font | Use | Expected license | Status |
|---|---|---|---|
| Comic Neue | Dialogue | OFL-1.1 | Not yet verified |
| Bangers | SFX, shouts, covers | OFL-1.1 | Not yet verified |
| Atkinson Hyperlegible | Kids captions and reading styles | OFL-1.1 | Not yet verified |
| Inter | UI | OFL-1.1 | Not yet verified |

Verify each font's license file and reserved font name clauses before bundling; record in `THIRD_PARTY_LICENSES.md`.

### 13.5 Verification checklist per backend

1. Read the current documentation and model card; record version, date, and URL in this section.
2. Confirm license text and any commercial-use or output restrictions; update the table and `THIRD_PARTY_LICENSES.md`.
3. Measure VRAM, time per panel, and quality on the fixture duck story; record numbers.
4. Fill `ImageCapabilities` from observed behavior and add contract tests.
5. Pin revisions and SHA-256 checksums for downloads; pin ComfyUI custom nodes by commit.
6. Update status to "verified on YYYY-MM-DD" with the evidence reference.

---

## 14. Open questions

These are not decided. Each is resolved by a Spec Change Protocol PR that updates this document.

| # | Question | Current default in this document | Decide by |
|---|---|---|---|
| 1 | What does `{version}` in `project.db.bak-{version}` mean: the pre-migration `schema_version` or the app release version? | Pre-migration `schema_version` (section 4.3) | Sprint 0 (S0-T06) |
| 2 | Is exit code 1 documented as "unexpected internal error"? The Prompt's table starts at 0 then 2. | Reserved for `internal_error`, not in the public table (section 7.1) | Sprint 0 |
| 3 | Arc template id `hero's-journey-lite` contains an apostrophe; should the id be normalized to `heros-journey-lite` for CLI and URLs? | Resolved in Sprint 1: normalized to `heros-journey-lite` (no apostrophe) in code, schemas, CLI, and URLs | Sprint 1 |
| 4 | Are the four added schemas (`style`, `beat`, `continuity`, `lettering`) published under `schemas/` as proposed? | Yes (section 5.10); resolved in Sprint 1, all ten are exported by `scripts/export-schemas.py` | Sprint 1 |
| 5 | Enums for `shot`, `angle`, `position`, `facing` in the Panel Spec | Values listed in section 5.3; resolved in Sprint 1 as `comic_smith.models` enums (`Shot`, `Angle`, `Position`, `Facing`) | Sprint 1 (S1-T02) |
| 6 | Internal layout ids for cover, title, dedication, cast, and back pages (`cover-full`, `title-center`, `dedication-center`, `cast-grid`, `back-simple`) | As listed in section 5.9 | Sprint 4 |
| 7 | Health endpoints at both `/healthz` and `/v1/healthz` (ADR-020) versus only one | Both | Sprint 7 (S7-T01) |
| 8 | Embedding similarity threshold 0.85 is from the PRD; does it hold for `nomic-embed-text` on short beat strings? | 0.85, one regenerate | Sprint 1 (S1-T05) |
| 9 | How many reference images can Qwen-Image-Edit take in the shipped ComfyUI workflow, and how does that change the sheet-reference strategy (views vs expressions)? | Unknown; reference selection picks the best view for the panel's shot and angle | Sprint 2 (S2-T05) |
| 10 | Lettering placement quality when `VisionProvider.locate` fails or is inaccurate for non-humanoid characters such as a duck or a sponge | Fall back to the character box from Panel Spec position and a default tail target | Sprint 3 (S3-T06) |
| 11 | Should QA scores (1 to 5) come from one vision call per character or one per panel? Affects cost and cache keys | One call per panel, per-character scores in one JSON | Sprint 3 (S3-T04) |
| 12 | Single-replica limit in Kubernetes: is a Postgres-backed queue needed for larger classrooms? | No; deferred (ADR-011, ADR-021) | After 1.1.0 feedback |
| 13 | CMYK and PDF/X-1a for print-on-demand | Out of scope for v1; RGB print PDF with bleed | Post v1 |
| 14 | Multi-language lettering: geometry is normalized so translation is feasible, but font coverage and UX are undefined | Out of scope for v1; `book.language` is metadata only | Post v1 |
| 15 | Manga right-to-left reading order: needs template and reader support | Out of scope for v1 | Post v1 |
| 16 | Redo semantics across workspaces in classroom mode when two users edit one shared project | Undo and redo are scoped per workspace actor; conflicts not specified | Sprint 7 (S7-T02) |
| 17 | Where does the model cache for `models pull` live when running outside Docker (default `./models` is a placeholder)? | Under `COMIC_SMITH_DATA_DIR/models` | Sprint 2 |
| 18 | Exact Pi extension package names (`@earendil-works/pi-agent-core`, `@sinclair/typebox`) | Verify current names and versions | Sprint 8 |

