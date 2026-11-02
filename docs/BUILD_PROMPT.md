# MR-COMIC-SMITH: Master Build Prompt
## Local-first comic studio: turn a narrative or a reference photo into an evolving comic strip, co-plotted with AI, stitched into pages, and bound into a book you can export as image, PDF, or web page

---

## Project Identity

**Name:** `mr-comic-smith`
**Family:** The "smith" toolset from SnackOnAI (siblings: `mr-pixel-smith` images, `mr-reel-smith` reels, `mr-motion-smith` motion, `mr-audio-smith` narration)
**GitHub repo:** `mohnishbasha/mr-comic-smith` (standalone repo; mirrored as `snackonai/mr-comic-smith/` via git subtree for the SnackOnAI tutorial series)
**Primary domain:** `getcomicsmith.com` (preferred) with `mrcomicsmith.com` as fallback
**Python package (PyPI):** `mr-comic-smith` (import name `comic_smith`, console script `mr-comic-smith`)
**npm scope:** `@mr-comic-smith` (for `@mr-comic-smith/reader` and `@mr-comic-smith/pi-extension`)
**Container image:** `ghcr.io/serverless-ventures/mr-comic-smith` (server + Studio + MCP; CPU and CUDA variants)
**Tagline:** *Every story deserves panels.*
**Short description (GitHub About field):** Turn a story idea or a photo into a growing comic strip, with AI plot suggestions at every step, then stitch it into pages and a book you can export as PNG, PDF, or a web page.
**Repository visibility:** Public, MIT licensed
**Distribution model:** Open-source, MIT (consistent with the rest of the smith family). Free forever for self-hosting.
**License:** MIT © 2026 Serverless Ventures LLC
**Long description (README opening):** mr-comic-smith is a local-first comic studio. Start from a sentence of narrative or a photo of anything (a duck, a dog, your kid's drawing), and it builds a consistent cast, writes the next strip with you, suggests where the plot could go next, and keeps going until the story lands. Finished strips stitch into comic pages, pages bind into a book, and the book exports as print-ready PDF, high-resolution images, or a self-contained web flipbook.

**Why mr-comic-smith:** A smith forges one medium with care and repetition. Pixel smith forges images, reel smith forges short videos, motion smith forges animation, audio smith forges narration. Comic smith forges sequential art: it heats a raw idea in the story engine, hammers it into panels, tempers it with consistency checks, and polishes it into pages. The family name also lets the two newest smiths cooperate: a comic exported as a web page is a valid input for mr-audio-smith, so a finished book can be read aloud.

**Flagship use case (drives every design decision):** A parent photographs a rubber duck on the bathtub edge and types "a brave little duck who is afraid of water." mr-comic-smith turns the photo into an original cartoon duck character sheet, writes a first four-panel strip, and offers three choices for what happens next. Parent and child pick, tweak, or write their own direction, strip after strip, until the duck learns to swim. The finished story is stitched into pages, given a cover, exported as a PDF to print, and shared as a web page grandparents can open on a phone.

**Second use case:** A newsletter writer turns a one-paragraph narrative ("a GPU that refuses to share memory") into a recurring four-panel comic for each issue, keeping the same cast across issues and collecting them into a yearly book.

---

## EXECUTION ORDER: THIS IS MANDATORY

The first action you take when executing this prompt is to generate the five product specification documents listed in Step 1 below. No GitHub setup, no scaffolding, no code of any kind is written before those documents exist on disk and are committed.

1. **Step 1:** Generate `docs/PRD.md`, `docs/ARCHITECTURE.md`, `docs/DESIGN.md`, `docs/SPRINT_PLAN.md`, `docs/TEST_PLAN.md`. Commit them on `main` as the first commit: `docs: add product specification documents`.
2. **Step 2:** Create and configure the GitHub repository (branches, protection, labels, milestones, project board, templates).
3. **Step 3:** Create every GitHub issue for every sprint task defined in `docs/SPRINT_PLAN.md`.
4. **Step 4 onward:** Execute sprints in order, Sprint 0 through Sprint 9, following the Sprint Start Protocol, Spec Change Protocol, Test Scenario Generation Protocol, and Sprint End Protocol. Every sprint gate is a hard stop.

If you are about to write code and Step 1 is not complete, stop. Complete Step 1 first.

**Spec documents supersede this prompt.** Once `docs/PRD.md` exists it is the source of truth for product behavior. Once `docs/ARCHITECTURE.md` exists it is the source of truth for structure, data model, and contracts. Once `docs/DESIGN.md` exists it is the source of truth for the Studio and reader UI. If this prompt and a spec doc disagree after Step 1, the spec doc wins, and any change to a spec doc follows the Spec Change Protocol.

---

## Step 1: Product Specification Documents

Generate all five documents in full. Each must be complete enough that an engineer who has never read this prompt can build from it. Use the content below as the minimum; expand where detail is missing, never shrink.

### 1.1 `docs/PRD.md`

#### Required sections

1. Overview (problem, solution, flagship use case)
2. Personas
3. Core loop (the co-plotting loop, described step by step)
4. User stories (US-001 onward)
5. Functional requirements (FR-001 onward) with acceptance criteria for every FR
6. Non-functional requirements (NFR-001 onward)
7. Success metrics
8. Constraints and assumptions
9. Out of scope for v1 (mirrors the "Out of Scope" section of this prompt)
10. Glossary

#### Problem statement

Image models can draw a single good picture, but a comic is not a single picture. A comic needs the same character to look the same in every panel, a story that moves forward with setup and payoff, dialogue that is legible, panels arranged in a reading order, and pages that print correctly. Today a person who wants a comic of "my duck" stitches this together by hand: prompting an image model panel by panel, fighting character drift, pasting speech bubbles in a design tool, and losing the thread of the story along the way. Image models also render text badly, so every bubble drawn by the model comes out garbled. Writing the story is a separate struggle: people often know how a story starts but not where it should go next.

#### Solution statement

mr-comic-smith separates the comic into the parts each tool is good at. A language model acts as a co-writer that keeps a story bible, writes each strip as structured panel specs, and proposes the next plot beat. An image model draws panels without any text, conditioned on an approved character sheet so the cast stays consistent. A deterministic lettering engine renders speech bubbles, captions, and sound effects as vector text. A layout engine stitches strips into pages and pages into a book. Everything is stored locally as a project you can reopen, branch, and export.

#### Personas

| ID | Persona | Goal | Technical level |
|---|---|---|---|
| P-1 | **Parent storyteller** (flagship) | Make a comic book with their child from a photo and a story idea | Comfortable installing a tool, prefers a visual UI |
| P-2 | **Young co-creator** (child, with parent) | Pick what happens next, see the duck do it | Non-technical, cannot read long text; needs big buttons and pictures |
| P-3 | **Newsletter or blog writer** | Recurring comic strips with a stable cast, collected into a book | CLI and UI |
| P-4 | **Agent operator** | Ask Claude Code, Pi, Goose, or OpenCode to "make a 4-panel strip about X" and get files back | Uses agent harnesses daily |
| P-5 | **Educator** | Students turn a lesson or a field-trip photo into a short comic | Shared machine or school server |
| P-6 | **Platform team** | Run the studio as a shared service with GPU rendering | Kubernetes, GPUs |

#### Core loop (the product)

```
 ┌──────────────┐   ┌─────────────────┐   ┌──────────────────┐
 │ 1. SEED      │──>│ 2. CAST + STYLE │──>│ 3. STORY BIBLE   │
 │ narrative    │   │ reference photo │   │ premise, tone,   │
 │ and/or photo │   │ -> character    │   │ audience, arc    │
 └──────────────┘   │    sheet        │   │ target length    │
                    └─────────────────┘   └────────┬─────────┘
                                                   v
        ┌──────────────────────────────────────────────────────────┐
        │ 4. STRIP LOOP (repeat until finalized)                   │
        │   a. Model suggests 3 next-plot options (+ "end here"    │
        │      when the arc is ready to resolve)                   │
        │   b. User picks one, edits it, or writes their own beat  │
        │   c. Model writes the strip as panel specs (3-4 panels)  │
        │   d. User edits script; panels render (no text in art)   │
        │   e. Consistency check; retake or edit any panel         │
        │   f. Lettering engine places bubbles; user adjusts       │
        │   g. Approve strip -> it joins the story timeline        │
        └────────────────────────┬─────────────────────────────────┘
                                 v
 ┌──────────────────┐   ┌─────────────────┐   ┌──────────────────────┐
 │ 5. FINALIZE      │──>│ 6. PAGES        │──>│ 7. BOOK + EXPORT     │
 │ continuity check │   │ stitch strips   │   │ cover, title page,   │
 │ title, lock      │   │ into page       │   │ page by page; export │
 │ story            │   │ layouts         │   │ PNG / PDF / web      │
 └──────────────────┘   └─────────────────┘   └──────────────────────┘
```

#### User stories (minimum set)

```
US-001  As a parent storyteller, I upload a photo of a duck and get an original cartoon
        character sheet of that duck (front, side, three-quarter, five expressions) that I
        can approve or regenerate, so the duck looks the same in every panel.
US-002  As a parent storyteller, I type one sentence of narrative and get a story bible
        (premise, tone, audience, setting, story arc with planned length) I can edit.
US-003  As a parent storyteller, I can start from narrative only, photo only, or both.
US-004  As a young co-creator, I see three illustrated choices for what happens next and
        tap one, so I help decide the story without reading paragraphs.
US-005  As a parent storyteller, I can edit a suggested plot beat or write my own instead.
US-006  As a parent storyteller, each chosen beat becomes a strip of 3 to 4 panels, with a
        script I can edit before any image is drawn.
US-007  As a parent storyteller, I regenerate any single panel, change its camera shot,
        or edit its description, without touching the other panels.
US-008  As any user, speech bubbles are crisp, correctly spelled, and readable, and I can
        drag, resize, and retype them.
US-009  As any user, the model tells me when the story has reached a good ending point
        and offers an "end the story here" choice, and I can keep going if I want.
US-010  As any user, when I finalize a story I get a continuity report (unresolved
        threads, character inconsistencies) and title suggestions before it locks.
US-011  As any user, finalized strips stitch automatically into comic pages using a
        layout I choose (classic three-tier, 2x2 grid, splash page, strip stack, vertical
        web scroll), and I can rearrange panels on a page.
US-012  As any user, I build a book page by page: cover, title page, story pages, and a
        back page, adding pages from one or many stories.
US-013  As any user, I export a page or the whole book as PNG or JPG images, a print-ready
        PDF, a CBZ archive, or a self-contained web page.
US-014  As any user, I export a single long strip image for social sharing.
US-015  As a newsletter writer, I reuse a saved cast and style across many projects so my
        recurring characters stay on-model.
US-016  As a newsletter writer, I run the whole loop from the CLI with an "auto" mode that
        picks plot suggestions for me, for a fast first draft.
US-017  As an agent operator, I call mr_comic_smith tools from my harness to create a
        strip from a prompt and receive file paths.
US-018  As any user, I choose an art style preset (picture book watercolor, bold cartoon,
        manga, newspaper ink, clay, pixel art) or define my own, applied to every panel.
US-019  As a parent storyteller, the app keeps content age-appropriate for the audience I
        set (all ages by default) in both story and images.
US-020  As any user, I branch a story at any strip to try a different direction, and
        switch between branches before finalizing.
US-021  As any user, I undo and redo every edit in the Studio.
US-022  As any user, `mr-comic-smith doctor` tells me what is missing (GPU, model weights,
        LLM, image backend, fonts) before anything fails.
US-023  As any user, the web page export can be narrated by mr-audio-smith without changes.
US-024  As an educator, I run the Studio on one machine and students open it in their
        browsers on the local network with a shared access code.
```

#### Functional requirements (minimum set, each with acceptance criteria)

```
FR-001  Project lifecycle
        Create, open, rename, duplicate, archive, delete projects. A project is a folder
        with project.db (SQLite) and assets/.
        AC: projects survive app restarts; duplicate copies assets by reference
            (content-addressed); delete moves to an OS trash or .trash/ folder.

FR-002  Seed input
        Accept narrative text (1 to 5,000 characters), zero to four reference images
        (PNG, JPG, WebP, HEIC; max 20 MB each), or both.
        AC: images are re-encoded, EXIF stripped (location removed), stored by SHA-256;
            HEIC converted; images over 4096 px on the long edge downscaled.

FR-003  Reference understanding
        A vision model describes each reference image: subject type, distinguishing
        features, colors, accessories, and suggests a character name.
        AC: description stored as structured JSON (subject, palette hex list, features,
            accessories); user can edit every field.

FR-004  Character sheet generation
        From a reference description (and the image when the backend supports image
        conditioning), generate an original character sheet in the chosen style:
        front, side, three-quarter views and expressions (neutral, happy, sad,
        surprised, angry, scared).
        AC: sheet rendered as separate images plus a composed sheet; user approves or
            regenerates per view; approved sheet becomes the canonical reference;
            character has a stable id and a "visual DNA" text block (one paragraph of
            invariant features) used in every panel prompt.

FR-005  Text-only characters
        Characters can be created from a description without a photo.
        AC: same sheet workflow as FR-004.

FR-006  Originality guard
        Block requests that name known copyrighted characters, franchises, or living
        artists' styles, and flag character sheets that resemble well-known characters.
        AC: denylist check on all user text and compiled prompts (configurable list,
            shipped with a starter set); vision-model similarity question on each
            approved sheet ("does this resemble a well-known copyrighted character?");
            on a match, the user is told which rule triggered and asked to change the
            design; no override flag in v1.

FR-007  People in reference photos
        When a reference image contains a person, require an attestation that the user
        has the right to use the likeness, and transform the person into a stylized
        cartoon character rather than a photorealistic depiction.
        AC: person detection via the vision model; attestation stored with the
            character; photoreal style presets disabled for characters derived from
            people; requests to depict public figures are declined by the story and
            prompt layers.

FR-008  Style presets
        Built-in presets: picture-book-watercolor, bold-cartoon, manga-ink,
        newspaper-strip, soft-3d-clay, pixel-art. Custom presets from text plus up to
        two style reference images the user owns.
        AC: preset = positive style tokens, negative tokens, palette hints, line weight,
            backend-specific parameters; preview grid of the cast in the style.

FR-009  Story bible
        LLM generates and the user edits: title (working), logline, premise, audience
        (all-ages default, kids-5-8, kids-9-12, teen, adult), tone, setting, cast list,
        themes, arc template, and target length in strips.
        AC: arc templates: three-act, hero's-journey-lite, problem-try-try-succeed (kids
            default), gag-a-day (no arc, standalone strips), mystery; target length
            between 1 and 40 strips; bible is versioned on every edit.

FR-010  Arc tracking
        Every strip is tagged with an arc stage and the bible tracks open threads.
        AC: arc stages per template; open threads list updated after each approved
            strip; arc progress (0 to 100 percent) visible in the UI.

FR-011  Plot suggestions
        After the bible and after every approved strip, generate exactly three next-beat
        options with different intents: continue (natural next step), twist (complication
        or surprise), and steer (move toward the planned resolution). When the arc is in
        its final stage or the target length is reached, add a fourth option: end here.
        AC: each option has a one-line beat, a two-sentence description, the arc stage it
            moves to, which characters appear, and a thumbnail sketch prompt; options are
            distinct (pairwise semantic similarity under 0.85 using embeddings, else
            regenerate once); thumbnails render with a fast low-step setting or are
            skipped when the backend is slow (configurable).

FR-012  Custom beats
        The user can edit any suggestion or write a free-text beat.
        AC: free-text beats are normalized into the same structure by the LLM before the
            strip is written; the user sees the normalized beat and can accept it.

FR-013  Strip writing
        Turn a chosen beat into a strip script: 1 to 6 panels (default 4 for strips,
        configurable), each panel as a Panel Spec (see ARCHITECTURE).
        AC: dialogue respects audience reading level (kids-5-8: max 10 words per balloon,
            max 2 balloons per panel); total words per strip limit per audience; every
            speaking character exists in the cast; output validates against the Panel
            Spec JSON Schema, with one corrective retry on validation failure.

FR-014  Script editing
        The user edits any panel field (shot, angle, setting, action, characters, poses,
        expressions, dialogue, caption, sound effects) before or after rendering.
        AC: edits that change visuals mark the panel stale; edits that change only text
            do not trigger re-rendering.

FR-015  Prompt compilation
        Compile a Panel Spec into a backend-specific image request: style tokens,
        character visual DNA, reference images, shot and composition, setting, action,
        continuity notes, and a "no text, no letters, no speech bubbles" constraint.
        AC: compiler is deterministic and unit-tested; reserves empty space for
            balloons by adding composition hints (for example "headroom at top third")
            when a panel has dialogue; compiled prompt viewable in the UI.

FR-016  Panel rendering
        Render panels through the selected image backend with reference conditioning.
        AC: per-panel seed recorded; takes stored; renders run in a job queue with
            progress events; cancel works; failures retried twice.

FR-017  Consistency check
        After each render, a vision model scores each character in the panel against its
        character sheet checklist (colors, features, accessories) from 1 to 5, and an OCR
        pass detects any text drawn in the image.
        AC: panels with any character under 4, or with detected text, are flagged and
            auto-retaken up to N times (default 2, new seed); the best take is selected;
            scores and reasons shown to the user.

FR-018  Panel editing
        Retake, pick among takes, change shot, inpaint a region with a text instruction
        (when the backend supports editing), crop and reframe.
        AC: inpaint limited to the selected mask; crop is non-destructive.

FR-019  Lettering engine
        Render balloons (speech, thought, shout, whisper), captions, and sound effects as
        vector SVG layers over the panel art.
        AC: automatic placement avoids character bounding boxes (from the vision model),
            follows reading order (top-left to bottom-right), points tails at the
            speaker's head box, auto-sizes font within min and max sizes, and never
            overflows the panel; user can drag, resize, retype, change balloon type;
            fonts are open-licensed and embedded in exports.

FR-020  Strip assembly and approval
        Compose panels into a strip with gutters and borders; approve the strip.
        AC: approval requires all panels rendered and lettered; approved strips are
            immutable until "unapprove"; approving triggers bible thread update and the
            next plot suggestions.

FR-021  Branching
        Create a branch from any approved strip; switch, rename, and delete branches.
        AC: branches share earlier strips; finalize applies to one branch.

FR-022  Finalize story
        Finalize a branch: run a continuity review (unresolved threads, characters who
        vanish, inconsistent props, tone breaks), suggest three titles and a one-line
        blurb, then lock the story.
        AC: the user can fix issues (jump to the strip) or finalize anyway; finalized
            stories are read-only unless explicitly reopened (reopen creates a new
            version).

FR-023  Page composer
        Stitch the strips of a finalized story into pages using layout templates:
        strip-stack (strips stacked vertically, 3 per page default), classic-three-tier,
        grid-2x2, grid-3x3, splash-plus-two, and vertical-scroll (web).
        AC: auto-paginate respecting strip boundaries by default (never split a strip
            across pages unless the user allows it); user can drag panels between slots,
            change page layout per page, add page-level captions; page sizes: US comic
            (6.625 x 10.25 in), US Letter, A4, square 8.5 x 8.5 in, and web; margins,
            gutters, bleed configurable.

FR-024  Book builder
        Build a book page by page: cover (title, subtitle, author, cover art generated
        from the story or picked from panels), title page, optional dedication page,
        story pages (from one or more finalized stories, as chapters), optional "about
        the characters" page from character sheets, back cover.
        AC: add, remove, reorder, and duplicate pages; page numbers; table of contents
            for multi-story books; book metadata (title, author, year, language).

FR-025  Exports
        Export a page, a story, or a book as: PNG, JPG, WebP (72, 150, 300 dpi); PDF
        (screen or print; print adds 0.125 in bleed and optional trim marks); CBZ; a
        single long strip image; a web page (static folder or single self-contained HTML
        file with a flipbook reader and a vertical scroll mode).
        AC: exports reproduce the Studio rendering exactly (same fonts, same balloon
            positions); PDF text in balloons is selectable and searchable; web export
            works offline from file://, is responsive, keyboard navigable, and includes
            alt text per panel from the panel action description; web export marks the
            reading text with data-narrate attributes for mr-audio-smith.

FR-026  Auto mode
        Generate a complete story draft without interaction: the model picks suggestions
        according to a policy (steer-heavy, balanced, twist-heavy) until the target length,
        then stops before finalize.
        AC: CLI `mr-comic-smith auto`; every auto pick is recorded and reversible.

FR-027  Cast and style library
        Save characters and styles to a user library and import them into any project.
        AC: imported characters keep sheets and visual DNA; version recorded.

FR-028  Content rating guard
        Story and image layers respect the audience setting.
        AC: system prompts include audience rules; a moderation pass on every generated
            beat, script, and compiled image prompt; image outputs checked by the vision
            model for audience suitability; blocked content explained in plain words.

FR-029  Studio UI
        A local web application served by `mr-comic-smith studio` implementing the core
        loop, page composer, book builder, and exports (see DESIGN).
        AC: works in current Chrome, Safari, Firefox, Edge; installable as a PWA;
            binds to 127.0.0.1 by default.

FR-030  CLI
        Every core action is available from the CLI (see ARCHITECTURE).
        AC: CLI and Studio operate on the same project files; CLI output supports --json.

FR-031  Doctor
        `mr-comic-smith doctor` checks Python, GPU and VRAM, image backend reachability
        and models, LLM and vision provider, fonts, Chromium for exports, disk space.
        AC: exit 0 when required checks pass; each failure has a fix hint.

FR-032  REST server and MCP server
        `serve` exposes the REST API; `mcp` exposes MCP tools (Appendix E).
        AC: long jobs report progress; bearer token for non-localhost binding.

FR-033  Undo and history
        Every mutating action is an event in an append-only project history.
        AC: undo and redo across script edits, lettering edits, take selection, layout
            changes; history survives restart.

FR-034  Classroom mode
        `studio --lan --access-code <code>` serves the Studio on the LAN with per-user
        workspaces inside one instance.
        AC: access code required; users see only their projects unless shared.
```

#### Non-functional requirements

```
NFR-001  Local-first: with default config (Ollama + ComfyUI), no text or image leaves the
         machine. Cloud backends are opt-in and shown with a visible "cloud" badge.
NFR-002  Zero telemetry.
NFR-003  Responsiveness: plot suggestions (text only) appear within 10 s on a local 14B
         model; a 4-panel strip renders in under 3 minutes on one 24 GB NVIDIA GPU with
         the default local backend, and under 90 s on the cloud backends.
NFR-004  Consistency: across the flagship test story (8 strips), at least 90 percent of
         character appearances score 4 or higher on the consistency check after retakes.
NFR-005  Text quality: 0 percent of exported balloons contain model-rendered text; 100
         percent of lettering is vector text from the lettering engine.
NFR-006  Reliability: a crash or kill never corrupts a project (SQLite WAL, atomic asset
         writes); in-flight renders resume or cancel cleanly.
NFR-007  Accessibility: Studio and web reader meet WCAG 2.2 AA; child mode uses 64 px
         minimum targets and picture-first choices; reader has alt text for every panel.
NFR-008  Portability: macOS Apple Silicon (cloud or MPS-capable backends), Linux x86_64
         and arm64 (including NVIDIA Grace systems), Windows 11 via WSL2 or native
         Python with cloud backends.
NFR-009  Export fidelity: exported page images and PDF are pixel-identical to Studio
         preview at the same resolution (same renderer).
NFR-010  Print quality: print PDF at 300 dpi effective resolution for panel art; upscale
         step applied automatically when source art is below target.
NFR-011  Licensing: every dependency, model weight, and font is recorded with its license;
         backends whose weights are non-commercial require explicit opt-in and are
         labeled in exports' metadata.
NFR-012  Safety: originality guard, people attestation, and audience guard are enforced in
         core, not only in the UI.
```

#### Success metrics

- Flagship: a parent and child complete an 8-strip duck story, a 4-page book with cover, and a PDF export in under 60 minutes of wall time on the reference GPU.
- Plot co-writing: in usability tests, users pick a model suggestion (unedited or lightly edited) for at least 60 percent of beats.
- Consistency: NFR-004 met on three fixture stories.
- Export: 100 percent of exports open correctly in Preview, Acrobat, Chrome, and iOS Books (PDF), and Chrome, Safari, Firefox (web).

#### Glossary

| Term | Meaning |
|---|---|
| Seed | The starting narrative and/or reference images |
| Character sheet | Approved multi-view, multi-expression reference images plus visual DNA for one character |
| Visual DNA | One paragraph of invariant visual features used in every panel prompt |
| Story bible | The living document of premise, cast, tone, setting, arc, and open threads |
| Beat | One plot step; the unit chosen from suggestions |
| Strip | A row of 1 to 6 panels that tells one beat |
| Panel Spec | Structured description of one panel (shot, characters, action, dialogue) |
| Take | One rendering attempt of a panel |
| Lettering | Balloons, captions, sound effects rendered as vector text |
| Branch | An alternative sequence of strips from a shared point |
| Page | A layout of panels or strips at a physical or web size |
| Book | Ordered pages with cover, metadata, and chapters |

---

### 1.2 `docs/ARCHITECTURE.md`

#### Required sections

1. System overview and diagram
2. Decision log (ADR-001 onward)
3. Module map
4. Data model (SQLite schema) and asset store
5. Data formats: Story Bible, Panel Spec, Plot Suggestion, Character, Style, Layout, Book manifest
6. Pipelines: seed to cast, beat to strip, strip to page, book to export
7. Contracts: CLI, Python API, REST API, WebSocket events, MCP tools, ImageBackend, LLMProvider, VisionProvider
8. Job system
9. Caching model
10. Error model
11. Security and safety model
12. Deployment topologies

#### System overview (include this diagram)

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

#### Decision log (minimum ADRs)

```
ADR-001  Core in Python 3.12; UI in TypeScript + React.
         Why: image generation clients (ComfyUI API, diffusers, cloud SDKs), vision tooling,
         and PDF and image processing are strongest in Python; the interactive canvas needs
         a modern web UI.
ADR-002  Local web app (Studio) served by the CLI, installable as a PWA; no Tauri shell in v1.
         Why: same UI works on a laptop, a LAN GPU box, and Kubernetes; classroom mode is
         free; avoids bundling a Python sidecar inside a desktop shell.
         Consequence: Rust/Tauri coding standards replaced by Python + TypeScript standards.
ADR-003  Image models never draw text. All lettering is vector SVG from the lettering engine.
         Why: image models misspell; vector text is crisp, editable, translatable,
         searchable in PDF, and narratable.
ADR-004  Character consistency via an approved character sheet used as reference images on
         every panel, plus a visual DNA text block, plus a vision-model consistency check
         with automatic retakes.
         Why: no single technique is reliable; layered defenses are.
ADR-005  Pluggable ImageBackend with capability flags (reference images, max references,
         edit/inpaint, seed control, sizes). Default local backend is ComfyUI driven by
         bundled workflow templates; default cloud backend is Gemini image generation;
         OpenAI images as a second cloud option; mock for tests.
         Why: local-first with an escape hatch for users without a large GPU; model choice
         changes fast, workflows absorb that churn.
ADR-006  Default local workflow uses Qwen-Image-Edit (Apache-2.0) for reference-conditioned
         panels. FLUX.1 Kontext [dev] workflow is shipped but opt-in because its weights are
         under a non-commercial license. Verify both licenses and VRAM needs at
         implementation time.
ADR-007  The story engine writes structured JSON (Panel Specs, Plot Suggestions) validated
         against JSON Schemas, never free-form prose that is parsed later.
ADR-008  One renderer for preview and export: pages are SVG documents (panel art as
         images, lettering as text with embedded fonts) rendered by headless Chromium via
         Playwright for PNG and PDF. Studio preview uses the same SVG.
         Consequence: WYSIWYG fidelity (NFR-009) by construction.
ADR-009  SQLite (SQLAlchemy 2 + Alembic) per project plus a content-addressed asset store.
         Why: projects are portable folders; zip a folder to share it.
ADR-010  Append-only event log per project powers undo/redo, history, and auto-mode audit.
ADR-011  Job queue in SQLite with a single GPU worker and a pool of text workers; progress
         over WebSocket. Redis deferred.
ADR-012  LLM default Ollama (qwen3:14b class) for story; vision default Ollama with a
         Qwen2.5-VL class model; Anthropic and OpenAI-compatible optional for both.
ADR-013  Safety guards (originality, people attestation, audience) live in core services,
         so CLI, REST, MCP, and Studio inherit them.
ADR-014  Web export embeds data-narrate markup so mr-audio-smith can narrate books without
         an integration layer.
```

#### Module map

```
comic_smith/
  __init__.py            version via importlib.metadata
  api.py                 public Python API (thin facade over services)
  cli.py                 typer app
  config.py              pydantic-settings, env prefix COMIC_SMITH_
  doctor.py
  errors.py              ComicSmithError hierarchy
  events.py              event log, undo/redo
  db/                    models.py (SQLAlchemy), session.py, migrations/ (Alembic)
  assets/                store.py (content-addressed), images.py (ingest, EXIF strip, resize)
  story/
    bible.py             create/edit/version bible
    arc.py               arc templates, stage tracking, progress
    suggest.py           plot suggestions + distinctness check
    writer.py            beat -> strip script (Panel Specs)
    finalize.py          continuity review, titles, lock
    moderation.py        audience guard for text
    prompts/             versioned prompt templates (*.md)
    schemas/             panel_spec.json, suggestion.json, bible.json
  cast/
    reference.py         vision describe, person detection
    sheet.py             character sheet generation and approval
    dna.py               visual DNA text
    originality.py       denylist + resemblance check
    styles.py            style presets
  panels/
    compiler.py          Panel Spec -> ImageRequest
    render.py            job orchestration, takes
    qa.py                consistency scoring, OCR text detection
    edit.py              inpaint, crop
  letter/
    layout.py            balloon placement algorithm
    svg.py               balloon shapes, tails, captions, SFX
    fonts.py             font registry, embedding
  layout/
    templates.py         page and strip templates
    paginate.py          strips -> pages
    page.py              page SVG composition
  book/
    builder.py           book model, cover, title, chapters, TOC
  export/
    chromium.py          Playwright rendering
    images.py            PNG/JPG/WebP, long strip, upscale
    pdf.py               screen and print PDF, bleed, trim marks, metadata
    cbz.py
    web.py               static folder + single-file reader
  backends/
    image/  base.py, comfyui.py, gemini.py, openai_images.py, mock.py, registry.py
            workflows/ qwen-image-edit.json, flux-kontext-dev.json, sdxl-ipadapter.json
    llm/    base.py, ollama.py, anthropic.py, openai_compat.py, fake.py
    vision/ base.py, ollama_vl.py, anthropic.py, openai_compat.py, fake.py
  jobs/                  queue.py, worker.py, progress.py
  server/                app.py (FastAPI), routes/, ws.py, auth.py, static/ (built Studio)
  mcp_server/            server.py, tools.py
web/studio/              React + TypeScript + Vite Studio
reader/                  @mr-comic-smith/reader web component (used by web export)
integrations/            pi/, goose/, opencode/, claude-code/
```

#### Data model (SQLite)

```
project(id TEXT PK, name, created_at, updated_at, audience, style_id, schema_version)
bible(id PK, project_id FK, version INT, json TEXT, created_at)            -- versioned
character(id PK, project_id FK, slug, name, source ENUM(photo,text,library),
          reference_json, visual_dna, sheet_asset_ids JSON, approved BOOL,
          person_attested BOOL, library_ref NULL)
style(id PK, project_id FK NULL, name, preset_json, builtin BOOL)
branch(id PK, project_id FK, name, parent_branch_id NULL, fork_strip_id NULL, active BOOL)
strip(id PK, project_id FK, branch_id FK, idx INT, beat_json, arc_stage, status
      ENUM(scripted,rendering,rendered,lettered,approved), created_at)
panel(id PK, strip_id FK, idx INT, spec_json, selected_take_id NULL, stale BOOL,
      lettering_json, crop_json NULL)
take(id PK, panel_id FK, asset_id, seed, backend, model, prompt_json, qa_json, created_at)
suggestion_set(id PK, project_id FK, branch_id FK, after_strip_id NULL, json, chosen_idx NULL,
               custom_beat_json NULL, created_at)
story(id PK, project_id FK, branch_id FK, title, blurb, finalized_at, continuity_json,
      version INT)
page(id PK, project_id FK, book_id NULL, idx INT, kind ENUM(story,cover,title,dedication,
     cast,back,custom), layout_id, size, slots_json, captions_json)
book(id PK, project_id FK, title, subtitle, author, year, language, settings_json)
export(id PK, project_id FK, target ENUM(page,story,book), format, options_json,
       asset_ids JSON, created_at)
event(id INTEGER PK AUTOINCREMENT, project_id, ts, actor ENUM(user,auto,agent), type,
      payload_json, inverse_json)
job(id PK, project_id, kind, status, priority, payload_json, progress, error_json,
    created_at, started_at, finished_at)
```

Assets: `assets/{sha256[0:2]}/{sha256}.{ext}` with an `asset` table (id = sha256, mime, width, height, bytes, origin ENUM(upload, render, export, derived), created_at). Never overwrite; garbage-collect unreferenced assets with `mr-comic-smith gc`.

#### Data formats

**Story Bible** (JSON, schema `comic-smith/bible@1`)

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

**Plot Suggestion set** (schema `comic-smith/suggestions@1`)

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

**Panel Spec** (schema `comic-smith/panel@1`)

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

**Character** (schema `comic-smith/character@1`): id, slug, name, source, reference description (subject, palette hex, features, accessories), visual DNA paragraph, sheet asset ids by view and expression, approval timestamp, attestation (for people), originality check result.

**Layout template** (schema `comic-smith/layout@1`): id, page size key, margins, gutter, bleed, slots (each slot: x, y, w, h in page units, accepts panel or strip, optional border style), reading order.

**Book manifest** (schema `comic-smith/book@1`): metadata, ordered page ids with kinds, chapters (story ids, start page), export defaults.

Publish all JSON Schemas under `schemas/`.

#### Pipelines

**Seed to cast:** ingest images (FR-002) -> vision describe (FR-003) -> person check (FR-007) -> originality check on description (FR-006) -> generate sheet views with style (FR-004) -> user approves -> originality resemblance check on approved sheet -> visual DNA finalized.

**Beat to strip:** suggestions (FR-011) -> chosen or custom beat (FR-012) -> writer (FR-013) -> moderation -> user edits -> compile each panel (FR-015) -> render jobs (FR-016) -> QA and retakes (FR-017) -> character boxes from vision model -> auto-lettering (FR-019) -> user adjusts -> approve (FR-020) -> bible update (open threads, arc stage) -> next suggestions.

**Strip to page:** finalize (FR-022) -> paginate with chosen template (FR-023) -> page SVG -> preview.

**Book to export:** book builder (FR-024) -> export job: for each page, render SVG via Chromium to PNG at target dpi, or print the whole book HTML to PDF -> post-process (bleed, trim marks, metadata) -> package (CBZ zip, web folder, single-file HTML with base64 assets).

#### Contracts

**CLI** (document every flag, default, and exit code)

```
mr-comic-smith new <name> [--narrative "..."] [--image duck.jpg ...] [--style picture-book-watercolor]
                   [--audience kids-5-8] [--strips 8] [--arc problem-try-try-succeed]
mr-comic-smith cast add <project> --image <file> [--name] [--attest-person]
mr-comic-smith cast sheet <project> <character> [--regenerate views]
mr-comic-smith bible <project> [--edit]
mr-comic-smith suggest <project> [--branch main] [--json]
mr-comic-smith strip <project> --pick 1|2|3|end | --beat "free text" [--panels 4]
mr-comic-smith render <project> [--strip N] [--panel M] [--takes 2] [--backend comfyui]
mr-comic-smith letter <project> --strip N [--auto]
mr-comic-smith approve <project> --strip N
mr-comic-smith branch <project> create|switch|list|delete ...
mr-comic-smith auto <project> [--policy balanced|steer|twist] [--until-target]
mr-comic-smith finalize <project> [--branch] [--title "..."]
mr-comic-smith pages <project> [--layout strip-stack] [--size us-comic]
mr-comic-smith book <project> add-page|move|remove|cover|show ...
mr-comic-smith export <project> --target page|story|book --format png|jpg|webp|pdf|cbz|web|strip
                      [--dpi 300] [--print] [--single-file] [--out ./exports]
mr-comic-smith library add|list|import ...
mr-comic-smith studio [--port 7351] [--lan --access-code CODE]
mr-comic-smith serve [--host 127.0.0.1] [--port 7350]
mr-comic-smith mcp [--transport stdio|http]
mr-comic-smith doctor [--json]
mr-comic-smith gc <project>
Exit codes: 0 ok, 2 usage, 3 preflight failed, 4 safety blocked, 5 generation invalid,
            6 render failed, 7 export failed, 8 project locked or not found
```

**ImageBackend**

```python
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

class ImageBackend(Protocol):
    id: str
    def capabilities(self) -> ImageCapabilities: ...
    def preflight(self) -> list[PreflightIssue]: ...
    def generate(self, req: ImageRequest, progress: ProgressFn) -> GeneratedImage: ...
```

**LLMProvider** and **VisionProvider**

```python
class LLMProvider(Protocol):
    id: str
    def preflight(self) -> list[PreflightIssue]: ...
    def complete_json(self, system: str, user: str, schema: dict[str, Any], *,
                      temperature: float, seed: int | None) -> dict[str, Any]: ...

class VisionProvider(Protocol):
    id: str
    def preflight(self) -> list[PreflightIssue]: ...
    def describe(self, image: AssetRef, instruction: str, schema: dict[str, Any]) -> dict[str, Any]: ...
    def locate(self, image: AssetRef, targets: list[str]) -> list[BoundingBox]: ...
```

**REST API** (prefix `/v1`; full list in ARCHITECTURE)

```
GET/POST        /v1/projects                       list, create
GET/PATCH/DEL   /v1/projects/{p}
POST            /v1/projects/{p}/characters        add from image or text
POST            /v1/projects/{p}/characters/{c}/sheet      generate or regenerate views
POST            /v1/projects/{p}/characters/{c}/approve
GET/PUT         /v1/projects/{p}/bible
POST            /v1/projects/{p}/suggestions       -> suggestion set
POST            /v1/projects/{p}/strips            body: {suggestion_set_id, pick | custom_beat}
PATCH           /v1/projects/{p}/panels/{id}       edit spec or lettering
POST            /v1/projects/{p}/panels/{id}/render | /retake | /edit
POST            /v1/projects/{p}/strips/{id}/approve
POST            /v1/projects/{p}/branches | /finalize | /pages | /book/pages
POST            /v1/projects/{p}/exports           -> job id
GET             /v1/jobs/{id}
GET             /v1/assets/{sha}                   immutable, long cache
POST            /v1/projects/{p}/undo | /redo
GET             /healthz | /readyz
WS              /v1/events?project={p}             job progress, entity changes
```

**WebSocket events:** `job.progress {job_id, kind, stage, pct}`, `job.done`, `job.failed`, `entity.changed {type, id}`, `qa.flagged {panel_id, reasons}`, `suggestions.ready {set_id}`.

**MCP tools:** Appendix E.

#### Job system

SQLite `job` table; workers claim jobs with `UPDATE ... WHERE status='queued' ORDER BY priority, created_at LIMIT 1 RETURNING`. One GPU worker (image backend local), N text workers (LLM, vision), cloud image jobs concurrency 2 by default. Priorities: interactive panel render (0) > suggestion thumbnails (5) > exports (7) > auto mode (9). Cancellation via status flag polled between steps and ComfyUI interrupt.

#### Caching model

- Compiled prompts and generated images are keyed by `H(compiled_request, backend, model, seed)`; identical requests reuse the asset.
- LLM outputs keyed by `H(prompt_template_version, inputs, provider, model, seed)` when temperature is 0 (auto mode and tests); interactive suggestions use temperature 0.8 and are not cached.
- Vision QA results keyed by `H(asset_sha, character_sheet_version, qa_prompt_version)`.

#### Error model

Typed `ComicSmithError` subclasses with `code`, `stage`, `message`, `hint`, `retryable`. REST maps to RFC 9457 problem+json. Studio shows `message` and `hint` in plain words; the technical detail appears behind a "details" toggle.

#### Security and safety model (summary; full detail in Security Guidelines)

Localhost binding by default; access code for LAN mode; bearer token for server; EXIF stripping; upload type and size checks; SVG sanitization (lettering SVG is generated, never user-uploaded); Chromium export runs offline with network disabled and JavaScript limited to the bundled reader; safety guards in core (originality, people attestation, audience); secrets only from environment or OS keyring.

#### Deployment topologies

1. Laptop with cloud image backend (no GPU needed).
2. Workstation or GPU box with ComfyUI + Ollama (fully local).
3. LAN classroom: one GPU box running `studio --lan`.
4. Kubernetes: Helm chart (Appendix G), suitable for a 2-node GPU cluster.

---
### 1.3 `docs/DESIGN.md`

mr-comic-smith has three visual surfaces: the **Studio** (where comics are made), **Child mode** (a simplified Studio view for young co-creators), and the **Reader** (the web export). DESIGN.md must specify all three using the Design System section of this prompt as the minimum, plus the following.

#### Required sections

1. Design principles
2. Information architecture and navigation
3. Wireframes for every screen (ASCII), with states
4. Component inventory (props, states, keyboard behavior)
5. Lettering visual spec (balloon shapes, tails, fonts, sizes)
6. Page layout templates (visual diagrams)
7. Motion and feedback
8. Copy guidelines and microcopy
9. Child mode rules
10. Reader spec
11. Anti-patterns

#### Principles

1. **The comic is the interface.** Panels are always the largest thing on screen; controls sit around them, never over them, except the lettering handles while editing.
2. **Always a next step.** At every moment the Studio shows one primary action (approve strip, pick a plot, render, export).
3. **Choices are pictures.** Plot suggestions show a thumbnail and one line before any paragraph.
4. **Undo everything.** No destructive action without undo or a confirmation.
5. **Calm while waiting.** Rendering shows progress per panel with a sketch placeholder, never a blank spinner.

#### Information architecture

```
Home (projects, library)
 └─ Project
     ├─ Story      (bible, arc progress, open threads, branches)
     ├─ Cast       (characters, sheets, styles)
     ├─ Strips     (timeline + strip editor + plot choices)   <- default view
     ├─ Pages      (page composer)
     ├─ Book       (book builder)
     └─ Export
```

#### Wireframes (include, then expand per state)

**Strips view (the core screen)**

```
┌───────────────────────────────────────────────────────────────────────────────────────┐
│ ◂ Projects   Puddle, the Duck Who Would Not Swim     Story Cast [Strips] Pages Book ⇪ │
├───────────────┬──────────────────────────────────────────────────┬────────────────────┤
│ STORY         │  Strip 4 of ~8            ● rendering 3/4        │ WHAT HAPPENS NEXT? │
│ Arc  ▓▓▓▓░░░  │ ┌──────────┬──────────┬──────────┬──────────┐    │ ┌────────────────┐ │
│ 42% try-1     │ │ panel 1  │ panel 2  │ panel 3  │ (sketch) │    │ │ [thumb]        │ │
│               │ │ [art]    │ [art]    │ [art]    │ drawing… │    │ │ Continue       │ │
│ Open threads  │ │ "Jump    │          │  SPLISH  │          │    │ │ Puddle builds  │ │
│ • Sub near    │ │  in!"    │          │          │          │    │ │ a raft         │ │
│   the drain   │ └──────────┴──────────┴──────────┴──────────┘    │ └────────────────┘ │
│               │  Panel 2 ▸ Shot [medium ▾] Angle [eye ▾]         │ ┌────────────────┐ │
│ CAST          │  Action: Sub waves Puddle into the water…        │ │ Twist          │ │
│ (o) Puddle ✓  │  Dialogue: Sub ▸ "Jump in! It's warm!" [speech]  │ └────────────────┘ │
│ (o) Sub    ✓  │  [Retake] [Takes 2/3 ◂ ▸] [Edit region] [Crop]   │ ┌────────────────┐ │
│               │  QA: Puddle 5/5, Sub 4/5 ✓  No text detected ✓    │ │ Steer          │ │
│ BRANCH main ▾ │                                                  │ └────────────────┘ │
│               │                     [ Approve strip ]            │ ✎ Write my own…    │
├───────────────┴──────────────────────────────────────────────────┴────────────────────┤
│ TIMELINE  [1 ✓][2 ✓][3 ✓][4 ●][ + ]                         ↶ Undo  ↷ Redo  ⚙        │
└───────────────────────────────────────────────────────────────────────────────────────┘
```

**Cast view: character sheet approval**

```
┌───────────────────────────────────────────────────────────────────┐
│ Reference           Sheet (picture-book-watercolor)               │
│ ┌─────────┐   ┌──────┬──────┬──────┐  ┌───┬───┬───┬───┬───┬───┐  │
│ │ [photo] │   │front │ side │ 3/4  │  │ :)│ :(│ :O│ >:│ :|│ D:│  │
│ └─────────┘   └──────┴──────┴──────┘  └───┴───┴───┴───┴───┴───┘  │
│ Name [Puddle]  Visual DNA: small yellow duck, orange flat beak,   │
│ Palette ■■■■   round body, red bandana, one feather tuft…  [edit] │
│ Originality ✓  [Regenerate view ▾]        [ Approve character ]   │
└───────────────────────────────────────────────────────────────────┘
```

**Pages view**

```
┌──────────────┬──────────────────────────────────────────┬─────────────────┐
│ PAGES        │            page 2 (US comic)             │ LAYOUT          │
│ [1][2●][3]   │  ┌────────────────────────────────────┐  │ ( ) strip-stack │
│ [+ page]     │  │ strip 3: p1 | p2 | p3 | p4         │  │ (•) three-tier  │
│              │  ├────────────────────────────────────┤  │ ( ) grid-2x2    │
│ UNPLACED     │  │ strip 4: p1 | p2 | p3 | p4         │  │ ( ) splash+2    │
│ strip 7      │  ├────────────────────────────────────┤  │ Gutter [12px]   │
│ strip 8      │  │ strip 5: p1 | p2 | p3 | p4         │  │ Bleed  [on]     │
│              │  └────────────────────────────────────┘  │ [Auto-paginate] │
└──────────────┴──────────────────────────────────────────┴─────────────────┘
```

**Book view:** horizontal spread view (two pages side by side like an open book), page strip at bottom, inspector at right with page kind, title fields, and cover art picker.

**Export dialog:** target (page, story, book), format cards (PNG, PDF, Web, CBZ, Long strip), options per format (dpi, print bleed, trim marks, single file), estimated size, Export button, progress, then "Open folder" and "Copy path".

#### Child mode

Toggle in the header ("Kid mode"). Shows only: the current strip large, three big picture choices (each 240 px thumbnail plus a 3 to 5 word label read aloud with the browser's speech synthesis on tap), a big "Make it!" button, and a "Read our comic" button. No settings, no text fields, no delete. Parent exits with a long-press (2 s) on the lock icon.

#### Lettering visual spec

- Speech: rounded ellipse or rounded rectangle, 2 px stroke, white fill, tail as a tapered curve to the speaker head box.
- Thought: cloud outline with three trailing circles.
- Shout: spiky burst, bold weight, slightly larger size.
- Whisper: dashed outline, lighter text color.
- Caption: rectangle, pale yellow fill (`--cs-caption`), top-left by default.
- SFX: display font, colored fill with dark outline, slight rotation (-8 to 8 deg), placed near its source.
- Text is set in uppercase for bold-cartoon and newspaper styles (configurable per style); mixed case for picture-book styles.
- Minimum font size: 9 pt at print size, 14 px on web; line height 1.15; padding 0.6 em.

#### Page templates (diagrams required in DESIGN.md)

strip-stack, classic-three-tier, grid-2x2, grid-3x3, splash-plus-two, vertical-scroll. Each diagram shows slot rectangles and reading order numbers.

#### Reader spec (web export)

Two modes: flipbook (one page or spread, arrow keys, swipe, page counter) and scroll (vertical, panels stacked, ideal on phones). Header shows title and mode toggle; no external requests; works from `file://`; `prefers-reduced-motion` disables page-turn animation; each panel has alt text; balloons are real text in the DOM (selectable, translatable, narratable).

#### Motion

- Panel render: sketch placeholder with a slow left-to-right "ink sweep" shimmer; replaced by art with a 200 ms fade.
- Plot choice selection: card lifts 4 px; others fade to 60 percent.
- Approve strip: strip slides into the timeline (250 ms).
- All motion disabled under `prefers-reduced-motion`.

#### Microcopy examples

- Empty project: "Start with a story idea, a photo, or both."
- Rendering: "Drawing panel 3 of 4..."
- QA retake: "Sub looked a little different, redrawing."
- End-here suggestion: "This feels like a good ending. End the story here?"
- Originality block: "That character looks a lot like a famous cartoon. Let's give Puddle a look that is all yours."

---

### 1.4 `docs/SPRINT_PLAN.md`

Copy every sprint and every task from the sprint sections of this prompt (Sprints 0 to 6) and Appendices E to G (Sprints 7 to 9) into SPRINT_PLAN.md with task IDs, titles, labels, descriptions, acceptance criteria, estimates (S = half day, M = 1 day, L = 2 days, XL = 3+ days; split XL before starting), and dependencies. Include the sprint overview table from Appendix H and this dependency graph:

```
S0 Scaffold ─> S1 Story engine ─> S2 Cast, style, backends ─> S3 Panels, lettering, strips (core)
                                                                   │
                                                  S4 Pages and book <┘
                                                         │
                                                  S5 Export ─> S6 Release v1.0.0
                                                                   │
                                        S7 Server + MCP ─> S8 Harnesses ─> S9 Packaging
```

---

### 1.5 `docs/TEST_PLAN.md`

#### Required sections

1. Strategy and pyramid
2. Coverage targets (mirror `.coverage-thresholds.toml`)
3. Naming convention
4. Fixtures and golden files
5. Scenario tables per feature area (status: ✅ Automated, ⚠️ Deferred, ❌ Skipped with reason and manual step)
6. Model evaluation protocol (story quality, consistency, lettering)
7. Visual regression strategy
8. Smoke checklist for staging
9. Regression policy

#### Strategy

- **Unit** (pytest, vitest): prompt compiler, schema validation, arc tracking, suggestion distinctness, paginate, layout math, balloon placement geometry, SVG generation, safety denylist, event log and undo, cache keys, export option resolution.
- **Integration** (pytest -m integration): SQLite migrations, job queue with real workers, Ollama with a tiny model, ComfyUI against a CPU-friendly tiny workflow (fixture workflow using a small SD model or a stub ComfyUI server), Chromium exports (PNG and PDF), PDF inspection with pypdf (page count, page size, embedded fonts, selectable text).
- **Contract tests**: each ImageBackend and LLMProvider adapter against recorded HTTP fixtures (respx); cloud adapters additionally against live APIs on a nightly job with secrets, never on PRs.
- **Visual regression**: page SVG and exported PNG compared with a perceptual diff (pixelmatch or SSIM) against goldens using the mock image backend (deterministic art); threshold 0.1 percent pixels.
- **E2E** (Playwright): full core loop with mock backends: create project from fixture duck photo, approve sheet, pick suggestion, render strip, edit balloon, approve, finalize, paginate, build book, export PDF and web; child mode flow; reader flow.
- **Smoke**: `tests/smoke/smoke.sh` runs doctor, then CLI `new` + `auto` + `finalize` + `pages` + `export --format pdf,web` with fake LLM, fake vision, and mock image backend; asserts files exist and PDF has expected pages.
- **Model evaluation** (manual plus scripted, per release): three fixture stories (duck from photo, robot from text, newsletter GPU gag-a-day). Score story coherence, suggestion usefulness, character consistency (vision QA scores plus human spot check), lettering readability. Release blocked if consistency NFR-004 fails or any human score averages under 4 of 5.
- **Regression**: one test per fixed bug, never deleted.

#### Naming convention

```
Unit:        test_{module}_{function}_{scenario}_{expected_outcome}
Integration: it_{component}_{operation}_{scenario}
Smoke:       smoke_{feature}_{minimal_assertion}
E2E:         e2e_{user_story_id}_{scenario}
Regression:  regression_{gh_issue_number}_{what_was_broken}
Visual:      vis_{surface}_{template_or_state}
```

#### Fixtures

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

#### Minimum scenario table (expand per feature)

| ID | Scenario | Type | Status |
|---|---|---|---|
| test_assets_ingest_exif_gps_stripped | Uploads lose location data | Unit | ⚠️ |
| test_assets_ingest_heic_converted_to_png | HEIC support | Unit | ⚠️ |
| test_cast_reference_person_detected_requires_attestation | People guard | Unit | ⚠️ |
| test_cast_originality_denylisted_name_blocked | Name denylist | Unit | ⚠️ |
| test_cast_originality_resemblance_flag_blocks_approval | Resemblance check | Unit | ⚠️ |
| test_story_bible_target_strips_out_of_range_rejected | Bible validation | Unit | ⚠️ |
| test_story_arc_progress_updates_after_approval | Arc tracking | Unit | ⚠️ |
| test_story_suggest_returns_three_distinct_intents | Suggestions shape | Unit | ⚠️ |
| test_story_suggest_similar_options_regenerated_once | Distinctness check | Unit | ⚠️ |
| test_story_suggest_final_stage_includes_end_here | End-here option | Unit | ⚠️ |
| test_story_writer_unknown_speaker_rejected | Cast integrity | Unit | ⚠️ |
| test_story_writer_kids_word_limit_enforced | Reading level | Unit | ⚠️ |
| test_panels_compiler_includes_no_text_constraint | No-text rule | Unit | ⚠️ |
| test_panels_compiler_adds_headroom_when_dialogue | Balloon space | Unit | ⚠️ |
| test_panels_qa_detected_text_triggers_retake | OCR retake | Unit | ⚠️ |
| test_panels_qa_low_consistency_keeps_best_take | Best take | Unit | ⚠️ |
| test_letter_layout_balloons_avoid_character_boxes | Placement | Unit | ⚠️ |
| test_letter_layout_reading_order_left_to_right | Reading order | Unit | ⚠️ |
| test_letter_layout_text_never_overflows_panel | Overflow | Unit | ⚠️ |
| test_layout_paginate_never_splits_strip_by_default | Pagination | Unit | ⚠️ |
| test_events_undo_redo_roundtrip_lettering_edit | Undo | Unit | ⚠️ |
| it_export_pdf_fonts_embedded_and_text_selectable | PDF quality | Integration | ⚠️ |
| it_export_pdf_print_adds_bleed | Print bleed | Integration | ⚠️ |
| it_export_web_single_file_works_offline | Web export | Integration | ⚠️ |
| it_export_web_has_data_narrate_markup | audio-smith compat | Integration | ⚠️ |
| it_jobs_kill_worker_mid_render_resumes | Resilience | Integration | ⚠️ |
| it_comfyui_qwen_edit_workflow_returns_image | Local backend | Integration (GPU) | ⚠️ |
| vis_page_strip_stack_us_comic | Page golden | Visual | ⚠️ |
| vis_page_three_tier_a4 | Page golden | Visual | ⚠️ |
| smoke_cli_auto_to_pdf_outputs_exist | End to end | Smoke | ⚠️ |
| e2e_US004_child_mode_pick_choice_renders_strip | Child mode | E2E | ⚠️ |
| e2e_US008_drag_balloon_persists_after_reload | Lettering edit | E2E | ⚠️ |
| e2e_US013_export_book_pdf_from_studio | Export | E2E | ⚠️ |
| e2e_US020_branch_switch_shows_alternate_strips | Branching | E2E | ⚠️ |

---

## Step 2: GitHub Project Setup

### 2.1 Repository initialization

```bash
gh repo create mohnishbasha/mr-comic-smith \
  --public \
  --description "Turn a story idea or a photo into a growing comic strip with AI plot suggestions, then stitch it into pages and a book you can export as PNG, PDF, or a web page." \
  --homepage "https://getcomicsmith.com" \
  --license mit \
  --gitignore Python
git clone git@github.com:mohnishbasha/mr-comic-smith.git && cd mr-comic-smith
# Replace the generated .gitignore with the one specified in S0-T03
git checkout -b develop && git push -u origin develop
git checkout -b staging && git push -u origin staging
gh repo edit --default-branch develop
gh repo edit --enable-issues --enable-projects --enable-wiki=false \
  --delete-branch-on-merge --enable-squash-merge --enable-merge-commit=false \
  --enable-rebase-merge=false
gh repo edit --add-topic comics,comic-generator,storytelling,image-generation,character-consistency,comfyui,local-first,python,react,mcp,snackonai
```

### 2.2 Branch protection

```bash
gh api -X PUT repos/mohnishbasha/mr-comic-smith/branches/main/protection \
  -f required_status_checks.strict=true \
  -f 'required_status_checks.contexts[]=lint-and-typecheck' \
  -f 'required_status_checks.contexts[]=unit-tests' \
  -f 'required_status_checks.contexts[]=coverage' \
  -f 'required_status_checks.contexts[]=integration-tests' \
  -f 'required_status_checks.contexts[]=visual-regression' \
  -f 'required_status_checks.contexts[]=e2e-tests' \
  -f 'required_status_checks.contexts[]=check-versions' \
  -F enforce_admins=true \
  -F required_pull_request_reviews.required_approving_review_count=1 \
  -F required_pull_request_reviews.dismiss_stale_reviews=true \
  -F restrictions=null -F allow_force_pushes=false -F allow_deletions=false \
  -F required_linear_history=true
# staging: same checks, 1 approval
# develop: lint-and-typecheck, unit-tests, coverage required; no approval required
```

### 2.3 Git branch strategy

```
main      -> production releases only, protected, requires 1+ approvals
staging   -> staging environment, requires 1 approval
develop   -> integration branch, all feature work merges here
feature/* -> off develop
fix/*     -> off develop (or main for hotfixes)
chore/*   -> non-functional changes
docs/*    -> documentation only
```

Rules:
- No direct commits to `main` or `staging`. Ever.
- All PRs require passing CI before merge.
- Hotfixes branch from `main`, merge to `main` and back-merge to `develop`.
- `main` tagged for every release using semantic versioning.

### 2.4 Label taxonomy (create all 48)

```bash
create() { gh label create "$1" --color "$2" --description "$3" --force; }

# type (10)
create "type: feature"      "1D76DB" "New user-facing capability"
create "type: bug"          "D73A4A" "Something is broken"
create "type: chore"        "C5DEF5" "Tooling, deps, maintenance"
create "type: docs"         "0075CA" "Documentation only"
create "type: test"         "BFD4F2" "Test infrastructure or coverage"
create "type: refactor"     "D4C5F9" "No behavior change"
create "type: perf"         "FBCA04" "Performance"
create "type: security"     "B60205" "Security or safety hardening"
create "type: spec"         "5319E7" "Spec document change"
create "enhancement"        "A2EEEF" "Deferred or future improvement"

# area (20)
for a in story cast style panels qa letter layout book export \
         backend-image backend-llm backend-vision jobs db studio reader cli server mcp harness; do
  create "area: $a" "0E8A16" "Area: $a"
done
create "area: ci"           "0E8A16" "GitHub Actions workflows"
create "area: packaging"    "0E8A16" "Docker, Helm, PyPI, npm"
create "area: safety"       "0E8A16" "Originality, people, audience guards"

# priority (4)
create "priority: p0"       "B60205" "Blocks the sprint gate"
create "priority: p1"       "D93F0B" "Must ship this sprint"
create "priority: p2"       "FBCA04" "Should ship this sprint"
create "priority: p3"       "C2E0C6" "Nice to have"

# status (3)
create "status: blocked"    "000000" "Waiting on a dependency"
create "status: needs-spec" "5319E7" "Spec must be updated first"
create "status: in-review"  "FEF2C0" "PR open"

# size (4)
create "size: S"            "EDEDED" "Half day"
create "size: M"            "D4D4D4" "One day"
create "size: L"            "BDBDBD" "Two days"
create "size: XL"           "9E9E9E" "Three+ days, split before starting"

# sprint (10)
for n in 0 1 2 3 4 5 6 7 8 9; do create "sprint: $n" "F9D0C4" "Sprint $n"; done
```

### 2.5 Milestones

```bash
ms() { gh api repos/mohnishbasha/mr-comic-smith/milestones -f title="$1" -f description="$2" -f due_on="$3"; }
ms "Sprint 0: Scaffold"                    "Tooling, CI, agent files, DB, Studio shell, doctor"          "2026-11-09T23:59:59Z"
ms "Sprint 1: Story Engine"                "Bible, arc, suggestions, strip writer, branching, finalize"  "2026-11-16T23:59:59Z"
ms "Sprint 2: Cast, Style, Backends"       "Reference ingest, vision, character sheets, image backends" "2026-11-23T23:59:59Z"
ms "Sprint 3: Panels, Lettering, Strips"   "Render, QA, retakes, lettering engine, strip loop in Studio" "2026-12-07T23:59:59Z"
ms "Sprint 4: Pages and Book"              "Page composer, templates, book builder"                       "2026-12-14T23:59:59Z"
ms "Sprint 5: Export"                      "PNG/JPG/WebP, PDF screen+print, CBZ, long strip, web reader" "2026-12-21T23:59:59Z"
ms "Sprint 6: Release v1.0.0"              "Child mode polish, safety review, evals, docs, ship"         "2026-12-28T23:59:59Z"
ms "Sprint 7: Server and MCP"              "REST hardening, LAN classroom mode, MCP tools"               "2027-01-04T23:59:59Z"
ms "Sprint 8: Harness Integrations"        "Pi extension, Goose, OpenCode, Claude Code skill"            "2027-01-11T23:59:59Z"
ms "Sprint 9: Packaging"                   "Docker CPU/CUDA, Compose with ComfyUI+Ollama, Helm, cosign"  "2027-01-18T23:59:59Z"
```

Adjust dates to the real start date; keep relative durations (Sprint 3 is two weeks).

### 2.6 Project board

```bash
gh project create --owner mohnishbasha --title "mr-comic-smith"
```

Status columns: **Backlog, Ready, In Progress, In Review, Done**. Custom fields: Sprint (0 to 9), Size (S to XL), Priority (p0 to p3), Area.

Automation: new issue -> Backlog; assigned with linked branch -> In Progress; PR opened -> In Review; PR merged or issue closed -> Done; reopened -> In Progress.

### 2.7 Templates

`.github/ISSUE_TEMPLATE/task.yml`

```yaml
name: Task
description: A sprint task from docs/SPRINT_PLAN.md
title: "[S{sprint}-T{nn}] "
body:
  - type: input
    id: task_id
    attributes: {label: Task ID, placeholder: S3-T05}
    validations: {required: true}
  - type: textarea
    id: description
    attributes: {label: Description}
    validations: {required: true}
  - type: textarea
    id: acceptance
    attributes: {label: Acceptance criteria, value: "- [ ] "}
    validations: {required: true}
  - type: input
    id: spec_refs
    attributes: {label: Spec references, placeholder: "PRD FR-019, ARCHITECTURE ADR-003, DESIGN Lettering"}
  - type: input
    id: depends
    attributes: {label: Depends on, placeholder: "#21, #22"}
  - type: textarea
    id: tests
    attributes: {label: Test scenarios (TEST_PLAN ids)}
```

`.github/ISSUE_TEMPLATE/bug.yml`

```yaml
name: Bug report
description: Something is broken
labels: ["type: bug"]
body:
  - type: textarea
    id: what
    attributes: {label: What happened}
    validations: {required: true}
  - type: textarea
    id: repro
    attributes: {label: Steps to reproduce (project, strip/panel, backend, style)}
    validations: {required: true}
  - type: textarea
    id: expected
    attributes: {label: Expected}
  - type: textarea
    id: screenshots
    attributes: {label: Screenshots or exported files}
  - type: textarea
    id: doctor
    attributes: {label: Output of `mr-comic-smith doctor --json`, render: json}
  - type: input
    id: version
    attributes: {label: Version (`mr-comic-smith --version`)}
```

`.github/ISSUE_TEMPLATE/generation-quality.yml`: for "the model drew the wrong thing" reports, with fields for panel spec JSON, compiled prompt, backend, seed, and attached take images. Label `area: qa`.

`.github/PULL_REQUEST_TEMPLATE.md`

```markdown
## Summary
Closes #

## Spec impact (choose one)
- [ ] A: Internal only, no spec change
- [ ] B: Spec updated in this PR: (list docs/ sections)
- [ ] C: Spec issue filed: #

## Tests
- [ ] Failing tests written first (TDD)
- [ ] TEST_PLAN.md scenarios added and marked ✅
- [ ] Visual goldens updated intentionally (attach before/after) or unchanged
- [ ] Coverage thresholds hold

## UI changes
- [ ] Screenshots attached (light, dark, child mode if affected)

## Checklist
- [ ] `make lint` exits 0
- [ ] `make typecheck` exits 0
- [ ] `make test` exits 0
- [ ] CHANGELOG.md [Unreleased] updated (if user-facing)
- [ ] No em dashes added in prose, comments, or UI copy
```

---

## Step 3: Create All GitHub Issues

### 3.1 Issue creation protocol

For every task in `docs/SPRINT_PLAN.md`:

1. Title: `[S{n}-T{nn}] {Imperative title}` (example: `[S3-T06] Implement balloon auto-placement avoiding character boxes`).
2. Body: Task template fields with description and acceptance criteria copied verbatim from SPRINT_PLAN.md, spec references, TEST_PLAN scenario ids.
3. Labels: one `type:`, one or more `area:`, one `priority:`, one `size:`, one `sprint:`.
4. Milestone: the sprint milestone.
5. Add to the project board in Backlog with fields set.
6. After all issues exist, replace task-id dependencies with issue numbers.

```bash
python scripts/create-issues.py --dry-run   # parses SPRINT_PLAN.md task blocks
python scripts/create-issues.py
```

### 3.2 Implementation comment protocol

Before closing any issue, add:

```markdown
### Implementation
- **PR:** #NN
- **What changed:** (2 to 5 bullets)
- **Spec sections updated:** (or "none, internal only")
- **Tests added:** unit N, integration N, visual N, e2e N (names)
- **Coverage delta:** comic_smith/letter 88.0% -> 91.2%
- **Screenshots:** (UI tasks)
- **Follow-ups:** (new issues, with numbers)
```

### 3.3 Issue closing protocol

An issue closes only when its PR is merged into `develop`, every acceptance criterion is checked, the implementation comment exists, and its TEST_PLAN scenarios are ✅ or ❌ with reason.

---

## Step 4 onward: Sprint Execution

### Sprint Start Protocol
1. Move all sprint issues from Backlog to In Progress on the project board
2. Assign issues to yourself
3. Pull latest `develop`, verify it is up to date with `staging`
4. Pick the highest-priority unblocked issue
5. Read the relevant PRD, ARCHITECTURE, DESIGN, and TEST_PLAN sections before writing code
6. Add test scenarios for this feature to `docs/TEST_PLAN.md` before writing code
7. Create a branch: `git checkout -b feature/s{n}-t{nn}-{short-slug} develop`
8. Write failing tests first (TDD), confirm they fail for the right reason
9. Implement until tests pass
10. Update `docs/TEST_PLAN.md` to mark new scenarios as ✅ Automated
11. Update relevant spec doc in the same branch if behavior changed
12. Open PR against `develop`; PR description must state which spec sections updated
13. Wait for CI (lint + type-check + unit + integration + visual + coverage threshold)
14. Merge
15. Add implementation comment and close issue
16. Pick next issue

**TDD is mandatory.** No production code without a failing test that requires it. UI components get a vitest component test or a Playwright test first. Exceptions (pure config, generated code, golden image creation) must be stated in the PR.

### Spec Change Protocol
Any PR that changes user-facing behavior, API contracts, data formats, the database schema, UI flows, or architectural decisions must satisfy one of:

- **A: No spec change:** PR description explicitly states "internal only, no spec change" and reviewer agrees
- **B: Spec updated in same PR:** Relevant `docs/` file updated alongside code
- **C: Spec issue filed:** Separate GitHub issue created before code PR merges, scheduled in current sprint, closed within same sprint

Option C is not a deferral mechanism.

Spec docs are living documents. Every PR that changes behavior updates the relevant spec doc in the same commit.

### Test Scenario Generation Protocol
1. Open `docs/TEST_PLAN.md` and add scenarios for the feature before writing code
2. Use naming convention: `{type}_{module}_{operation}_{scenario}_{outcome}`
3. Mark new scenarios as ⚠️ Deferred until test written, then ✅ Automated
4. Scenarios too hard to automate: ❌ Skipped with written reason and manual step
5. Test file must have a test for every ✅ scenario when feature PR merges

### Sprint End Protocol
1. All sprint issues closed or moved to next sprint with explanation
2. Run full sprint gate checklist
3. Spec doc audit: review all five docs for stale sections, update before proceeding
4. Coverage check: `make coverage` (pytest-cov + vitest --coverage), confirm meets targets
5. Merge `develop` into `staging` via PR
6. Run manual smoke tests on staging using TEST_PLAN.md smoke checklist
7. Document sprint retrospective in `docs/RETROSPECTIVES.md`:
   - What was built (link to closed issues)
   - Spec sections updated
   - Tests added (counts by type)
   - Coverage delta
   - What worked, what didn't, what to change
8. Tag staging build: `git tag sprint-{n}-complete && git push origin sprint-{n}-complete`

### Definition of Done

A feature is done when:
- [ ] Code implemented and runs without errors
- [ ] Unit tests written and passing
- [ ] `make lint` exits 0 with 0 warnings (ruff, eslint)
- [ ] `make typecheck` exits 0 (mypy --strict, tsc --noEmit)
- [ ] Coverage has not dropped below thresholds
- [ ] Visual goldens pass or were intentionally updated with before/after in the PR
- [ ] PR opened against `develop` with issue linked
- [ ] CI green on all 3 platforms
- [ ] Spec doc changes committed in same PR (or Option A/C confirmed)
- [ ] New test scenarios added to TEST_PLAN.md
- [ ] Implementation comment added to issue before closing

### Regression Test Lifecycle

```
Bug reported -> GitHub issue created (type: bug label)
      |
Reproduction confirmed -> regression test written (FAILS)
      |
Fix implemented -> regression test passes
      |
PR opened: regression test + fix in same commit
      |
PR merged -> issue closed -> test runs in CI forever
```

Regression tests are never deleted. Generation-quality bugs get a regression test against the deterministic layer that caused them (compiler, QA threshold, placement), never against model output.

---
## Sprint 0: Scaffold

**Milestone:** Sprint 0: Scaffold
**Duration:** 1 week
**Goal:** A repository where `mr-comic-smith --version`, `doctor`, and `studio` (empty shell) run; database migrations work; CI is green on all platforms; every agent file exists.

### S0-T01: Commit the five spec documents
- **Labels:** type: spec, area: ci, priority: p0, size: L, sprint: 0
- **Description:** Generate PRD, ARCHITECTURE, DESIGN, SPRINT_PLAN, TEST_PLAN per Step 1. Done before Step 2; recorded retroactively as an issue.
- **AC:**
  - [ ] All five files under `docs/` with every required section
  - [ ] Every FR has acceptance criteria; every US maps to at least one FR
  - [ ] First commit on `main`
- **Depends on:** none

### S0-T02: Python project skeleton
- **Labels:** type: chore, area: cli, priority: p0, size: M, sprint: 0
- **Description:** `pyproject.toml` (hatchling, Python `>=3.12,<3.14`), `uv.lock`, `comic_smith/` with version via `importlib.metadata`, typer CLI with `--version`. Optional dependency groups: `comfyui`, `gemini`, `openai`, `anthropic`, `ocr`, `server` (included by default for Studio), `mcp`, `dev`.
- **AC:**
  - [ ] `uv sync --all-extras --dev` works on macOS arm64, Linux x86_64, Linux arm64
  - [ ] `uv run mr-comic-smith --version` prints the pyproject version
  - [ ] Base install does not pull torch
- **Depends on:** S0-T01

### S0-T03: Repository hygiene files
- **Labels:** type: chore, area: ci, priority: p0, size: S, sprint: 0
- **Description:** `.gitignore`, `.editorconfig`, `.gitattributes` (LFS for `tests/fixtures/images/*`, `tests/fixtures/goldens/*`, `comic_smith/letter/fonts/*`), `LICENSE` (MIT, Serverless Ventures LLC, 2026), `THIRD_PARTY_LICENSES.md` stub, `CHANGELOG.md` with `[Unreleased]`, `SECURITY.md`, `CODE_OF_CONDUCT.md`, `CONTRIBUTING.md` (DCO sign-off).
- **.gitignore must include:**
  ```
  # Python
  __pycache__/
  *.py[cod]
  .venv/
  dist/
  build/
  *.egg-info/
  .mypy_cache/
  .ruff_cache/
  .pytest_cache/
  # TypeScript / Node / Bun
  node_modules/
  *.tsbuildinfo
  web/studio/dist/
  reader/dist/
  integrations/pi/dist/
  comic_smith/server/static/
  .bun/
  # Environment
  .env
  .env.*
  !.env.*.example
  # Test / coverage
  coverage/
  .coverage
  htmlcov/
  coverage.xml
  playwright-report/
  test-results/
  tests/visual/__diff__/
  # Product runtime
  projects/
  exports/
  library/
  *.db
  *.db-shm
  *.db-wal
  !tests/fixtures/projects/**/project.db
  # Models and backends
  models/
  ComfyUI/
  *.safetensors
  *.ckpt
  *.gguf
  # Agent sessions
  .pi/sessions/
  .agent/sessions/
  CLAUDE.local.md
  # OS / editor
  .DS_Store
  Thumbs.db
  .vscode/settings.json
  .idea/
  # Lock files ARE tracked: uv.lock, bun.lockb, package-lock.json
  ```
- **AC:** all files present; fixtures not ignored; user projects ignored
- **Depends on:** S0-T02

### S0-T04: Lint, format, type-check toolchain
- **Labels:** type: chore, area: ci, priority: p0, size: S, sprint: 0
- **Description:** ruff (lint + format, rules `E,F,W,I,N,UP,B,A,C4,SIM,RUF,S,PTH,TID,PL`), mypy `--strict`, ESLint (`@typescript-eslint/strict-type-checked`), Prettier, pre-commit (ruff, mypy, eslint, codespell, check-yaml, check-json, end-of-file-fixer, a hook rejecting U+2014 and U+2013 in `*.md *.py *.ts *.tsx *.json *.yaml`). `Makefile`: `lint format typecheck test test-int visual coverage smoke e2e check-versions build studio-dev`.
- **AC:** `make lint typecheck` exit 0; em dash hook fails on a test file containing the character
- **Depends on:** S0-T02

### S0-T05: Test harness, coverage thresholds, visual diff
- **Labels:** type: test, area: ci, priority: p0, size: M, sprint: 0
- **Description:** pytest + pytest-cov + pytest-asyncio + pytest-timeout + hypothesis + respx + syrupy; vitest + @testing-library/react; Playwright; visual diff helper (`tests/visual/compare.py` using SSIM via scikit-image and a pixel threshold). Directories `tests/{unit,integration,smoke,e2e,visual,regression,fixtures}`. `.coverage-thresholds.toml` + `scripts/check-coverage.py`.
- **AC:** `make test`, `make visual` run; threshold script fails under target
- **Depends on:** S0-T04

### S0-T06: Database and migrations
- **Labels:** type: feature, area: db, priority: p0, size: M, sprint: 0
- **Description:** SQLAlchemy 2 models for every table in ARCHITECTURE, Alembic migrations, WAL mode, foreign keys on, `Project.open(path)` that creates or migrates. Content-addressed asset store with atomic writes.
- **AC:** migrations up and down tested; concurrent readers during a write work; asset write is atomic (temp + rename) and idempotent
- **Depends on:** S0-T05

### S0-T07: Event log and undo framework
- **Labels:** type: feature, area: db, priority: p1, size: M, sprint: 0
- **Description:** `events.py` with `apply(event)`, `undo()`, `redo()`, inverse payloads, actor field. Every service mutation goes through it.
- **AC:** property test: random sequences of apply/undo/redo restore identical state
- **Depends on:** S0-T06

### S0-T08: Studio shell
- **Labels:** type: feature, area: studio, priority: p0, size: M, sprint: 0
- **Description:** `web/studio` with Vite + React 18 + TypeScript + Zustand + TanStack Query + React Router; design tokens from the Design System as CSS variables; app frame with header, navigation tabs, empty Home; FastAPI serves the built assets at `/` and `/v1/healthz`. `mr-comic-smith studio` builds-if-needed (dev) or serves bundled static (release) and opens the browser.
- **AC:** Studio loads in Chrome, Safari, Firefox; light and dark themes; Playwright smoke passes
- **Depends on:** S0-T02

### S0-T09: CI workflow
- **Labels:** type: chore, area: ci, priority: p0, size: M, sprint: 0
- **Description:** `.github/workflows/ci.yml`: `lint-and-typecheck` (ubuntu, macos, windows), `unit-tests` (3 OS x py3.12, 3.13, plus vitest), `coverage` (ubuntu, Codecov), `integration-tests` (ubuntu; Ollama tiny model; Playwright Chromium; stub ComfyUI server), `visual-regression` (ubuntu, fixed fonts, uploads diff images on failure), `e2e-tests`, `check-versions`, `smoke`. `gpu-integration` on self-hosted `gpu` runner (dispatch and PRs to staging/main). Dependabot for uv, npm, github-actions, docker.
- **AC:** all jobs green on the skeleton; concurrency cancels superseded runs
- **Depends on:** S0-T05, S0-T08

### S0-T10: Version scripts
- **Labels:** type: chore, area: ci, priority: p1, size: S, sprint: 0
- **Description:** `scripts/check-versions.sh`, `scripts/bump-version.sh`, `scripts/extract-changelog.sh` per the Versioning section.
- **AC:** mismatch exits 1 naming the file; extract prints only the requested section
- **Depends on:** S0-T08

### S0-T11: Agent repository files
- **Labels:** type: docs, area: harness, priority: p0, size: M, sprint: 0
- **Description:** `AGENTS.md`, `CLAUDE.md`, `SKILLS.md`, `SOUL.md`, `.agent/skills/run-tests/`, `.agent/skills/check-types/`, `.agent/skills/make-fixture-comic/` per Appendix K.
- **AC:** `CLAUDE.md` starts with `@import AGENTS.md`; skills run green; SOUL.md has at least 6 hard constraints and no commands or paths
- **Depends on:** S0-T04, S0-T05

### S0-T12: Config and doctor skeleton
- **Labels:** type: feature, area: cli, priority: p1, size: M, sprint: 0
- **Description:** pydantic-settings with env prefix `COMIC_SMITH_`, project-level `comic-smith.toml`, precedence flags > env > file > defaults. Doctor with check registry: Python, disk, Chromium (Playwright) present, fonts present, writable data dir.
- **AC:** precedence unit tests; doctor `--json`; exit 3 on required failure
- **Depends on:** S0-T02

### Sprint 0 Gate (hard stop)
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

### S1-T01: LLM provider interface and providers
- **Labels:** type: feature, area: backend-llm, priority: p0, size: L, sprint: 1
- **Description:** `LLMProvider.complete_json` with JSON Schema; `OllamaProvider` (REST `/api/chat` with `format` set to the schema), `AnthropicProvider` (official SDK, tool-use or structured output for JSON), `OpenAICompatProvider` (`response_format` JSON schema), `FakeProvider` (recorded fixtures by prompt hash). Retries with backoff; timeout; token usage recorded. Provider string format: `ollama:qwen3:14b`, `anthropic:<model-id>`, `openai_compat:<base_url>#<model>`.
- **AC:** respx unit tests per provider; Ollama integration test with a tiny model; schema-invalid output triggers one corrective retry with validation errors
- **Depends on:** Sprint 0

### S1-T02: JSON Schemas and models
- **Labels:** type: feature, area: story, priority: p0, size: M, sprint: 1
- **Description:** pydantic models and exported JSON Schemas for bible, suggestions, panel spec, beat, continuity report; `schemas/` published.
- **AC:** round-trip tests; schemas validate fixture documents
- **Depends on:** S0-T06

### S1-T03: Story bible
- **Labels:** type: feature, area: story, priority: p0, size: L, sprint: 1
- **Description:** Generate the bible from seed narrative (and later reference descriptions); edit; version on every change; arc templates (three-act, hero's-journey-lite, problem-try-try-succeed, gag-a-day, mystery) with stages. Prompt template `story/prompts/bible.md` versioned.
- **AC:** FR-009 ACs; editing creates a new version and an undoable event
- **Depends on:** S1-T01, S1-T02

### S1-T04: Arc tracking and open threads
- **Labels:** type: feature, area: story, priority: p0, size: M, sprint: 1
- **Description:** After a strip is approved, update the arc stage and open threads via an LLM call that returns a structured diff (threads opened, threads closed, stage); progress computation from stage index and target strips.
- **AC:** FR-010 ACs
- **Depends on:** S1-T03

### S1-T05: Plot suggestions
- **Labels:** type: feature, area: story, priority: p0, size: L, sprint: 1
- **Description:** Generate continue, twist, and steer options plus end-here at the final stage or target length; distinctness check using sentence embeddings (Ollama embeddings endpoint, `nomic-embed-text` class model, or provider equivalent); regenerate once if any pair exceeds 0.85 cosine. Context passed to the LLM: bible, last three strip summaries, open threads, arc stage, audience rules.
- **AC:** FR-011 ACs (thumbnails deferred to S3-T09)
- **Depends on:** S1-T04

### S1-T06: Custom beat normalization
- **Labels:** type: feature, area: story, priority: p1, size: S, sprint: 1
- **Description:** Normalize free-text beats into the beat structure; return for confirmation.
- **AC:** FR-012 ACs
- **Depends on:** S1-T05

### S1-T07: Strip writer
- **Labels:** type: feature, area: story, priority: p0, size: L, sprint: 1
- **Description:** Beat to Panel Specs with audience reading rules (word limits per balloon, balloons per panel, words per strip), cast integrity, continuity notes from previous strips, shot variety rule (no more than two consecutive panels with the same shot), `balloon_space` hint per panel.
- **AC:** FR-013 ACs; shot variety enforced by validator
- **Depends on:** S1-T05

### S1-T08: Text moderation and audience guard
- **Labels:** type: security, area: safety, priority: p0, size: M, sprint: 1
- **Description:** Audience rule blocks in every system prompt; moderation pass (LLM classifier with a strict JSON verdict) on bible, suggestions, beats, and scripts; denylist check for copyrighted names (starter list in `comic_smith/cast/denylist.yaml`).
- **AC:** FR-028 text ACs; blocked content returns `ComicSmithError(code="safety_blocked")` with a plain-words explanation
- **Depends on:** S1-T01

### S1-T09: Branching
- **Labels:** type: feature, area: story, priority: p1, size: M, sprint: 1
- **Description:** Create, switch, rename, delete branches; strip listing per branch follows the parent chain up to the fork point.
- **AC:** FR-021 ACs
- **Depends on:** S1-T07

### S1-T10: Finalize
- **Labels:** type: feature, area: story, priority: p0, size: M, sprint: 1
- **Description:** Continuity review (structured report), three titles and a blurb, lock; reopen creates a new story version.
- **AC:** FR-022 ACs
- **Depends on:** S1-T09

### S1-T11: Story CLI
- **Labels:** type: feature, area: cli, priority: p0, size: M, sprint: 1
- **Description:** `new`, `bible`, `suggest`, `strip --pick/--beat` (script only for now), `branch`, `finalize`, `auto` (script-only auto mode using the policy), all with `--json`.
- **AC:** smoke: `new --narrative` + `auto --until-target` + `finalize` with FakeProvider produces a finalized story of N scripted strips
- **Depends on:** S1-T10

### Sprint 1 Gate (hard stop)
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

### S2-T01: Asset ingest
- **Labels:** type: feature, area: cast, priority: p0, size: M, sprint: 2
- **Description:** Pillow + pillow-heif ingest: type sniffing (not extension), size limits, EXIF strip, orientation fix, HEIC to PNG, downscale to 4096 px long edge, SHA-256 store.
- **AC:** FR-002 ACs; corrupt and oversized fixtures rejected with clear errors
- **Depends on:** S0-T06

### S2-T02: Vision provider interface and providers
- **Labels:** type: feature, area: backend-vision, priority: p0, size: L, sprint: 2
- **Description:** `describe` (structured JSON) and `locate` (bounding boxes for named targets, normalized 0 to 1 coordinates). Providers: `OllamaVisionProvider` (Qwen2.5-VL class model), `AnthropicVisionProvider`, `OpenAICompatVisionProvider`, `FakeVisionProvider`.
- **AC:** respx tests; locate returns valid boxes for fixtures; doctor checks reachability
- **Depends on:** S1-T01

### S2-T03: Reference understanding and people guard
- **Labels:** type: feature, area: safety, priority: p0, size: M, sprint: 2
- **Description:** FR-003 describe; FR-007 person detection and attestation requirement; public-figure decline in prompt layer.
- **AC:** person fixture blocks sheet generation until attestation; photoreal styles disabled for person-derived characters
- **Depends on:** S2-T02

### S2-T04: ImageBackend interface, registry, mock backend
- **Labels:** type: feature, area: backend-image, priority: p0, size: M, sprint: 2
- **Description:** Capabilities, ImageRequest, GeneratedImage; registry; `MockBackend` that draws deterministic flat-color scenes with labeled shapes per character (Pillow), respects size and seed, and simulates progress and occasional failures (configurable) for testing.
- **AC:** mock outputs are byte-identical across platforms for the same request
- **Depends on:** S0-T06

### S2-T05: ComfyUI backend with bundled workflows
- **Labels:** type: feature, area: backend-image, priority: p0, size: XL (split: client, workflows, references), sprint: 2
- **Description:** Client for a running ComfyUI server: upload reference images, queue a workflow (prompt JSON), stream progress over its websocket, fetch outputs from history, interrupt on cancel. Workflow templates in `backends/image/workflows/` with named input slots (prompt, negative, refs[], width, height, seed, steps, mask). Ship: `qwen-image-edit` (default, Apache-2.0), `flux-kontext-dev` (opt-in, non-commercial license gate), `sdxl-ipadapter` (fallback for smaller GPUs). Workflow manifest declares required model files with download URLs and SHA-256; `mr-comic-smith models pull <workflow>` downloads into ComfyUI's model folders. Verify current node names, model files, licenses, and VRAM requirements at implementation time and record them in ARCHITECTURE.
- **AC:** stub-server integration tests in CI; GPU integration test renders a panel with two reference images; license gate enforced
- **Depends on:** S2-T04

### S2-T06: Gemini image backend
- **Labels:** type: feature, area: backend-image, priority: p0, size: M, sprint: 2
- **Description:** Google GenAI SDK, current image-generation model with multiple reference images (verify model id and reference limits at implementation time); key from env or keyring; cloud badge.
- **AC:** respx contract tests; nightly live test behind secret
- **Depends on:** S2-T04

### S2-T07: OpenAI images backend
- **Labels:** type: feature, area: backend-image, priority: p1, size: M, sprint: 2
- **Description:** OpenAI SDK images generate and edit with reference images and masks (verify current model id at implementation time).
- **AC:** respx contract tests; nightly live test behind secret
- **Depends on:** S2-T04

### S2-T08: Style presets
- **Labels:** type: feature, area: style, priority: p0, size: M, sprint: 2
- **Description:** Six built-in presets (FR-008) as YAML with tokens, negative tokens, palette hints, line weight, per-backend overrides; custom preset creation; preview grid job.
- **AC:** presets validate; preview renders with mock backend
- **Depends on:** S2-T04

### S2-T09: Character sheet generation and approval
- **Labels:** type: feature, area: cast, priority: p0, size: L, sprint: 2
- **Description:** Generate views and expressions using the reference image (when the backend accepts references) plus description and style; compose a sheet image; per-view regenerate; approve; derive visual DNA paragraph from description plus approved front view via vision model; text-only characters (FR-005).
- **AC:** FR-004 and FR-005 ACs
- **Depends on:** S2-T03, S2-T05, S2-T08

### S2-T10: Originality guard
- **Labels:** type: security, area: safety, priority: p0, size: M, sprint: 2
- **Description:** Denylist on user text and compiled prompts; resemblance question to the vision model on approved sheets; block approval on match with an explanation.
- **AC:** FR-006 ACs; denylist is data, editable, and versioned
- **Depends on:** S2-T09

### S2-T11: Cast and library CLI plus doctor checks
- **Labels:** type: feature, area: cli, priority: p1, size: M, sprint: 2
- **Description:** `cast add|sheet|approve`, `library add|list|import`, `models pull`; doctor checks for ComfyUI reachability, installed workflow models, GPU and VRAM (nvidia-smi or torch if present), cloud keys present.
- **AC:** CLI flows covered by smoke with mock backend
- **Depends on:** S2-T09

### Sprint 2 Gate (hard stop)
- [ ] Duck photo fixture becomes an approved character sheet (mock in CI, ComfyUI on GPU runner, Gemini on nightly)
- [ ] People and originality guards verified
- [ ] Six style presets preview correctly
- [ ] Retrospective written, `sprint-2-complete` tagged

---

## Sprint 3: Panels, Lettering, and Strips (Core Feature)

**Milestone:** Sprint 3: Panels, Lettering, Strips
**Duration:** 2 weeks
**Goal:** The complete co-plotting loop works in the Studio: pick a plot, edit the script, render consistent panels, letter them, approve, repeat. This sprint IS the product.

### S3-T01: Prompt compiler
- **Labels:** type: feature, area: panels, priority: p0, size: L, sprint: 3
- **Description:** Panel Spec + style + characters to ImageRequest: ordered prompt sections (style, shot and angle vocabulary mapped per backend, setting, each character's visual DNA with position, pose, expression, facing, action, mood, continuity), negative prompt with the no-text constraint, reference selection (pick the sheet views closest to required facing and expression; respect backend `max_reference_images`; prioritize characters by screen importance), aspect ratio from layout slot, headroom hint from `balloon_space`.
- **AC:** FR-015 ACs; snapshot tests per backend; never exceeds backend reference limit
- **Depends on:** Sprint 2

### S3-T02: Job queue and workers
- **Labels:** type: feature, area: jobs, priority: p0, size: L, sprint: 3
- **Description:** SQLite job queue, GPU worker and text workers, priorities, cancellation, resume after restart, progress events over WebSocket.
- **AC:** kill-and-resume integration test; priority ordering test
- **Depends on:** S0-T06

### S3-T03: Panel render and takes
- **Labels:** type: feature, area: panels, priority: p0, size: M, sprint: 3
- **Description:** Render job per panel; take records with seed, backend, model, compiled prompt; select take; retake with new seed.
- **AC:** FR-016 ACs
- **Depends on:** S3-T01, S3-T02

### S3-T04: Consistency QA with auto retakes
- **Labels:** type: feature, area: qa, priority: p0, size: L, sprint: 3
- **Description:** Vision model scores each character against its sheet checklist (1 to 5 with reasons) using the panel and the sheet front view; OCR text detection (RapidOCR, ONNX, CPU) with a confidence threshold; auto retake loop; best-take selection by min character score then OCR clean.
- **AC:** FR-017 ACs; QA results cached; thresholds configurable per project
- **Depends on:** S3-T03

### S3-T05: Panel editing
- **Labels:** type: feature, area: panels, priority: p1, size: M, sprint: 3
- **Description:** Region edit with mask and instruction (backends with `supports_edit`), non-destructive crop and reframe, shot change triggers re-render.
- **AC:** FR-018 ACs; edit disabled with a tooltip when backend lacks support
- **Depends on:** S3-T03

### S3-T06: Lettering placement engine
- **Labels:** type: feature, area: letter, priority: p0, size: XL (split: geometry, placement, tails), sprint: 3
- **Description:** Inputs: panel size, character boxes (vision `locate`, head sub-box when available), dialogue list in order, caption, sfx, style lettering rules. Algorithm: measure text with the real font metrics (fontTools) to size balloons; candidate positions on a grid inside the panel weighted by `balloon_space` hint; cost function penalizing overlap with character boxes (heavy), overlap with other balloons (infinite), distance from speaker head (medium), violation of reading order (heavy), proximity to panel edge (light); greedy placement in reading order with local search refinement; tails as quadratic curves to the speaker head box edge; font downsizing to a minimum before splitting lines; fallback to caption boxes at top when no valid position exists.
- **AC:** FR-019 placement ACs; property tests: no balloon overlaps another, all inside panel, reading order holds
- **Depends on:** S2-T02

### S3-T07: Lettering SVG renderer and fonts
- **Labels:** type: feature, area: letter, priority: p0, size: L, sprint: 3
- **Description:** SVG generation for speech, thought, shout, whisper, caption, SFX per DESIGN lettering spec; open-licensed fonts bundled (Comic Neue for dialogue, Bangers for SFX and shouts, a picture-book friendly rounded face such as Andika or Atkinson Hyperlegible for kids styles; verify licenses, all OFL expected); fonts embedded as base64 `@font-face` in SVG for exact export.
- **AC:** visual goldens for every balloon type; text remains real text in SVG
- **Depends on:** S3-T06

### S3-T08: Strip composition and approval
- **Labels:** type: feature, area: layout, priority: p0, size: M, sprint: 3
- **Description:** Strip SVG (panels in a row, gutters, borders, rounded or square corners per style); approve flow (FR-020) triggering arc update and next suggestions.
- **AC:** FR-020 ACs; strip goldens
- **Depends on:** S3-T07

### S3-T09: Suggestion thumbnails
- **Labels:** type: feature, area: story, priority: p2, size: M, sprint: 3
- **Description:** Low-cost thumbnail per suggestion (fast steps, small size, low priority job); skipped when the backend estimate exceeds a configurable budget; placeholder illustration otherwise.
- **AC:** suggestions never wait on thumbnails; thumbnails fill in as they arrive
- **Depends on:** S3-T03

### S3-T10: Studio: Cast and Story views
- **Labels:** type: feature, area: studio, priority: p0, size: L, sprint: 3
- **Description:** New project wizard (narrative, photos, style, audience, length); Cast view with sheet approval, regenerate per view, originality and attestation states; Story view with bible editor, arc progress, open threads, branches.
- **AC:** e2e: create duck project and approve character with mocks
- **Depends on:** S3-T08

### S3-T11: Studio: Strips view (the core screen)
- **Labels:** type: feature, area: studio, priority: p0, size: XL (split: canvas, inspector, choices, timeline), sprint: 3
- **Description:** Implement the Strips wireframe: plot choice cards with thumbnails and "write my own"; strip canvas with per-panel progress placeholders; panel inspector (shot, angle, action, characters, dialogue editor); takes carousel; QA badges; retake and edit region; timeline with approved strips and branch selector; undo and redo; keyboard shortcuts (J/K panel navigation, R retake, A approve, Cmd/Ctrl+Z undo).
- **AC:** e2e: pick suggestion, render, retake one panel, approve, next suggestions appear
- **Depends on:** S3-T10

### S3-T12: Studio: Lettering editor
- **Labels:** type: feature, area: studio, priority: p0, size: L, sprint: 3
- **Description:** SVG overlay editing: drag balloon, drag tail tip, resize, edit text inline, change balloon type, add caption or SFX, re-run auto placement; changes persisted as events.
- **AC:** `e2e_US008_drag_balloon_persists_after_reload`
- **Depends on:** S3-T11

### S3-T13: Image-side audience check
- **Labels:** type: security, area: safety, priority: p0, size: S, sprint: 3
- **Description:** Vision model suitability verdict per take for the project audience; failing takes hidden and auto-retaken.
- **AC:** FR-028 image ACs
- **Depends on:** S3-T04

### Sprint 3 Gate (hard stop)
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

### S4-T01: Layout templates
- **Labels:** type: feature, area: layout, priority: p0, size: M, sprint: 4
- **Description:** Templates per FR-023 as data (`layout/templates/*.yaml`) in page units with slots and reading order; page sizes (US comic, Letter, A4, square, web); margins, gutter, bleed.
- **AC:** template schema validation; goldens per template
- **Depends on:** Sprint 3

### S4-T02: Auto-paginate
- **Labels:** type: feature, area: layout, priority: p0, size: M, sprint: 4
- **Description:** Strips to pages without splitting strips (unless allowed), filling slots in order; panel-level templates (three-tier, grids, splash) map strip panels into slots with aspect-aware crop and optional re-render at slot aspect ratio.
- **AC:** pagination property tests; never drops a panel
- **Depends on:** S4-T01

### S4-T03: Page SVG composition
- **Labels:** type: feature, area: layout, priority: p0, size: M, sprint: 4
- **Description:** Page SVG with panel art, lettering layers, borders, page captions, page number; bleed area extends art when bleed is on.
- **AC:** goldens for every template and size
- **Depends on:** S4-T02

### S4-T04: Book model and builder
- **Labels:** type: feature, area: book, priority: p0, size: L, sprint: 4
- **Description:** Book entity; page kinds (cover, title, dedication, story, cast, back, custom); chapters from multiple finalized stories; TOC page generation; page numbering rules (no number on cover and title).
- **AC:** FR-024 ACs
- **Depends on:** S4-T03

### S4-T05: Cover generation
- **Labels:** type: feature, area: book, priority: p1, size: M, sprint: 4
- **Description:** Cover art from a cover prompt derived from bible and cast (rendered with references) or chosen from panels; title and author lettering with a cover typography preset; back cover with blurb.
- **AC:** cover renders with mock backend and passes QA with ComfyUI on GPU runner
- **Depends on:** S4-T04

### S4-T06: Studio: Pages view
- **Labels:** type: feature, area: studio, priority: p0, size: L, sprint: 4
- **Description:** Page list, page canvas, layout picker, drag panels between slots, unplaced strips tray, auto-paginate button, page captions.
- **AC:** e2e: change layout, drag panel, undo
- **Depends on:** S4-T03

### S4-T07: Studio: Book view
- **Labels:** type: feature, area: studio, priority: p0, size: L, sprint: 4
- **Description:** Spread view, page strip, add page by kind, reorder by drag, inspector for page fields, cover picker and generator, chapter management.
- **AC:** e2e: build a 6-page book with cover and title page
- **Depends on:** S4-T04, S4-T06

### S4-T08: Pages and book CLI
- **Labels:** type: feature, area: cli, priority: p1, size: S, sprint: 4
- **Description:** `pages`, `book add-page|move|remove|cover|show`.
- **AC:** smoke extended through book creation
- **Depends on:** S4-T04

### Sprint 4 Gate (hard stop)
- [ ] Finalized duck story paginates in all templates without losing panels
- [ ] A book with cover, title, story pages, and back cover is buildable in Studio and CLI
- [ ] Page goldens green
- [ ] Retrospective written, `sprint-4-complete` tagged

---

## Sprint 5: Export

**Milestone:** Sprint 5: Export
**Duration:** 1 week
**Goal:** Every page, story, and book exports as images, PDF, CBZ, long strip, and a web page that matches the Studio exactly.

### S5-T01: Chromium renderer
- **Labels:** type: feature, area: export, priority: p0, size: M, sprint: 5
- **Description:** Playwright Chromium with network disabled (route abort for any non-`data:`/`file:` request), device scale factor computed from target dpi, page SVG to PNG; one browser per export job, pages streamed.
- **AC:** pixel diff between Studio preview capture and export under 0.1 percent
- **Depends on:** Sprint 4

### S5-T02: Image exports
- **Labels:** type: feature, area: export, priority: p0, size: M, sprint: 5
- **Description:** PNG, JPG (quality 92), WebP; 72, 150, 300 dpi; long strip image (strips stacked vertically, max height guard with automatic splitting into parts for social sizes); upscale step for print when art is under target resolution (Real-ESRGAN via ComfyUI workflow when available, else Lanczos with a warning).
- **AC:** dimensions and dpi metadata tests
- **Depends on:** S5-T01

### S5-T03: PDF export
- **Labels:** type: feature, area: export, priority: p0, size: L, sprint: 5
- **Description:** Book HTML (one page per SVG) printed with Chromium `page.pdf` at exact page size (plus bleed for print); post-process with pikepdf: set TrimBox and BleedBox, document metadata (title, author, subject, keywords, producer), optional trim marks layer, page labels; verify fonts embedded and text selectable.
- **AC:** FR-025 PDF ACs; `it_export_pdf_*` tests; opens in Preview, Acrobat, Chrome, iOS Books (manual checklist)
- **Depends on:** S5-T01

### S5-T04: CBZ export
- **Labels:** type: feature, area: export, priority: p2, size: S, sprint: 5
- **Description:** Zip of page images in order with `ComicInfo.xml` metadata.
- **AC:** opens in a CBZ reader (manual) and validates structure
- **Depends on:** S5-T02

### S5-T05: Reader web component
- **Labels:** type: feature, area: reader, priority: p0, size: L, sprint: 5
- **Description:** `@mr-comic-smith/reader`: zero-dependency TypeScript web component with flipbook and scroll modes, keyboard and swipe, spreads on wide screens, reduced motion, alt text, balloons rendered as DOM text over images (positions from lettering JSON) so text is selectable; under 25 KB gzipped.
- **AC:** NFR-007 reader ACs; e2e for both modes; axe zero violations
- **Depends on:** S4-T03

### S5-T06: Web export
- **Labels:** type: feature, area: export, priority: p0, size: M, sprint: 5
- **Description:** Static folder (index.html, reader.js, pages/*.webp, book.json) and single-file mode (everything inlined as base64, size warning above 50 MB); Open Graph tags with cover image; `data-narrate` markup: book title as `h1`, each page's balloons in reading order as paragraphs inside `<article data-narrate>` (visually hidden for screen readers and narration, with `data-narrate-role` for speaker names), so mr-audio-smith can narrate it.
- **AC:** FR-025 web ACs; `it_export_web_*` tests; works from file://
- **Depends on:** S5-T05

### S5-T07: Studio: Export dialog and CLI
- **Labels:** type: feature, area: studio, priority: p0, size: M, sprint: 5
- **Description:** Export dialog per DESIGN; export history list; CLI `export` with all formats.
- **AC:** `e2e_US013_export_book_pdf_from_studio`
- **Depends on:** S5-T03, S5-T06

### Sprint 5 Gate (hard stop)
- [ ] All formats export from Studio and CLI for page, story, and book targets
- [ ] PDF fidelity, embedded fonts, selectable text verified
- [ ] Web export works offline and narrates with mr-audio-smith (manual check recorded)
- [ ] Retrospective written, `sprint-5-complete` tagged

---

## Sprint 6: Release v1.0.0

**Milestone:** Sprint 6: Release v1.0.0
**Duration:** 1 week
**Goal:** Ship v1.0.0 with child mode, auto mode, safety review, evaluations, and docs.

### S6-T01: Child mode
- **Labels:** type: feature, area: studio, priority: p0, size: L, sprint: 6
- **Description:** DESIGN child mode: big picture choices, speech synthesis labels, "Make it!" flow that renders and auto-letters, "Read our comic" opens the reader, long-press exit.
- **AC:** `e2e_US004_child_mode_pick_choice_renders_strip`; 64 px targets verified
- **Depends on:** Sprint 5

### S6-T02: Auto mode end to end
- **Labels:** type: feature, area: story, priority: p1, size: M, sprint: 6
- **Description:** Extend `auto` to render, QA, letter, and approve strips; Studio button "Draft the rest for me" with progress and per-strip review afterwards.
- **AC:** FR-026 ACs; every auto action recorded with actor `auto` and undoable
- **Depends on:** Sprint 5

### S6-T03: Safety review
- **Labels:** type: security, area: safety, priority: p0, size: M, sprint: 6
- **Description:** Walk the Security Guidelines checklist; red-team prompts for originality and audience guards (documented test set); `pip-audit`, `npm audit`, `gitleaks`, bandit (ruff S) in CI; fuzz uploads.
- **AC:** report `docs/SECURITY_REVIEW.md`; zero high or critical findings
- **Depends on:** Sprint 5

### S6-T04: Evaluation round
- **Labels:** type: test, area: qa, priority: p0, size: M, sprint: 6
- **Description:** Run TEST_PLAN model evaluation on three fixture stories with the default local backend and with Gemini; record in `docs/EVALS.md`.
- **AC:** NFR-004 met; human scores at least 4 of 5
- **Depends on:** S6-T02

### S6-T05: Docs site
- **Labels:** type: docs, area: cli, priority: p0, size: L, sprint: 6
- **Description:** README, mkdocs-material site at getcomicsmith.com: quickstart (cloud and local paths), making your first comic (duck tutorial with screenshots), cast and consistency tips, styles, pages and books, exports and printing, safety and originality, backends and GPUs, CLI and API reference, troubleshooting.
- **AC:** quickstart completes in under 15 minutes on a fresh machine with a cloud key
- **Depends on:** S6-T03

### S6-T06: THIRD_PARTY_LICENSES.md
- **Labels:** type: docs, area: packaging, priority: p0, size: S, sprint: 6
- **Description:** Generated from pip-licenses and license-checker, plus sections for model weights (per workflow), fonts (OFL texts included), and bundled assets; CI fails on missing entries.
- **AC:** complete and verified at implementation time
- **Depends on:** S6-T03

### S6-T07: Release pipeline and ship
- **Labels:** type: chore, area: packaging, priority: p0, size: M, sprint: 6
- **Description:** Release workflow per Versioning section; TestPyPI rc; then v1.0.0 to PyPI (with bundled Studio static assets in the wheel) and npm (reader); GitHub Release with SBOM.
- **AC:** `uv tool install mr-comic-smith` installs v1.0.0 and `studio` works offline after install
- **Depends on:** S6-T04, S6-T05, S6-T06

### Sprint 6 Gate (hard stop)
- [ ] Release checklist complete
- [ ] v1.0.0 published with provenance
- [ ] Duck book made with v1.0.0 and exported to PDF and web as the launch validation
- [ ] Retrospective written, `sprint-6-complete` tagged, `v1.0.0` annotated tag on `main`

---
## Versioning, Changelog, and Release

### Semantic versioning

`MAJOR.MINOR.PATCH` following semver 2.0.0.

- **MAJOR:** breaking change to CLI flags or exit codes, Python API, REST, WebSocket events, MCP tools, JSON Schemas (bible, panel, suggestions, layout, book), project database without automatic migration, or reader attributes.
- **MINOR:** new backward-compatible capability (new backend, style preset, layout template, export format, MCP tool, schema field with default).
- **PATCH:** bug fixes, performance, docs, dependency bumps without behavior change.
- Pre-releases `1.1.0-rc.1`. Before 1.0.0 minor bumps may break, and the changelog must say so.
- Project databases carry `schema_version`; every release with a DB change ships an Alembic migration, and opening an older project migrates it after making a backup copy (`project.db.bak-{version}`).
- Prompt templates carry their own versions (included in cache keys); changing a prompt is at least a PATCH and is noted in the changelog under "Changed".

### Version source of truth

`pyproject.toml` `[project].version` is the only human-edited version.

| File | How it stays in sync |
|---|---|
| `comic_smith/__init__.py` | `importlib.metadata.version("mr-comic-smith")` at runtime |
| `web/studio/package.json` | set by `bump-version.sh`, checked |
| `reader/package.json` | set by `bump-version.sh`, checked |
| `integrations/pi/package.json` | set by `bump-version.sh`, checked |
| `charts/mr-comic-smith/Chart.yaml` (`version`, `appVersion`) | set by `bump-version.sh`, checked |
| Studio About dialog | reads `/v1/healthz` version at runtime |

### `scripts/check-versions.sh`

```bash
#!/usr/bin/env bash
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"

CANONICAL=$(python3 - <<'PY'
import tomllib
with open("pyproject.toml", "rb") as f:
    print(tomllib.load(f)["project"]["version"])
PY
)

check() {
  local actual=$1 file=$2
  if [[ "$actual" != "$CANONICAL" ]]; then
    echo "✗ Version mismatch in $file: expected $CANONICAL, got $actual"
    exit 1
  fi
  echo "✓ $file: $CANONICAL"
}

check "$(jq -r '.version' web/studio/package.json)" "web/studio/package.json"
check "$(jq -r '.version' reader/package.json)" "reader/package.json"
check "$(jq -r '.version' integrations/pi/package.json)" "integrations/pi/package.json"
check "$(yq -r '.version' charts/mr-comic-smith/Chart.yaml)" "charts/mr-comic-smith/Chart.yaml (version)"
check "$(yq -r '.appVersion' charts/mr-comic-smith/Chart.yaml)" "charts/mr-comic-smith/Chart.yaml (appVersion)"

echo "── All versions consistent: $CANONICAL ──"
```

Runs in CI on every PR to `staging` and `main`.

### `scripts/bump-version.sh`

```bash
#!/usr/bin/env bash
set -euo pipefail
NEW="${1:?Usage: $0 <new-version>}"
[[ "$NEW" =~ ^[0-9]+\.[0-9]+\.[0-9]+(-rc\.[0-9]+)?$ ]] || { echo "Invalid semver: $NEW"; exit 2; }
cd "$(git rev-parse --show-toplevel)"
uv version "$NEW"   # verify the subcommand for the installed uv version
for f in web/studio/package.json reader/package.json integrations/pi/package.json; do
  tmp=$(mktemp); jq --arg v "$NEW" '.version=$v' "$f" > "$tmp" && mv "$tmp" "$f"
done
yq -i ".version = \"$NEW\" | .appVersion = \"$NEW\"" charts/mr-comic-smith/Chart.yaml
./scripts/check-versions.sh
```

### Version bump process

1. On `chore/release-x.y.z` off `develop`, run `scripts/bump-version.sh x.y.z`.
2. Move `[Unreleased]` entries in `CHANGELOG.md` under `## [x.y.z] - YYYY-MM-DD`; leave an empty `[Unreleased]` with all subsections.
3. Commit `chore(release): x.y.z`; PR to `develop`, then `develop` -> `staging` -> `main` per the release checklist.
4. Annotated tag `vx.y.z` on `main` triggers the release workflow.

### Changelog protocol

Keep a Changelog 1.1.0. `[Unreleased]` always at the top with `Added`, `Changed`, `Deprecated`, `Removed`, `Fixed`, `Security`. Every user-facing PR adds a line in the same PR, written for users ("Added the splash-plus-two page layout"). Prompt template changes are listed under `Changed` with the template name. Compare links at the bottom.

### `scripts/extract-changelog.sh`

```bash
#!/usr/bin/env bash
set -euo pipefail
VERSION="${1:?Usage: $0 <version>}"
awk "/^## \\[${VERSION}\\]/{found=1; next} found && /^## \\[/{exit} found{print}" CHANGELOG.md
```

### Git tagging strategy

- Releases: annotated tags on `main` (`git tag -a v1.0.0 -m "mr-comic-smith 1.0.0"`).
- Sprints: lightweight tags on `staging` (`sprint-{n}-complete`).
- Release candidates: annotated tags on `staging` (`v1.1.0-rc.1`), publishing to TestPyPI and npm `next` only.
- Tags are never moved or deleted after push.

### Release workflow (CI)

```
push tag v*.*.*
   |
   +-> verify: tag == pyproject version; tag on main (or staging for -rc)
   +-> full CI: lint, typecheck, unit, integration, visual, e2e, smoke
   +-> build:
   |     bun run build (web/studio) -> copy into comic_smith/server/static/
   |     uv build -> sdist + wheel (wheel includes Studio static assets and fonts)
   |     bun build reader + pi extension
   |     docker buildx linux/amd64, linux/arm64: cpu and cuda variants
   +-> sign and attest: cosign keyless for images and chart; npm --provenance; PyPI attestations
   +-> SBOM: CycloneDX (Python, npm), attached to release
   +-> publish:
   |     PyPI (trusted publishing)            TestPyPI for -rc
   |     npm @mr-comic-smith/reader, pi-extension (latest | next for -rc)
   |     ghcr.io/serverless-ventures/mr-comic-smith:{version, version-cuda, latest}
   |     Helm chart to GHCR OCI
   +-> GitHub Release: body from extract-changelog.sh, SBOMs, sample exports (duck book PDF and web zip)
   +-> docs: mkdocs gh-deploy
```

### Release checklist

**Pre-release**
- [ ] Milestone issues closed
- [ ] CHANGELOG complete
- [ ] `check-versions.sh` passes after bump
- [ ] THIRD_PARTY_LICENSES.md current (dependencies, models, fonts)
- [ ] Alembic migration tested on a project from the previous release
- [ ] EVALS.md updated, NFR-004 met

**Staging validation**
- [ ] `develop` merged to `staging`; CI including `gpu-integration` green
- [ ] Install rc from TestPyPI in a clean venv; run quickstart with a cloud key
- [ ] Make the fixture duck book with ComfyUI (local) and Gemini (cloud)
- [ ] Export PDF (screen and print) and verify in Preview, Acrobat, Chrome, iOS Books
- [ ] Export web, open in Safari, Chrome, Firefox, iOS Safari, Android Chrome, and from file://
- [ ] Child mode checked on a tablet
- [ ] Docker CPU and CUDA images run `doctor` green

**Release**
- [ ] PR `staging` -> `main` approved and merged
- [ ] Annotated tag pushed
- [ ] Release workflow green; packages visible on PyPI, npm, GHCR
- [ ] GitHub Release body and sample exports correct

### Post-release actions

1. Back-merge `main` into `develop`.
2. Announce: SnackOnAI deep-dive and LinkedIn post (use the SnackOnAI composer and LinkedIn skills), with the duck comic as the hero image.
3. Close the milestone; open the next.
4. Watch issues for 72 hours; P0 bugs get a hotfix branch from `main`.
5. Narrate the release's sample book with mr-audio-smith and add the audio to the docs site.

---

## Coding Standards

### Python (core, server, MCP)

- Python 3.12+; `mypy --strict` clean; no `Any` except at third-party boundaries, immediately wrapped in typed models; no `# type: ignore` without an error code and a reason.
- pydantic v2 for every format, config, and API payload; SQLAlchemy 2 typed mappings for persistence; never pass untyped dicts across module boundaries.
- Services are the only writers; every mutation goes through the event log.
- Errors: typed `ComicSmithError` subclasses with `code`, `stage`, `message`, `hint`, `retryable`; no bare `except Exception` without conversion; `sys.exit` only in `cli.py`.
- No `print()` outside `cli.py`; structured logs with `structlog`.
- Subprocess with argument arrays and timeouts only; `shell=True` forbidden.
- Paths via `pathlib`; all user-derived file names through `safe_slug()`; all writes through `atomic_write()`.
- I/O boundaries injectable (LLM, vision, image backend, clock, filesystem, browser) so unit tests never touch network or GPU.
- Prompt templates live in versioned `.md` files, never inline strings longer than one line.
- Functions under 50 lines; modules under 400 lines.
- Docstrings on public functions (Google style), explaining why.
- Async only at the server and MCP edges and in backends that stream; core services sync with executor bridging.

### TypeScript and React (Studio, reader, Pi extension)

- `strict`, `noUncheckedIndexedAccess`, `exactOptionalPropertyTypes`.
- No `any`, no non-null assertions without a comment, no `console.log` in shipped code.
- React: function components and hooks; Zustand stores per domain (`useProjectStore`, `useStripStore`, `useLetteringStore`); server state through TanStack Query; WebSocket events update query caches, never ad hoc state.
- API types generated from the FastAPI OpenAPI schema (`openapi-typescript`) and committed; CI fails if generation produces a diff.
- Components accessible by default: semantic elements, labels, focus management, visible focus rings.
- SVG lettering components are pure functions of lettering JSON; editing state lives in the store.
- Reader: zero runtime dependencies, Shadow DOM, CSS custom properties.
- ESLint `strict-type-checked`, Prettier, vitest, Playwright.

### General

- No magic numbers: named constants (`DEFAULT_TAKES = 2`, `QA_MIN_SCORE = 4`).
- TODO format `TODO(#123): reason`; TODO without an issue fails lint.
- Conventional Commits:
  ```
  feat:     new feature
  fix:      bug fix
  chore:    maintenance, tooling, dependencies
  docs:     documentation only
  test:     testing infrastructure or coverage
  refactor: code improvement, no behavior change
  perf:     performance improvement
  ci:       GitHub Actions and pipelines
  ```
- No em dashes anywhere (prose, comments, docs, UI copy); enforced by pre-commit. No "game-changer" or "revolutionary" in any copy.
- Every commit passes unit tests (bisectable history).

---

## Security Guidelines

### Uploads and assets
- Sniff types by magic bytes; allow PNG, JPEG, WebP, HEIC only; max 20 MB; reject decompression bombs (Pillow `MAX_IMAGE_PIXELS` set explicitly).
- Strip all EXIF and XMP (location, device) on ingest; store only re-encoded pixels.
- Assets are immutable and served with `Content-Type` from the asset table, `X-Content-Type-Options: nosniff`, and `Content-Disposition` for downloads.
- No user-uploaded SVG accepted anywhere. All SVG is generated by the lettering and layout engines from typed data; text content is XML-escaped.

### Studio and server
- Default bind `127.0.0.1`. LAN mode requires `--access-code` (min 8 chars) and issues a session cookie (`HttpOnly`, `SameSite=Strict`); server mode on non-localhost requires `COMIC_SMITH_SERVER_TOKEN`.
- CSRF: state-changing requests require a per-session header token; Origin checked against the served origin.
- CSP for Studio: `default-src 'self'; img-src 'self' blob: data:; font-src 'self' data:; connect-src 'self' ws: wss:; script-src 'self'; style-src 'self' 'unsafe-inline'; frame-ancestors 'none'`.
- Rate limits on generation endpoints per session.
- Path traversal guards on every file operation; project paths confined to the data directory.

### Export renderer
- Chromium launched per job with network blocked (Playwright route abort for anything not `data:` or the local file root), no extensions, a fresh profile, and a timeout per page.
- Web export reader has no network calls, no eval, no third-party scripts.

### Model and prompt safety
- Story text, user beats, and reference descriptions are untrusted when inserted into prompts: wrapped in delimiters with explicit instructions; outputs constrained by JSON Schema, so injected instructions cannot change structure.
- Originality guard (denylist plus resemblance check), people attestation, and audience guard enforced in core services; no flag disables them in v1.
- Non-commercial model weights require explicit opt-in; the choice is recorded in project metadata and export metadata.

### Dependencies and supply chain
- `uv.lock` and `bun.lockb` committed; CI installs frozen.
- `pip-audit`, `npm audit --audit-level=high`, `gitleaks`, Dependabot.
- Model downloads over HTTPS with pinned revisions and SHA-256 verification; ComfyUI custom nodes required by workflows pinned by commit hash and listed in THIRD_PARTY_LICENSES.
- Docker images run as non-root, read-only root filesystem, signed with cosign.

### Privacy
- Zero telemetry; no analytics in Studio or reader.
- Local-first defaults; cloud backends show a persistent "cloud" badge and a first-use notice listing what is sent (prompts and reference images).
- API keys from environment or OS keyring only; never written to project files, exports, or logs; logs redact keys matching `*key*`, `*token*`, `*secret*`.

---

## Design System

### Principles
Playful but calm. The art is colorful; the interface is quiet so the art leads. Warm paper tones nod to print comics.

### Color tokens

```css
:root {
  /* Surfaces: warm paper */
  --cs-bg:            #FBF8F3;
  --cs-surface:       #FFFFFF;
  --cs-surface-2:     #F3EEE6;
  --cs-border:        #E2D9CC;
  --cs-canvas:        #EDE7DD;   /* behind pages and strips */

  /* Text: ink */
  --cs-text:          #1F1B16;
  --cs-text-muted:    #6B6158;
  --cs-text-inverse:  #FFFFFF;

  /* Accent: comic primary trio, used sparingly */
  --cs-accent:        #2F5BEA;   /* primary actions, focus on approve */
  --cs-accent-hover:  #2448C4;
  --cs-pop-red:       #E5484D;   /* destructive, shout balloons in UI previews */
  --cs-pop-yellow:    #F5C542;   /* highlights, child mode */

  /* Lettering defaults */
  --cs-balloon-fill:  #FFFFFF;
  --cs-balloon-ink:   #111111;
  --cs-caption:       #FFF4C2;

  /* Status */
  --cs-ok:            #2E8B57;
  --cs-warn:          #C77D12;
  --cs-error:         #B3261E;
  --cs-focus:         #1F6FEB;
}
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    --cs-bg: #15130F; --cs-surface: #1E1B16; --cs-surface-2: #27231D; --cs-border: #3A342B;
    --cs-canvas: #0F0D0A; --cs-text: #F2ECE3; --cs-text-muted: #B5AA9C;
    --cs-accent: #6F8DFF; --cs-accent-hover: #8AA2FF;
  }
}
:root[data-theme="dark"] { /* same values as the dark block above */ }
```

Lettering colors never follow the UI theme: balloons stay white with black ink in dark mode because they are part of the artwork.

### Typography
- UI: `Inter` (400, 500, 600); scale 12, 14, 16, 20, 24, 32 px; tabular numerals for counters.
- Lettering: Comic Neue (dialogue), Bangers (SFX, shouts), Atkinson Hyperlegible (kids reading styles and captions for early readers). All bundled and embedded; no web font requests.
- Child mode labels: 24 px, 600 weight.

### Spacing and shape
4 px base: 4, 8, 12, 16, 24, 32, 48, 64. Radius 10 for cards, 6 for inputs, full for avatar chips. Panel borders default 3 px ink with 2 px radius (style can override).

### Signature element
**The ink sweep.** While a panel renders, its slot shows a pencil-sketch placeholder generated from the panel's composition (simple shapes for characters at their positions) with a soft diagonal ink sweep moving across it. When the art arrives, the ink sweep "lands" and the art fades in. It turns waiting into anticipation and doubles as a preview of composition. Disabled under reduced motion (static sketch only).

### Components
Studio: AppHeader, ProjectCard, WizardStep, CharacterCard, SheetGrid, StylePicker, BibleEditor, ArcMeter, ThreadList, BranchSelect, PlotChoiceCard, CustomBeatInput, StripCanvas, PanelSlot (states: empty, sketch, rendering, rendered, flagged, stale, approved), PanelInspector, TakesCarousel, QABadge, LetteringLayer, BalloonHandle, Timeline, PageList, PageCanvas, LayoutPicker, UnplacedTray, SpreadView, BookInspector, ExportDialog, JobToast, UndoBar, KidModeLock.
Reader: ReaderShell, PageView, Spread, ScrollStrip, BalloonText, ModeToggle, PageCounter.

### Anti-patterns (must not appear)
- Text drawn by the image model anywhere in approved art
- Controls overlaid on panel art (except lettering handles during editing)
- Blank spinners without a sketch placeholder or text status
- Modal dialogs for routine actions (use inline panels; modals only for export and destructive confirmations)
- Gradients and glassmorphism in UI chrome
- Emoji in UI chrome (lettering may contain user-typed emoji only if the font supports it; default fonts do not)
- Autoplaying sound in child mode except when a choice is tapped
- Infinite generation without a visible stop button
- Tiny targets: under 32 px in Studio, under 64 px in child mode
- Color as the only status signal (always pair with icon and text)

---

## Environment Model

- **dev:** laptop; mock image backend or cloud key; FakeProvider or small Ollama model; everything on localhost.
- **stage:** GPU box (or GPU runner) with ComfyUI + Ollama; `studio --lan` for team testing; TestPyPI rc builds.
- **prod:** released packages on user machines; optional shared server or Kubernetes.

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
| `COMIC_SMITH_LLM` | `fake` | `ollama:qwen3:14b` | `ollama:qwen3:14b` | provider string |
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

Provide `.env.dev.example`, `.env.stage.example`, `.env.prod.example`.

---

## Dependency Versions

Verify the latest stable versions at implementation time and pin in lock files. Constraints are minimums.

### Python

```toml
[project]
requires-python = ">=3.12,<3.14"
dependencies = [
  "typer>=0.12",
  "rich>=13.7",
  "pydantic>=2.8",
  "pydantic-settings>=2.4",
  "sqlalchemy>=2.0.32",
  "alembic>=1.13",
  "httpx>=0.27",
  "websockets>=12.0",
  "pillow>=10.4",
  "pillow-heif>=0.18",
  "numpy>=1.26",
  "fonttools>=4.53",
  "jsonschema>=4.23",
  "pyyaml>=6.0",
  "structlog>=24.1",
  "keyring>=25.0",
  "fastapi>=0.112",
  "uvicorn[standard]>=0.30",
  "playwright>=1.47",
  "pikepdf>=9.0",
]

[project.optional-dependencies]
comfyui   = []                                 # HTTP/websocket client only; ComfyUI runs separately
gemini    = ["google-genai>=1.0"]
openai    = ["openai>=1.40"]
anthropic = ["anthropic>=0.34"]
ocr       = ["rapidocr-onnxruntime>=1.3"]
mcp       = ["mcp>=1.2"]
dev       = ["pytest>=8.3", "pytest-cov>=5.0", "pytest-asyncio>=0.24", "pytest-timeout>=2.3",
             "hypothesis>=6.100", "respx>=0.21", "syrupy>=4.6", "scikit-image>=0.24",
             "pypdf>=5.0", "ruff>=0.6", "mypy>=1.11", "pre-commit>=3.8", "pip-audit>=2.7",
             "pip-licenses>=5.0", "mkdocs-material>=9.5", "mkdocstrings[python]>=0.25",
             "types-PyYAML"]
```

System: Chromium via `playwright install chromium` (handled by `mr-comic-smith doctor --fix`). For local image generation: ComfyUI (pinned commit) with workflow-required custom nodes and an NVIDIA GPU (24 GB VRAM recommended for the default workflow at full precision; quantized variants documented for smaller cards; verify at implementation time).

### TypeScript / npm

```json
{
  "dependencies": {
    "react": "^18.3",
    "react-dom": "^18.3",
    "react-router-dom": "^6.26",
    "zustand": "^4.5",
    "@tanstack/react-query": "^5.56"
  },
  "devDependencies": {
    "typescript": "^5.6",
    "vite": "^5.4",
    "@vitejs/plugin-react": "^4.3",
    "vitest": "^2.1",
    "@testing-library/react": "^16.0",
    "@playwright/test": "^1.48",
    "@axe-core/playwright": "^4.10",
    "openapi-typescript": "^7.4",
    "eslint": "^9.12",
    "@typescript-eslint/eslint-plugin": "^8.8",
    "prettier": "^3.3",
    "license-checker": "^25.0"
  }
}
```

Pi extension: `@earendil-works/pi-agent-core` and `@sinclair/typebox` (verify current names and versions). Build: `bun>=1.1`.

### Models (verify every entry at implementation time)

| Model | Role | License (expected) | Notes |
|---|---|---|---|
| Qwen-Image-Edit (via ComfyUI) | Default local panel and sheet generation with references | Apache-2.0 | 24 GB VRAM class at bf16; quantized options |
| FLUX.1 Kontext [dev] (via ComfyUI) | Optional reference editing workflow | Non-commercial | Opt-in gate |
| SDXL + IP-Adapter (via ComfyUI) | Fallback for smaller GPUs | OpenRAIL++ / Apache-2.0 | Weaker consistency |
| Gemini image generation (cloud) | Default cloud backend | Google API terms | Multiple reference images |
| OpenAI image generation (cloud) | Second cloud backend | OpenAI API terms | Edit with masks |
| qwen3 14B (Ollama) | Story engine | Apache-2.0 | 0.6B for CI |
| Qwen2.5-VL 7B (Ollama) | Vision describe, locate, QA | Apache-2.0 (check per size) | |
| nomic-embed-text (Ollama) | Suggestion distinctness | Apache-2.0 | |
| RapidOCR (ONNX) | Text-in-image detection | Apache-2.0 | CPU |
| Real-ESRGAN (via ComfyUI) | Print upscaling | BSD-3-Clause | Optional |

### Fonts (bundled)

| Font | Use | License |
|---|---|---|
| Comic Neue | Dialogue | OFL-1.1 |
| Bangers | SFX, shouts, covers | OFL-1.1 |
| Atkinson Hyperlegible | Kids captions and reading styles | OFL-1.1 |
| Inter | UI | OFL-1.1 |

---

## Out of Scope for v1

Create a GitHub issue with the `enhancement` label for each.

| Feature | Rationale |
|---|---|
| Desktop app shell (Tauri) | Studio PWA covers v1; revisit for app-store distribution |
| Hosted SaaS with accounts and billing | Local-first first; conflicts with zero telemetry until designed |
| Built-in narration audio | mr-audio-smith narrates the web export already; deeper integration (audio in reader) is v1.1 |
| Animated panels and motion comics | Belongs with mr-motion-smith |
| Multi-language lettering and translation | Lettering is vector text so this is feasible; needs translation UX and font coverage |
| Real-time collaboration (multi-cursor) | LAN classroom mode gives separate workspaces; co-editing later |
| Print-on-demand ordering and CMYK PDF/X | v1 exports RGB print PDF; CMYK conversion and PDF/X-1a need a color pipeline |
| EPUB fixed-layout export | Web and PDF cover reading; EPUB later |
| LoRA training per character | Reference sheets plus QA meet NFR-004; LoRA as an advanced option later |
| Manga right-to-left reading order | Template and reader support needed |
| Vector inking (SVG art) | Raster art is fine for v1 |
| Mobile native apps | PWA first |
| Style transfer from copyrighted artists | Blocked by design, not deferred |

---

## README Template

```markdown
# mr-comic-smith

*Every story deserves panels.*

Turn a story idea or a photo into a comic strip that grows one beat at a time. At every step
mr-comic-smith suggests what could happen next; you pick, tweak, or write your own. When the story
lands, it stitches the strips into pages and binds the pages into a book you can export as
images, a print-ready PDF, or a web page.

Part of the SnackOnAI smith family: mr-pixel-smith (images), mr-reel-smith (reels),
mr-motion-smith (motion), mr-audio-smith (narration), mr-comic-smith (comics).

## What it does

1. **Cast:** a photo of a duck becomes an original cartoon character sheet that stays on-model
2. **Co-plot:** three choices for what happens next, every strip, until the story ends
3. **Draw:** panels rendered with your cast, checked for consistency, never with garbled text
4. **Letter:** crisp, editable speech balloons, captions, and sound effects
5. **Bind:** pages, cover, and book, exported as PNG, PDF, CBZ, or a web flipbook

## Requirements

- Python 3.12+ and [uv](https://docs.astral.sh/uv/)
- Either a cloud image key (Gemini or OpenAI) or a local NVIDIA GPU with ComfyUI
- Ollama for the story engine (or an Anthropic / OpenAI-compatible key)

## Install

    uv tool install "mr-comic-smith[gemini,ocr]"
    mr-comic-smith doctor --fix

## Quickstart

    mr-comic-smith studio
    # New project -> add a photo -> pick a style -> approve your character -> pick what happens next

Or from the CLI:

    mr-comic-smith new duck --image duck.jpg --narrative "a brave little duck who is afraid of water"
    mr-comic-smith auto duck --until-target
    mr-comic-smith finalize duck
    mr-comic-smith pages duck --layout strip-stack --size us-comic
    mr-comic-smith export duck --target book --format pdf,web

## Fully local

Run ComfyUI and Ollama, then:

    mr-comic-smith models pull qwen-image-edit
    COMIC_SMITH_IMAGE_BACKEND=comfyui mr-comic-smith studio

## Use from your agent

Claude Code, Goose, OpenCode: add the MCP server (`mr-comic-smith mcp`). Pi: install
`@mr-comic-smith/pi-extension`.

## Originality and people

mr-comic-smith makes original characters. It declines famous copyrighted characters and artist
styles, and turns people in photos into cartoon characters only when you confirm you have the
right to use their likeness.

## Build from source

    git clone https://github.com/mohnishbasha/mr-comic-smith && cd mr-comic-smith
    uv sync --all-extras --dev && (cd web/studio && bun install)
    make lint typecheck test

## License

MIT © 2026 Serverless Ventures LLC. Model weights and fonts carry their own licenses; see
THIRD_PARTY_LICENSES.md.
```

---

## Implementation Notes for the Executing Agent

1. Your first action is Step 1: generate all five spec documents. No code before they are committed.
2. Spec documents supersede this prompt once they exist; keep them current through the Spec Change Protocol.
3. Every sprint gate is a hard stop.
4. TDD is mandatory, including for UI components and the lettering engine.
5. The flagship user is a parent making a comic with a five-year-old from a photo of a duck. When a choice is ambiguous, pick what makes that session delightful, safe, and finishable in under an hour.
6. Image models never draw text. If you find yourself letting a model render a balloon, a title, or a sign with words, stop and use the lettering engine.
7. Character consistency is a layered system: approved sheet references, visual DNA text, QA scoring, and retakes. Do not remove a layer to save time.
8. Story engine outputs are JSON validated against schemas. Never parse prose.
9. Image model capabilities, model ids, ComfyUI node names, VRAM needs, and licenses change quickly. Before writing each backend, read its current documentation, record what you found in ARCHITECTURE.md, and adapt the adapter, not the interface.
10. Keep backends behind capability flags. The Studio disables features a backend lacks rather than failing.
11. Safety guards (originality, people attestation, audience) live in core services. Never add a bypass flag.
12. Preview and export share one renderer. If preview and export differ, the bug is in whichever one is not using the shared SVG pipeline.
13. Every mutation is an event. If an action cannot be undone, it needs a confirmation and a reason in the spec.
14. No network or GPU in unit tests: FakeProvider, FakeVisionProvider, MockBackend, respx.
15. Visual goldens use the mock backend and bundled fonts only, so they are deterministic across machines.
16. Do not commit real photos of people, model weights, or generated images of real people. Fixture photos are the maintainer's own and documented.
17. Do not add em dashes anywhere.
18. Update CHANGELOG.md `[Unreleased]` in every user-facing PR.
19. When uncertain, write the open question into the relevant spec doc in your PR instead of guessing silently.
20. End every sprint with the retrospective and the sprint tag.

---
## Appendix A: Integration Architecture Decision

| Decision | Choice | Why | Rejected alternatives |
|---|---|---|---|
| Core language | Python 3.12 | Image backends, vision tooling, PDF post-processing are Python-native | Rust core (would wrap Python model clients anyway) |
| UI | React + TypeScript local web app (PWA) | Rich canvas editing, works on laptop, LAN, and Kubernetes | Tauri desktop (Python sidecar packaging cost, no LAN or classroom mode) |
| CLI runtime | Python + typer via `uv tool` | Same process as services | bun-compiled TS binary (portfolio default; cannot host the Python services) |
| Default image backend (local) | ComfyUI + Qwen-Image-Edit workflow | Reference-conditioned editing with a permissive license; workflows absorb model churn | Direct diffusers pipelines (re-implementing what ComfyUI already maintains) |
| Default image backend (cloud) | Gemini image generation | Strong multi-reference consistency, no GPU needed | Cloud-only design (privacy) |
| Story engine | LLM with JSON Schema output, Ollama default | Local-first, structured outputs | Free prose parsing |
| Consistency | Sheet refs + visual DNA + vision QA + retakes | Layered defense | LoRA per character (slow, deferred) |
| Lettering | Deterministic SVG engine | Crisp, editable, searchable, narratable | Model-drawn text |
| Rendering | One SVG pipeline, Chromium for PNG and PDF | Exact preview-export parity | Separate Pillow and ReportLab paths |
| Storage | SQLite per project + content-addressed assets | Portable project folders | Postgres (overkill for local-first) |
| Harness integration | MCP server for Claude Code, Goose, OpenCode; Pi extension in TS over REST | One server, all MCP harnesses; Pi gets slash commands and progress streaming | Per-harness code |
| Packaging | PyPI wheel with bundled Studio; npm reader; GHCR images; Helm | Covers every tier | Single fat image only |

**Deviation note:** Serverless Ventures defaults are Tauri, Rust, and a bun-compiled TypeScript CLI. mr-comic-smith deviates because its core value lives in Python model clients and an interactive web canvas that must also run on a shared GPU server. Recorded as ADR-001 and ADR-002. Rust and Tauri coding standards are replaced by the Python and TypeScript standards in this prompt.

---

## Appendix B: Repository Structure

```
mr-comic-smith/
├── .agent/skills/
│   ├── run-tests/{SKILL.md,run.sh}
│   ├── check-types/{SKILL.md,run.sh}
│   └── make-fixture-comic/{SKILL.md,run.sh}
├── .github/
│   ├── ISSUE_TEMPLATE/{task.yml,bug.yml,generation-quality.yml}
│   ├── PULL_REQUEST_TEMPLATE.md
│   ├── dependabot.yml
│   └── workflows/{ci.yml,release.yml,docs.yml,gpu-integration.yml,nightly-cloud.yml}
├── comic_smith/
│   ├── __init__.py  api.py  cli.py  config.py  doctor.py  errors.py  events.py
│   ├── db/{models.py,session.py,migrations/}
│   ├── assets/{store.py,images.py}
│   ├── story/{bible.py,arc.py,suggest.py,writer.py,finalize.py,moderation.py,prompts/,schemas/}
│   ├── cast/{reference.py,sheet.py,dna.py,originality.py,styles.py,denylist.yaml,presets/*.yaml}
│   ├── panels/{compiler.py,render.py,qa.py,edit.py}
│   ├── letter/{layout.py,svg.py,fonts.py,fonts/}
│   ├── layout/{templates.py,paginate.py,page.py,templates/*.yaml}
│   ├── book/builder.py
│   ├── export/{chromium.py,images.py,pdf.py,cbz.py,web.py}
│   ├── backends/
│   │   ├── image/{base.py,registry.py,comfyui.py,gemini.py,openai_images.py,mock.py,workflows/}
│   │   ├── llm/{base.py,ollama.py,anthropic.py,openai_compat.py,fake.py}
│   │   └── vision/{base.py,ollama_vl.py,anthropic.py,openai_compat.py,fake.py}
│   ├── jobs/{queue.py,worker.py,progress.py}
│   ├── server/{app.py,routes/,ws.py,auth.py,static/}
│   └── mcp_server/{server.py,tools.py}
├── web/studio/
│   ├── package.json  vite.config.ts  index.html
│   └── src/{app/,api/ (generated types),stores/,views/{Home,Story,Cast,Strips,Pages,Book,Export}/,
│            components/,lettering/,kid/,styles/tokens.css}
├── reader/{package.json,src/{reader.ts,flipbook.ts,scroll.ts,balloons.ts,styles.css},tests/}
├── integrations/
│   ├── pi/{package.json,src/{index.ts,tools.ts,commands.ts},tests/}
│   ├── goose/toolkit.yaml
│   ├── opencode/opencode.json.example
│   └── claude-code/{README.md,skill/SKILL.md}
├── charts/mr-comic-smith/{Chart.yaml,values.yaml,values-k3s-gpu.yaml,templates/}
├── deploy/
│   ├── docker/{Dockerfile.cpu,Dockerfile.cuda,Dockerfile.comfyui}
│   ├── docker-compose.local.yml
│   └── docker-compose.prod.yml
├── docs/
│   ├── PRD.md  ARCHITECTURE.md  DESIGN.md  SPRINT_PLAN.md  TEST_PLAN.md
│   ├── RETROSPECTIVES.md  EVALS.md  SECURITY_REVIEW.md
│   ├── guide/  reference/
├── examples/
│   ├── duck-book/            (project made with mock art + README)
│   └── newsletter-gag-a-day/
├── schemas/{bible,suggestions,panel,character,layout,book}.schema.json
├── scripts/{check-versions.sh,bump-version.sh,extract-changelog.sh,create-issues.py,
│            check-coverage.py,gen-api-types.sh,update-goldens.sh}
├── tests/{unit,integration,smoke,e2e,visual,regression,fixtures}/
├── .coverage-thresholds.toml
├── .env.dev.example  .env.stage.example  .env.prod.example
├── .gitignore  .gitattributes  .editorconfig  .pre-commit-config.yaml
├── AGENTS.md  CLAUDE.md  SKILLS.md  SOUL.md
├── CHANGELOG.md  CONTRIBUTING.md  CODE_OF_CONDUCT.md  SECURITY.md
├── LICENSE  THIRD_PARTY_LICENSES.md  README.md
├── Makefile  mkdocs.yml  pyproject.toml  uv.lock
└── comic-smith.toml.example
```

---

## Appendix C: Core Extraction (not applicable)

mr-comic-smith is library-first from Sprint 1: `comic_smith.api` is the core, and CLI, Studio server routes, MCP, and the Pi extension (over REST) are thin front doors. Enforce with an `import-linter` contract in CI: `comic_smith.cli`, `comic_smith.server`, and `comic_smith.mcp_server` may import only `comic_smith.api`, `comic_smith.errors`, and schema models.

## Appendix D: CLI (delivered in Sprints 1 to 5)

The CLI grows alongside each feature and ships with v1.0.0, so there is no separate CLI sprint. Sprint numbering continues at 7.

---

## Appendix E: Sprint 7: Server and MCP

**Milestone:** Sprint 7: Server and MCP
**Duration:** 1 week
**Goal:** mr-comic-smith runs as a shared service for a classroom or team, and agents can make comics through MCP.

### S7-T01: Server hardening
- **Labels:** type: feature, area: server, priority: p0, size: M, sprint: 7
- **Description:** `serve` mode without Studio static (API only) and with it; bearer token on non-localhost; rate limits; `/readyz` reflecting backend, LLM, vision, Chromium readiness; problem+json everywhere; OpenAPI published at `/v1/openapi.json`.
- **AC:** FR-032 REST ACs; auth tests; readiness flips when a dependency is down
- **Depends on:** Sprint 6

### S7-T02: LAN classroom mode
- **Labels:** type: feature, area: server, priority: p1, size: L, sprint: 7
- **Description:** `studio --lan --access-code`; per-user workspaces (name chosen at join, stored in a workspace table), project sharing within the instance, teacher view listing all projects, GPU job fairness (round-robin by user).
- **AC:** FR-034 ACs; e2e with two browser contexts
- **Depends on:** S7-T01

### S7-T03: MCP server
- **Labels:** type: feature, area: mcp, priority: p0, size: L, sprint: 7
- **Description:** Official Python MCP SDK; stdio and streamable HTTP. Tools:

```
mr_comic_smith_create_project   {name, narrative?, image_paths?, style?, audience?, target_strips?}
                                -> {project_id, characters:[{id, name, needs_approval}], bible_summary}
mr_comic_smith_approve_character{project_id, character_id} -> {approved, originality_ok}
mr_comic_smith_suggest_next     {project_id, branch?} -> {options:[{idx, intent, beat, description}], end_here?}
mr_comic_smith_make_strip       {project_id, pick? | beat?, panels?, render?: true}
                                -> {strip_id, panels:[{idx, image_path, qa}], strip_image_path}
                                (long-running: progress notifications per panel)
mr_comic_smith_edit_panel       {project_id, panel_id, changes} -> {panel_id, image_path}
mr_comic_smith_finalize         {project_id, title?} -> {story_id, continuity_issues, titles}
mr_comic_smith_build_book       {project_id, layout?, size?, cover?: true} -> {book_id, pages}
mr_comic_smith_export           {project_id, target, formats[]} -> {files:[absolute paths]}
mr_comic_smith_list_styles      {} -> [{id, name, description}]
mr_comic_smith_list_backends    {} -> [{id, available, local, references, edit, license}]
mr_comic_smith_status           {} -> doctor report JSON
mr_comic_smith_recommend        {description} -> {style, audience, arc_template, target_strips, reason}
```

  Tool descriptions state the originality and people rules so agents do not attempt to bypass them.
- **AC:** FR-032 MCP ACs; MCP inspector lists valid schemas; integration test drives create -> suggest -> make_strip -> export with mocks over stdio
- **Depends on:** S7-T01

### S7-T04: Remote mode for CLI
- **Labels:** type: feature, area: cli, priority: p2, size: M, sprint: 7
- **Description:** `--server URL --token` makes CLI commands operate against a remote server and download exports.
- **AC:** end-to-end test against a local server process
- **Depends on:** S7-T01

### Sprint 7 Gate (hard stop)
- [ ] A laptop browser uses the Studio on the GPU box in LAN mode with an access code
- [ ] Claude Code makes a 4-panel strip and exports a PDF through MCP
- [ ] Coverage for `server` and `mcp_server` at or above targets
- [ ] Retrospective written, `sprint-7-complete` tagged

---

## Appendix F: Sprint 8: Harness Integrations

**Milestone:** Sprint 8: Harness Integrations
**Duration:** 1 week
**Goal:** "Make a comic about my duck" works from Pi, Goose, OpenCode, and Claude Code.

| Harness | Integration | Why |
|---|---|---|
| Pi | `@mr-comic-smith/pi-extension` on `pi-agent-core` + TypeBox, calling REST | Slash commands, progress via `onUpdate`, context hook with styles and current project |
| Goose | `integrations/goose/toolkit.yaml` launching `mr-comic-smith mcp` | Goose speaks MCP natively |
| OpenCode | `integrations/opencode/opencode.json.example` + README | OpenCode speaks MCP natively, zero code |
| Claude Code | MCP config + `integrations/claude-code/skill/SKILL.md` + repo `CLAUDE.md`/`AGENTS.md` | Native MCP and file context |

### S8-T01: Pi extension
- **Labels:** type: feature, area: harness, priority: p0, size: L, sprint: 8
- **Description:** TypeBox schemas mirroring MCP tools; slash commands `/comic new <name>`, `/comic next` (shows three options, user picks by number), `/comic strip <n|"beat">`, `/comic book`, `/comic export pdf|web`; streams panel progress with `onUpdate`; context extension lists styles and the active project.
- **AC:** vitest unit tests with mocked REST; manual Pi session recorded in TEST_PLAN
- **Depends on:** Sprint 7

### S8-T02: Goose toolkit
- **Labels:** type: feature, area: harness, priority: p1, size: S, sprint: 8
- **AC:** smoke test listing tools from Goose
- **Depends on:** Sprint 7

### S8-T03: OpenCode config
- **Labels:** type: docs, area: harness, priority: p1, size: S, sprint: 8
- **AC:** smoke test listing tools from OpenCode
- **Depends on:** Sprint 7

### S8-T04: Claude Code skill
- **Labels:** type: feature, area: harness, priority: p1, size: M, sprint: 8
- **Description:** Skill teaching the co-plotting loop through MCP: create, approve character (show sheet path to the user first), suggest, ask the user which option, make strip, repeat, finalize, build book, export; rules on originality and people; `claude mcp add` instructions.
- **AC:** scripted session makes a 3-strip story with mocks
- **Depends on:** Sprint 7

### S8-T05: Harness smoke tests in CI
- **Labels:** type: test, area: ci, priority: p2, size: M, sprint: 8
- **Description:** `harness-smoke-tests` job on staging and release: MCP stdio handshake and `tools/list`; Pi extension unit tests.
- **AC:** green on staging
- **Depends on:** S8-T01 to S8-T04

### Sprint 8 Gate (hard stop)
- [ ] Each harness completes a recorded mock session from new project to export
- [ ] Docs cover setup for all four harnesses
- [ ] Retrospective written, `sprint-8-complete` tagged

---

## Appendix G: Sprint 9: Packaging and Deployment

**Milestone:** Sprint 9: Packaging
**Duration:** 1 week
**Goal:** All three deployment tiers documented and tested.

### Tier 1: Local install
- `uv tool install mr-comic-smith[...]` (primary); `pipx` alternative; `doctor --fix` installs Chromium for exports.
- Fully local mode: ComfyUI and Ollama installed by the user (docs link to their official installers); `models pull` fetches workflow models.

### Tier 2: Docker Compose

`deploy/docker-compose.local.yml`

```yaml
services:
  ollama:
    image: ollama/ollama:latest
    volumes: [ollama:/root/.ollama]
    healthcheck: {test: ["CMD", "ollama", "list"], interval: 10s, retries: 30}
    deploy: {resources: {reservations: {devices: [{capabilities: [gpu]}]}}}
  ollama-pull:
    image: ollama/ollama:latest
    depends_on: {ollama: {condition: service_healthy}}
    environment: {OLLAMA_HOST: http://ollama:11434}
    entrypoint: ["/bin/sh", "-c", "ollama pull qwen3:14b && ollama pull qwen2.5vl:7b && ollama pull nomic-embed-text"]
    restart: "no"
  comfyui:
    image: ghcr.io/serverless-ventures/mr-comic-smith-comfyui:${VERSION:-latest}  # pinned ComfyUI + nodes
    volumes: [comfy-models:/opt/ComfyUI/models]
    healthcheck: {test: ["CMD", "curl", "-fsS", "http://localhost:8188/system_stats"], interval: 15s, retries: 40}
    deploy: {resources: {reservations: {devices: [{capabilities: [gpu]}]}}}
  models-pull:
    image: ghcr.io/serverless-ventures/mr-comic-smith:${VERSION:-latest}
    command: ["models", "pull", "qwen-image-edit", "--comfyui-models", "/models"]
    volumes: [comfy-models:/models]
    restart: "no"
  comic-smith:
    image: ghcr.io/serverless-ventures/mr-comic-smith:${VERSION:-latest}
    command: ["studio", "--host", "0.0.0.0", "--lan", "--access-code", "${COMIC_SMITH_ACCESS_CODE:?set an access code}"]
    environment:
      COMIC_SMITH_IMAGE_BACKEND: comfyui
      COMIC_SMITH_COMFYUI_URL: http://comfyui:8188
      COMIC_SMITH_LLM: ollama:qwen3:14b
      COMIC_SMITH_VISION: ollama:qwen2.5vl:7b
      OLLAMA_HOST: http://ollama:11434
    ports: ["7351:7351"]
    volumes: [data:/var/lib/comic-smith]
    depends_on:
      comfyui: {condition: service_healthy}
      models-pull: {condition: service_completed_successfully}
      ollama-pull: {condition: service_completed_successfully}
volumes: {ollama: {}, comfy-models: {}, data: {}}
```

`deploy/docker-compose.prod.yml`: images pinned by digest, resource limits, read-only root filesystems with writable volumes only, internal network for ollama and comfyui (no published ports), comic-smith behind a TLS reverse proxy, restart policies, log rotation, server token and access code from secrets.

### Tier 3: Kubernetes via Helm (`charts/mr-comic-smith`)

- **StatefulSet `comfyui`**: `nvidia.com/gpu: 1` via NVIDIA device plugin; PVC `comfy-models` (100Gi); init container runs `models pull` with checksum verification; readiness on `/system_stats`.
- **StatefulSet `ollama`** (optional): PVC 50Gi; init job pulls story, vision, and embedding models. Alternatively configure an existing OpenAI-compatible vLLM endpoint (on NVIDIA Grace arm64 nodes, `nvcr.io/nvidia/vllm-openai:latest`).
- **StatefulSet `comic-smith`** (single replica in v1, because the SQLite job queue and project databases live on one volume): PVC `data` (50Gi); Secret for server token and access code; liveness `/healthz`, readiness `/readyz`.
- **Deployment `comic-smith-export`** (optional, HPA on CPU): stateless Chromium export workers reading shared storage via ReadWriteMany PVC.
- **Ingress**: TLS, `proxy-read-timeout: 900`, `proxy-body-size: 25m` (uploads), WebSocket upgrade enabled.
- **NetworkPolicy**: only comic-smith pods reach comfyui and ollama.
- `values-k3s-gpu.yaml` for a 2-node k3s + Cilium GPU cluster: comfyui on node A, ollama on node B, comic-smith on either.

### S9-T01: Dockerfiles
- **Labels:** type: chore, area: packaging, priority: p0, size: L, sprint: 9
- **Description:** `Dockerfile.cpu` (python slim, Chromium deps, non-root, Studio bundled), `Dockerfile.cuda` (CUDA runtime base for future in-process backends; same app), `Dockerfile.comfyui` (pinned ComfyUI commit, required custom nodes pinned by commit, no model weights baked in); multi-arch amd64 and arm64.
- **AC:** images run `doctor` green; CPU image under 1.5 GB
- **Depends on:** Sprint 7

### S9-T02: Compose files
- **Labels:** type: chore, area: packaging, priority: p0, size: M, sprint: 9
- **AC:** `docker compose -f deploy/docker-compose.local.yml up` on a GPU host serves the Studio and completes the duck strip
- **Depends on:** S9-T01

### S9-T03: Helm chart
- **Labels:** type: chore, area: packaging, priority: p0, size: L, sprint: 9
- **AC:** `helm lint`, `helm template`, `ct install` in kind with mock backend; manual GPU cluster install documented
- **Depends on:** S9-T01

### S9-T04: Signing and publishing
- **Labels:** type: ci, area: packaging, priority: p1, size: M, sprint: 9
- **AC:** `cosign verify` succeeds for released images and chart
- **Depends on:** S9-T02, S9-T03

### Sprint 9 Gate (hard stop)
- [ ] All three tiers documented and tested
- [ ] Signed images and chart published
- [ ] Retrospective written, `sprint-9-complete` tagged; release v1.1.0

---

## Appendix H: Complete Sprint Overview

| Sprint | Name | Duration | Goal | Release |
|---|---|---|---|---|
| 0 | Scaffold | 1 week | Tooling, CI, DB, events, Studio shell, agent files | |
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

---

## Appendix I: Modularity Principles

1. **The story engine never sees pixels; the image layer never writes story.** They meet only through Panel Specs and character references.
2. **Interfaces are small and capability-flagged.** ImageBackend has three methods; adding a backend is one adapter, one registry entry, contract tests.
3. **Workflows are data.** ComfyUI workflow JSON with named slots lets a new model ship without code changes beyond its manifest.
4. **Styles, layouts, arc templates, denylist, and prompts are data,** versioned and validated.
5. **One renderer.** Preview and export share the SVG pipeline.
6. **Services own mutations; events own history.** No front door writes the database directly.
7. **Front doors are thin.** CLI, Studio routes, MCP, and Pi call `comic_smith.api` only (import-linter).
8. **Safety in core.** Guards sit below every front door.
9. **Optional extras stay optional.** The base install runs the Studio with the mock or a cloud backend; local GPU pieces are separate services.

---

## Appendix J: Test Infrastructure and Maintenance

### Coverage targets

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

### Test types

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

### CI pipeline structure

```yaml
jobs:
  lint-and-typecheck:   # ubuntu, macos, windows: ruff, mypy, eslint, tsc, em dash check, api types diff
  unit-tests:           # 3 OS x py3.12/3.13; vitest
  coverage:             # ubuntu; thresholds; Codecov
  integration-tests:    # ubuntu; SQLite, jobs, Chromium, Ollama tiny, stub ComfyUI
  visual-regression:    # ubuntu; fixed fonts; upload diffs on failure
  e2e-tests:            # ubuntu; Playwright + axe; mock backends
  check-versions:       # PRs to staging and main
  smoke:                # CLI end to end with fakes
  gpu-integration:      # self-hosted [gpu]; ComfyUI workflows; staging/main PRs + dispatch
  nightly-cloud:        # schedule; Gemini/OpenAI live with secrets
  harness-smoke-tests:  # staging and release
```

### Golden maintenance
- `scripts/update-goldens.sh` regenerates goldens with the mock backend; PRs that change goldens must attach before and after images and explain why.
- Goldens render with bundled fonts only and a pinned Chromium version from Playwright.
- Recorded LLM, vision, and ComfyUI fixtures are keyed by prompt template version; changing a template requires re-recording (`make record-fixtures`, needs Ollama) and reviewing diffs.

### Flake policy
Quarantine flaky tests with `@pytest.mark.flaky_quarantine` and a linked issue within 24 hours; fix within the sprint; never more than 5 quarantined.

---

## Appendix K: Agent Repository Files (content specification)

### `AGENTS.md`

```markdown
# mr-comic-smith

Local-first comic studio: narrative or photo -> consistent cast -> co-plotted strips with AI
suggestions -> pages -> book -> PNG/PDF/CBZ/web export.

## Commands
uv sync --all-extras --dev && (cd web/studio && bun install)   # install
make lint                     # ruff + eslint + em dash check
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
```

### `CLAUDE.md`

```markdown
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
```

### `SKILLS.md`

```markdown
# Skills

| Skill | Directory | When to use |
|---|---|---|
| run-tests | .agent/skills/run-tests | After any change; before opening a PR |
| check-types | .agent/skills/check-types | After changing signatures, models, or API routes |
| make-fixture-comic | .agent/skills/make-fixture-comic | To verify the full pipeline end to end with fakes |

## Skill format
Each skill is a directory with SKILL.md (frontmatter: name, description; body: when to use,
steps, expected output) and an executable run.sh that exits non-zero on failure.

## Adding a skill
Create .agent/skills/<name>/{SKILL.md,run.sh}, add a row above, and reference it in AGENTS.md
if it belongs in the PR checklist.

## Pi
Pi loads .agent/skills when the repository is opened; skills must not prompt for input.
```

### `.agent/skills/run-tests/SKILL.md` and `run.sh`

```markdown
---
name: run-tests
description: Run lint, unit tests, visual goldens, and coverage thresholds for mr-comic-smith.
---
Run `./run.sh`. Passes when lint, unit tests, visual goldens, and coverage thresholds pass.
On failure, read the first failing test, fix the cause, re-run.
```

```bash
#!/usr/bin/env bash
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"
make lint
make test
make visual
make coverage
```

### `.agent/skills/check-types/SKILL.md` and `run.sh`

```markdown
---
name: check-types
description: Run mypy --strict, regenerate API types, and run tsc --noEmit.
---
Run `./run.sh`. Fix every error. A diff in generated API types means the OpenAPI schema changed:
commit the regenerated types.
```

```bash
#!/usr/bin/env bash
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"
./scripts/gen-api-types.sh
git diff --exit-code web/studio/src/api/ || { echo "API types changed: commit them"; exit 1; }
make typecheck
```

### `.agent/skills/make-fixture-comic/SKILL.md` and `run.sh`

```markdown
---
name: make-fixture-comic
description: Build the duck fixture comic end to end with fake LLM, fake vision, and mock image backend.
---
Run `./run.sh`. Passes when the PDF has the expected page count and the web export folder
contains index.html with data-narrate markup.
```

```bash
#!/usr/bin/env bash
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"
export COMIC_SMITH_DATA_DIR="$(mktemp -d)"
export COMIC_SMITH_LLM=fake COMIC_SMITH_VISION=fake COMIC_SMITH_IMAGE_BACKEND=mock
uv run mr-comic-smith new duck --image tests/fixtures/images/duck.jpg \
  --narrative "$(cat tests/fixtures/narratives/duck.txt)" --strips 4
uv run mr-comic-smith cast approve duck --all
uv run mr-comic-smith auto duck --until-target
uv run mr-comic-smith finalize duck --title "Puddle"
uv run mr-comic-smith pages duck --layout strip-stack --size us-comic
uv run mr-comic-smith book duck cover --generate
uv run mr-comic-smith export duck --target book --format pdf,web --out "$COMIC_SMITH_DATA_DIR/out"
uv run python -c "import sys,pypdf; r=pypdf.PdfReader(sys.argv[1]); assert len(r.pages)>=3, len(r.pages)" \
  "$COMIC_SMITH_DATA_DIR/out/duck/book.pdf"
grep -q 'data-narrate' "$COMIC_SMITH_DATA_DIR/out/duck/web/index.html"
echo "fixture comic OK"
```

### `SOUL.md`

```markdown
# Soul

## Identity
You are building mr-comic-smith, an open-source studio where a parent and child, a writer, or
a classroom turn an idea or a photo into a comic book, one beat at a time. The first story is
about a little duck who is afraid of water. Build so that story gets finished.

## What this project values
- Finishing: every session should be able to end with a book in hand
- Collaboration between person and model: the model suggests, the person decides
- Consistency and legibility over spectacle
- Local-first and private by default
- Specs first, tests permanent, small interfaces

## Hard constraints
- Never let an image model draw the words of a comic.
- Never generate famous copyrighted characters or imitate a living artist's style.
- Never depict a real person without the user's attestation, and never photorealistically.
- Never produce content unsuitable for the project's audience.
- Never send text or images to a cloud service the user did not choose.
- Never merge code without tests that fail without it.
- Never add telemetry.
- Never use em dashes.

## What good work looks like
A child taps a picture, the duck does the thing, the words are crisp, the duck looks like
the duck, and at the end there is a PDF on the fridge and a link for the grandparents. The
code behind it is typed, tested, documented, and easy to change when models change next month.

## When uncertain
Write the question into the relevant spec doc in your PR. Prefer the choice that is safer,
more reversible, and keeps the user in control of the story.

## Tone
Plain, warm, specific. Explain why.
```

---

*End of build prompt.*
