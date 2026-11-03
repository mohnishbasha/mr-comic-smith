# mr-comic-smith: Product Requirements Document

| Field | Value |
|---|---|
| Version | 1.0 (draft for v1) |
| Date | 2026-11-02 |
| Owner | Serverless Ventures LLC |
| Repo | `mohnishbasha/mr-comic-smith` (MIT licensed) |
| Package | PyPI `mr-comic-smith` (import `comic_smith`, console script `mr-comic-smith`) |
| Related documents | `docs/ARCHITECTURE.md` (structure, data model, contracts), `docs/DESIGN.md` (Studio and reader UI), `docs/SPRINT_PLAN.md`, `docs/TEST_PLAN.md` |

This document is the source of truth for product behavior. Structure and contracts live in `docs/ARCHITECTURE.md`; the Studio and reader visuals live in `docs/DESIGN.md`. Once this file exists, it supersedes `Prompt.md` where the two disagree. Changes follow the Spec Change Protocol.

Tagline: *Every story deserves panels.*

## Contents

1. Overview
2. Personas
3. Core loop
4. User stories
5. Functional requirements
6. Non-functional requirements
7. Success metrics
8. Constraints and assumptions
9. Out of scope for v1
10. Glossary
11. Open questions

---

## 1. Overview

### 1.1 Problem

Image models can draw a single good picture, but a comic is not a single picture. A comic needs:

- the same character to look the same in every panel;
- a story that moves forward with setup and payoff;
- dialogue that is legible;
- panels arranged in a reading order;
- pages that print correctly.

Today a person who wants a comic of "my duck" stitches this together by hand: prompting an image model panel by panel, fighting character drift, pasting speech bubbles in a design tool, and losing the thread of the story along the way. Image models also render text badly, so every bubble drawn by the model comes out garbled. Writing the story is a separate struggle: people often know how a story starts but not where it should go next.

### 1.2 Solution

mr-comic-smith separates the comic into the parts each tool is good at:

1. A language model acts as a co-writer. It keeps a story bible, writes each strip as structured panel specs, and proposes the next plot beat.
2. An image model draws panels with no text in the art, conditioned on an approved character sheet so the cast stays consistent.
3. A deterministic lettering engine renders speech bubbles, captions, and sound effects as vector text.
4. A layout engine stitches strips into pages and pages into a book.
5. Everything is stored locally as a project that can be reopened, branched, and exported.

Finished strips stitch into comic pages, pages bind into a book, and the book exports as a print-ready PDF, high-resolution images, a CBZ archive, or a self-contained web flipbook.

### 1.3 Flagship use case

A parent photographs a rubber duck on the bathtub edge and types "a brave little duck who is afraid of water." mr-comic-smith turns the photo into an original cartoon duck character sheet, writes a first four-panel strip, and offers three choices for what happens next. Parent and child pick, tweak, or write their own direction, strip after strip, until the duck learns to swim. The finished story is stitched into pages, given a cover, exported as a PDF to print, and shared as a web page grandparents can open on a phone.

Every design decision in this document is tested against this use case first.

### 1.4 Second use case

A newsletter writer turns a one-paragraph narrative ("a GPU that refuses to share memory") into a recurring four-panel comic for each issue, keeping the same cast across issues and collecting them into a yearly book.

### 1.5 Product principles

- Local-first: with default configuration no text or image leaves the machine.
- Separation of concerns: the model draws, the engine letters, the layout engine paginates.
- Co-plotted: the model always offers choices; the human always decides.
- Safe by construction: originality, likeness, and audience guards live in core, not only in the UI.
- Reviewable and reversible: every edit is an event that can be undone.

---

## 2. Personas

| ID | Persona | Goal | Technical level |
|---|---|---|---|
| P-1 | **Parent storyteller** (flagship) | Make a comic book with their child from a photo and a story idea | Comfortable installing a tool, prefers a visual UI |
| P-2 | **Young co-creator** (child, with parent) | Pick what happens next, see the duck do it | Non-technical, cannot read long text; needs big buttons and pictures |
| P-3 | **Newsletter or blog writer** | Recurring comic strips with a stable cast, collected into a book | CLI and UI |
| P-4 | **Agent operator** | Ask Claude Code, Pi, Goose, or OpenCode to "make a 4-panel strip about X" and get files back | Uses agent harnesses daily |
| P-5 | **Educator** | Students turn a lesson or a field-trip photo into a short comic | Shared machine or school server |
| P-6 | **Platform team** | Run the studio as a shared service with GPU rendering | Kubernetes, GPUs |

---

## 3. Core loop

The co-plotting loop is the product. Steps 1 to 3 run once per story, step 4 repeats once per strip, and steps 5 to 7 run once per story or book.

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

### 3.1 Step-by-step walkthrough

**Step 1. Seed.**
- User sees: a start screen with a narrative text box (1 to 5,000 characters) and an image drop zone (zero to four images). Narrative only, photo only, or both are all valid.
- System does: validates the input, sniffs image types by magic bytes, re-encodes each image, strips EXIF and XMP, converts HEIC, downscales images over 4096 px on the long edge, and stores each image by SHA-256. A vision model describes each image (subject type, distinguishing features, palette, accessories) and proposes a character name. Person detection runs; if a person is present, the likeness attestation is required (FR-007). Denylist checks run on all text (FR-006).

**Step 2. Cast and style.**
- User sees: the editable description of each reference, an art style picker (picture-book-watercolor, bold-cartoon, manga-ink, newspaper-strip, soft-3d-clay, pixel-art, or custom) with a preview grid, and a character sheet grid (front, side, three-quarter, and expressions neutral, happy, sad, surprised, angry, scared).
- System does: generates an original character sheet in the chosen style from the reference description (and the image when the backend supports conditioning), writes a "visual DNA" paragraph of invariant features, and runs the resemblance check on the sheet. The user approves or regenerates per view. The approved sheet becomes the canonical reference with a stable character id.

**Step 3. Story bible.**
- User sees: an editable bible with working title, logline, premise, audience (all-ages default, kids-5-8, kids-9-12, teen, adult), tone, setting, cast list, themes, arc template (three-act, hero's-journey-lite, problem-try-try-succeed which is the kids default, gag-a-day, mystery), target length (1 to 40 strips), and an arc meter.
- System does: generates the bible with the LLM from the seed, validates it against the Story Bible JSON Schema, versions it on every edit, and seeds the open-thread list.

**Step 4a. Suggest.**
- User sees: three illustrated choice cards (large, picture-first in child mode), labeled continue, twist, and steer. A fourth card "end here" appears when the arc is in its final stage or the target length is reached.
- System does: generates exactly three next-beat options (one-line beat, two-sentence description, target arc stage, characters present, thumbnail sketch prompt), checks pairwise semantic similarity of options (under 0.85 using embeddings, regenerate once otherwise), and renders low-step thumbnails or skips them when the backend is slow.

**Step 4b. Choose.**
- User sees: the chosen card expanded into an editable beat, or an empty "write your own" field.
- System does: normalizes a free-text beat into the structured beat format, shows the normalized result for acceptance, and runs the moderation pass on the beat.

**Step 4c. Write the strip.**
- User sees: a script view with 1 to 6 panels (default 4), each showing shot, angle, setting, action, characters, poses, expressions, dialogue, caption, and sound effects.
- System does: turns the beat into Panel Specs respecting the audience reading level (for kids-5-8: at most 10 words per balloon and 2 balloons per panel), validates against the Panel Spec JSON Schema with one corrective retry, and moderates the script.

**Step 4d. Edit and render.**
- User sees: editable script fields, then panel slots moving through states empty, sketch, rendering, rendered, flagged, stale, approved, with progress and a cancel button; the compiled prompt is viewable.
- System does: compiles each Panel Spec deterministically into a backend request (style tokens, visual DNA, references, composition hints, "no text, no letters, no speech bubbles"), queues render jobs, records per-panel seeds and takes, streams progress events, and retries failures twice. Visual edits mark a panel stale; text-only edits do not.

**Step 4e. Consistency check.**
- User sees: a score badge per panel with reasons, flagged panels, a takes carousel, and tools to retake, change shot, inpaint a masked region, or crop and reframe.
- System does: scores each character in the panel against its sheet checklist from 1 to 5 with a vision model, runs OCR to detect drawn text, auto-retakes panels with any score under 4 or any detected text (default up to 2 retakes, new seed), selects the best take, and checks the image for audience suitability.

**Step 4f. Lettering.**
- User sees: vector balloons (speech, thought, shout, whisper), captions, and sound effects placed over the art, with drag, resize, retype, and balloon-type handles.
- System does: places lettering avoiding character bounding boxes, in reading order, with tails pointing at the speaker's head box, auto-sizing fonts within min and max sizes and never overflowing the panel. Lettering is vector SVG using open-licensed embedded fonts.

**Step 4g. Approve.**
- User sees: an Approve action enabled once all panels are rendered and lettered; the strip joins the timeline and the arc meter advances.
- System does: composes panels into a strip with gutters and borders, freezes the strip (immutable until "unapprove"), tags the arc stage, updates the open-thread list, and triggers the next round of plot suggestions (return to step 4a).

**Step 5. Finalize.**
- User sees: a continuity report (unresolved threads, vanished characters, inconsistent props, tone breaks) with jump-to-strip links, three title suggestions and a one-line blurb, and a choice to fix issues or finalize anyway.
- System does: runs the continuity review on the branch, locks the story as read-only (reopening creates a new version).

**Step 6. Pages.**
- User sees: auto-paginated pages in a chosen layout (strip-stack, classic-three-tier, grid-2x2, grid-3x3, splash-plus-two, vertical-scroll) and page size (US comic 6.625 x 10.25 in, US Letter, A4, square 8.5 x 8.5 in, web). Panels can be dragged between slots.
- System does: paginates respecting strip boundaries by default, generates page SVG, and previews it with the same renderer used for export.

**Step 7. Book and export.**
- User sees: a page list with cover, title page, optional dedication, story pages (chapters), optional "about the characters" page, and back cover; an Export dialog.
- System does: assembles the book manifest, renders exports (PNG, JPG, WebP at 72, 150, or 300 dpi; PDF screen or print; CBZ; single long strip; static web folder or single-file HTML flipbook), and writes metadata including model and font licenses.

---

## 4. User stories

### 4.1 Stories

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

### 4.2 Traceability matrix (US to FR)

Every story maps to at least one functional requirement. Every FR appears in at least one row (verified in section 5.36).

| US | Primary FRs | Supporting FRs |
|---|---|---|
| US-001 | FR-004 | FR-002, FR-003, FR-006, FR-007, FR-008 |
| US-002 | FR-009 | FR-002, FR-010 |
| US-003 | FR-002, FR-005 | FR-001, FR-003 |
| US-004 | FR-011 | FR-029, FR-016 |
| US-005 | FR-012 | FR-011 |
| US-006 | FR-013, FR-014 | FR-028 |
| US-007 | FR-018, FR-014 | FR-016, FR-017 |
| US-008 | FR-019 | FR-015, FR-017 |
| US-009 | FR-011, FR-010 | FR-009 |
| US-010 | FR-022 | FR-010 |
| US-011 | FR-023 | FR-020 |
| US-012 | FR-024 | FR-023 |
| US-013 | FR-025 | FR-023, FR-024 |
| US-014 | FR-025 | FR-020 |
| US-015 | FR-027 | FR-004, FR-008 |
| US-016 | FR-026 | FR-030, FR-011 |
| US-017 | FR-032 | FR-030 |
| US-018 | FR-008 | FR-015 |
| US-019 | FR-028 | FR-009, FR-013 |
| US-020 | FR-021 | FR-020 |
| US-021 | FR-033 | FR-029 |
| US-022 | FR-031 | FR-030 |
| US-023 | FR-025 | none |
| US-024 | FR-034 | FR-029 |

---

## 5. Functional requirements

Acceptance criteria (AC) are checklists. A requirement is done only when every box can be checked by an automated test or a named manual procedure in `docs/TEST_PLAN.md`.

### FR-001 Project lifecycle

Create, open, rename, duplicate, archive, and delete projects. A project is a folder with `project.db` (SQLite) and `assets/`.

Acceptance criteria:
- [ ] A new project creates a folder containing `project.db` and `assets/`.
- [ ] Projects survive app restarts with all data intact.
- [ ] Open, rename, duplicate, archive, and delete are available from the CLI and Studio.
- [ ] Duplicate copies assets by reference (content-addressed), so disk usage grows only by the database.
- [ ] Delete moves the project to the OS trash or a `.trash/` folder and is recoverable.
- [ ] Archived projects are hidden from the default list and can be restored.
- [ ] A project that is locked by another process reports exit code 8 ("project locked or not found") instead of opening twice.
- [ ] Project paths are confined to the data directory (path traversal rejected).

### FR-002 Seed input

Accept narrative text (1 to 5,000 characters), zero to four reference images (PNG, JPG, WebP, HEIC; max 20 MB each), or both.

Acceptance criteria:
- [ ] Narrative shorter than 1 or longer than 5,000 characters is rejected with a plain-language message.
- [ ] Image type is sniffed by magic bytes; only PNG, JPEG, WebP, and HEIC are accepted; other types (including SVG) are rejected.
- [ ] Images larger than 20 MB are rejected; more than four images are rejected.
- [ ] Images are re-encoded, EXIF and XMP are stripped (location removed), and stored by SHA-256.
- [ ] HEIC is converted to a supported working format.
- [ ] Images over 4096 px on the long edge are downscaled.
- [ ] Decompression bombs are rejected (explicit Pillow pixel limit).
- [ ] Narrative only, images only, and both are accepted; empty seed (neither) is rejected.
- [ ] Seed narrative is wrapped as untrusted text whenever inserted into a prompt.

### FR-003 Reference understanding

A vision model describes each reference image: subject type, distinguishing features, colors, accessories, and suggests a character name.

Acceptance criteria:
- [ ] The description is stored as structured JSON with fields subject, palette (hex list), features, and accessories, plus a suggested name.
- [ ] The user can edit every field, and edits are versioned.
- [ ] Output validates against a JSON Schema; invalid output triggers one corrective retry.
- [ ] A person-present flag is produced and passed to FR-007.
- [ ] With the `fake` vision provider the output is deterministic for tests.

### FR-004 Character sheet generation

From a reference description (and the image when the backend supports image conditioning), generate an original character sheet in the chosen style: front, side, three-quarter views and expressions (neutral, happy, sad, surprised, angry, scared).

Acceptance criteria:
- [ ] The sheet is rendered as separate images plus a composed sheet.
- [ ] Three views (front, side, three-quarter) and six expressions (neutral, happy, sad, surprised, angry, scared) are produced.
- [ ] The user approves or regenerates per view; regenerating one view leaves the others unchanged.
- [ ] The approved sheet becomes the canonical reference for all later panels.
- [ ] The character has a stable id and a "visual DNA" text block (one paragraph of invariant features) used in every panel prompt.
- [ ] The sheet is an original cartoon design, not a copy of the photo; photoreal output is not produced.
- [ ] The resemblance check (FR-006) runs on each approved sheet before it becomes canonical.
- [ ] Backends without image conditioning fall back to description-only generation and the UI states this.

### FR-005 Text-only characters

Characters can be created from a description without a photo.

Acceptance criteria:
- [ ] A character can be created from a text description alone via CLI and Studio.
- [ ] The same sheet workflow as FR-004 applies (views, expressions, approval, visual DNA).
- [ ] The same originality guard (FR-006) applies to the description and the result.
- [ ] A project can mix photo-derived and text-only characters.

### FR-006 Originality guard

Block requests that name known copyrighted characters, franchises, or living artists' styles, and flag character sheets that resemble well-known characters.

Acceptance criteria:
- [ ] A denylist check runs on all user text and on compiled prompts; the list is configurable and ships with a starter set.
- [ ] A vision-model similarity question ("does this resemble a well-known copyrighted character?") runs on each approved sheet.
- [ ] On a match, the user is told which rule triggered and is asked to change the design.
- [ ] There is no override flag in v1 (no CLI option, no environment variable, no Studio setting).
- [ ] The guard is enforced in core services, so REST, MCP, and CLI paths cannot bypass it.
- [ ] CLI exits with code 4 (safety blocked) on a block.
- [ ] Style requests that name a living artist are blocked, not deferred.
- [ ] Every block is logged with the rule id, without logging the full user text.

### FR-007 People in reference photos

When a reference image contains a person, require an attestation that the user has the right to use the likeness, and transform the person into a stylized cartoon character rather than a photorealistic depiction.

Acceptance criteria:
- [ ] Person detection runs through the vision model on every reference image.
- [ ] When a person is detected, the attestation is required (CLI `--attest-person`, Studio checkbox) before a character can be created.
- [ ] The attestation (who, when, wording) is stored with the character.
- [ ] Photoreal style presets are disabled for characters derived from people.
- [ ] Requests to depict public figures are declined by the story and prompt layers.
- [ ] Without attestation the CLI exits with code 4.
- [ ] Attestation cannot be pre-set by configuration.

### FR-008 Style presets

Built-in presets: `picture-book-watercolor`, `bold-cartoon`, `manga-ink`, `newspaper-strip`, `soft-3d-clay`, `pixel-art`. Custom presets from text plus up to two style reference images the user owns.

Acceptance criteria:
- [ ] All six built-in preset ids exist and load from validated data files.
- [ ] A preset contains positive style tokens, negative tokens, palette hints, line weight, and backend-specific parameters.
- [ ] A preview grid renders the cast in the chosen style.
- [ ] A custom preset accepts a text description and up to two reference images; a third image is rejected.
- [ ] The user attests that custom style reference images are owned by them; named living artists are blocked (FR-006).
- [ ] The chosen style applies to every panel, sheet, and cover in the project.
- [ ] Changing the style marks rendered panels stale rather than silently re-rendering.

### FR-009 Story bible

The LLM generates and the user edits: working title, logline, premise, audience, tone, setting, cast list, themes, arc template, and target length in strips.

Acceptance criteria:
- [ ] Audience values are exactly: `all-ages` (default), `kids-5-8`, `kids-9-12`, `teen`, `adult`.
- [ ] Arc templates are exactly: `three-act`, `hero's-journey-lite`, `problem-try-try-succeed` (kids default), `gag-a-day` (no arc, standalone strips), `mystery`.
- [ ] Target length is between 1 and 40 strips; values outside the range are rejected.
- [ ] The bible validates against the Story Bible JSON Schema.
- [ ] The bible is versioned on every edit and earlier versions can be viewed.
- [ ] A one-sentence narrative alone is enough to generate a complete bible.
- [ ] The default audience comes from `COMIC_SMITH_DEFAULT_AUDIENCE` (default `all-ages`).

### FR-010 Arc tracking

Every strip is tagged with an arc stage and the bible tracks open threads.

Acceptance criteria:
- [ ] Arc stages are defined per arc template.
- [ ] Each approved strip stores its arc stage.
- [ ] The open threads list updates after each approved strip (threads added, advanced, or resolved).
- [ ] Arc progress (0 to 100 percent) is visible in the UI and `--json` output.
- [ ] Un-approving a strip reverts the thread and progress changes it caused.
- [ ] The `gag-a-day` template shows no arc meter and no open-thread requirement.

### FR-011 Plot suggestions

After the bible and after every approved strip, generate exactly three next-beat options with different intents: continue (natural next step), twist (complication or surprise), and steer (move toward the planned resolution). When the arc is in its final stage or the target length is reached, add a fourth option: end here.

Acceptance criteria:
- [ ] Exactly three options are returned, one per intent (continue, twist, steer); a fourth "end here" option is added only in the final arc stage or at target length.
- [ ] Each option has a one-line beat, a two-sentence description, the arc stage it moves to, the characters who appear, and a thumbnail sketch prompt.
- [ ] Options are pairwise distinct: semantic similarity under 0.85 using embeddings; otherwise regenerate once.
- [ ] Thumbnails render with a fast low-step setting or are skipped when the backend is slow (configurable).
- [ ] Output validates against the Plot Suggestion JSON Schema.
- [ ] The user can keep going after "end here" is offered (declining it is a normal path).
- [ ] CLI `suggest <project> [--branch main] [--json]` returns the same data as the Studio.
- [ ] Text-only suggestions appear within the latency budget in NFR-003.

### FR-012 Custom beats

The user can edit any suggestion or write a free-text beat.

Acceptance criteria:
- [ ] Any suggestion field is editable before acceptance.
- [ ] A free-text beat is normalized into the same structure by the LLM before the strip is written.
- [ ] The user sees the normalized beat and can accept or edit it.
- [ ] Free-text beats pass the originality, people, and audience guards.
- [ ] CLI `strip <project> --beat "free text"` performs the same normalization.

### FR-013 Strip writing

Turn a chosen beat into a strip script: 1 to 6 panels (default 4 for strips, configurable), each panel as a Panel Spec (see ARCHITECTURE).

Acceptance criteria:
- [ ] Panel count is between 1 and 6, default 4, configurable per project and per call (`--panels`).
- [ ] Dialogue respects the audience reading level; for `kids-5-8`: max 10 words per balloon and max 2 balloons per panel.
- [ ] A total-words-per-strip limit applies per audience and is documented in ARCHITECTURE.
  Values (Sprint 1, resolves open question 2): `kids-5-8` 60, `kids-9-12` 110, `all-ages` 130, `teen` 170, `adult` 220 words per strip; per-balloon and per-panel limits as listed in section 11.
- [ ] Every speaking character exists in the cast.
- [ ] Output validates against the Panel Spec JSON Schema, with one corrective retry on validation failure; a second failure surfaces exit code 5 (generation invalid).
- [ ] The script is shown for editing before any image is rendered.
- [ ] Story text and beats are treated as untrusted input inside prompts (delimited, schema-constrained output).

### FR-014 Script editing

The user edits any panel field (shot, angle, setting, action, characters, poses, expressions, dialogue, caption, sound effects) before or after rendering.

Acceptance criteria:
- [ ] Every listed field is editable in the Studio and via CLI/REST.
- [ ] Edits that change visuals (shot, angle, setting, action, characters, poses, expressions) mark the panel stale.
- [ ] Edits that change only text (dialogue, caption, sound effects) do not trigger re-rendering.
- [ ] Edited specs are re-validated against the Panel Spec schema before saving.
- [ ] Each edit is an undoable history event (FR-033).

### FR-015 Prompt compilation

Compile a Panel Spec into a backend-specific image request: style tokens, character visual DNA, reference images, shot and composition, setting, action, continuity notes, and a "no text, no letters, no speech bubbles" constraint.

Acceptance criteria:
- [ ] The compiler is deterministic: the same spec, style, and backend always yield the same request (unit-tested with golden files).
- [ ] The "no text, no letters, no speech bubbles" constraint appears in every compiled request.
- [ ] When a panel has dialogue, composition hints reserve empty space for balloons (for example "headroom at top third").
- [ ] The compiled prompt is viewable in the UI and retrievable by CLI.
- [ ] Reference images respect the selected backend's `max_reference_images`.
- [ ] The denylist (FR-006) and moderation (FR-028) passes run on the compiled prompt.

### FR-016 Panel rendering

Render panels through the selected image backend with reference conditioning.

Acceptance criteria:
- [ ] The per-panel seed is recorded with every take.
- [ ] Takes are stored; earlier takes are never overwritten.
- [ ] Renders run in a job queue with progress events (WebSocket and CLI).
- [ ] Cancel works and leaves no partial assets.
- [ ] Failures are retried twice before the job is marked failed (exit code 6).
- [ ] CLI `render <project> [--strip N] [--panel M] [--takes 2] [--backend comfyui]` works per project, strip, or panel.
- [ ] A kill during render leaves the project consistent; the job resumes or cancels cleanly on restart (NFR-006).
- [ ] Backends are selectable by `COMIC_SMITH_IMAGE_BACKEND` (`mock`, `comfyui`, `gemini`, and others per ARCHITECTURE).

### FR-017 Consistency check

After each render, a vision model scores each character in the panel against its character sheet checklist (colors, features, accessories) from 1 to 5, and an OCR pass detects any text drawn in the image.

Acceptance criteria:
- [ ] Every character in the panel receives a 1 to 5 score with a reason.
- [ ] Panels with any character scoring under `COMIC_SMITH_QA_MIN_SCORE` (default 4), or with detected text, are flagged.
- [ ] Flagged panels are auto-retaken up to `COMIC_SMITH_QA_MAX_RETAKES` times (default 2), each with a new seed.
- [ ] The best take is selected automatically; the user can override.
- [ ] Scores and reasons are shown to the user.
- [ ] After retakes still failing, the panel stays flagged and the user is told why; it is never silently accepted.
- [ ] OCR detection uses a CPU-capable engine so the check runs without a GPU.

### FR-018 Panel editing

Retake, pick among takes, change shot, inpaint a region with a text instruction (when the backend supports editing), crop and reframe.

Acceptance criteria:
- [ ] Retake and take selection work for any single panel without altering other panels.
- [ ] Changing a panel's camera shot re-renders only that panel.
- [ ] Inpaint is limited to the selected mask; pixels outside the mask are unchanged.
- [ ] Inpaint is offered only when the backend reports `supports_edit`; otherwise it is hidden with an explanation.
- [ ] Crop and reframe are non-destructive (stored as parameters, original retained).
- [ ] Inpainted results pass the same consistency, OCR, and audience checks.

### FR-019 Lettering engine

Render balloons (speech, thought, shout, whisper), captions, and sound effects as vector SVG layers over the panel art.

Acceptance criteria:
- [ ] All four balloon types, captions, and sound effects are supported.
- [ ] Automatic placement avoids character bounding boxes (from the vision model).
- [ ] Placement follows reading order (top-left to bottom-right).
- [ ] Tails point at the speaker's head box.
- [ ] Font size is auto-sized within min and max limits, and lettering never overflows the panel.
- [ ] The user can drag, resize, retype, and change balloon type; changes are undoable.
- [ ] Fonts are open-licensed (Comic Neue, Bangers, Atkinson Hyperlegible, Inter) and embedded in exports.
- [ ] All text content is XML-escaped; no user-uploaded SVG is ever accepted.
- [ ] Lettering is deterministic: the same inputs produce byte-identical SVG.
- [ ] CLI `letter <project> --strip N [--auto]` applies automatic lettering.

### FR-020 Strip assembly and approval

Compose panels into a strip with gutters and borders; approve the strip.

Acceptance criteria:
- [ ] Approval requires all panels rendered and lettered; otherwise it is refused with the missing items listed.
- [ ] Approved strips are immutable until "unapprove".
- [ ] Approving triggers the bible thread update (FR-010) and the next plot suggestions (FR-011).
- [ ] Gutters and borders follow the style (default panel border 3 px ink).
- [ ] The strip can be exported as a single image (FR-025).
- [ ] CLI `approve <project> --strip N` works and is recorded in history.

### FR-021 Branching

Create a branch from any approved strip; switch, rename, and delete branches.

Acceptance criteria:
- [ ] A branch can be created from any approved strip.
- [ ] Branches share earlier strips without copying them.
- [ ] Switch, rename, and delete work from CLI (`branch <project> create|switch|list|delete`) and Studio.
- [ ] Deleting a branch never deletes strips shared with another branch.
- [ ] Finalize applies to exactly one branch.
- [ ] The Studio shows the current branch at all times.

### FR-022 Finalize story

Finalize a branch: run a continuity review (unresolved threads, characters who vanish, inconsistent props, tone breaks), suggest three titles and a one-line blurb, then lock the story.

Acceptance criteria:
- [ ] The report covers unresolved threads, vanished characters, inconsistent props, and tone breaks.
- [ ] Each issue links to the strip where it occurs.
- [ ] Exactly three title suggestions and a one-line blurb are produced.
- [ ] The user can fix issues or finalize anyway.
- [ ] Finalized stories are read-only.
- [ ] Reopening a finalized story creates a new version and keeps the old one.
- [ ] CLI `finalize <project> [--branch] [--title "..."]` works.

### FR-023 Page composer

Stitch the strips of a finalized story into pages using layout templates: `strip-stack` (strips stacked vertically, 3 per page default), `classic-three-tier`, `grid-2x2`, `grid-3x3`, `splash-plus-two`, and `vertical-scroll` (web).

Acceptance criteria:
- [ ] All six layout templates exist as validated data.
- [ ] Auto-paginate respects strip boundaries by default (a strip is never split across pages unless the user allows it).
- [ ] The user can drag panels between slots, change the layout per page, and add page-level captions.
- [ ] Page sizes: US comic (6.625 x 10.25 in), US Letter, A4, square 8.5 x 8.5 in, and web.
- [ ] Margins, gutters, and bleed are configurable.
- [ ] Panels not placed on a page appear in an unplaced tray and are never lost.
- [ ] CLI `pages <project> [--layout strip-stack] [--size us-comic]` works.
- [ ] Page SVG is generated by the same renderer used by exports (NFR-009).

### FR-024 Book builder

Build a book page by page: cover (title, subtitle, author, cover art generated from the story or picked from panels), title page, optional dedication page, story pages (from one or more finalized stories, as chapters), optional "about the characters" page from character sheets, back cover.

Acceptance criteria:
- [ ] Add, remove, reorder, and duplicate pages.
- [ ] Page numbers are generated and can be suppressed on cover pages.
- [ ] A table of contents is generated for multi-story books.
- [ ] Book metadata: title, author, year, language.
- [ ] Cover art can be generated or chosen from existing panels.
- [ ] Stories from several projects or branches can be added as chapters.
- [ ] CLI `book <project> add-page|move|remove|cover|show` works.

### FR-025 Exports

Export a page, a story, or a book as: PNG, JPG, WebP (72, 150, 300 dpi); PDF (screen or print; print adds 0.125 in bleed and optional trim marks); CBZ; a single long strip image; a web page (static folder or single self-contained HTML file with a flipbook reader and a vertical scroll mode).

Acceptance criteria:
- [ ] Targets: `page`, `story`, `book`. Formats: `png`, `jpg`, `webp`, `pdf`, `cbz`, `web`, `strip`.
- [ ] Image formats support 72, 150, and 300 dpi (`--dpi`).
- [ ] PDF has screen and print modes (`--print` adds 0.125 in bleed and optional trim marks).
- [ ] Exports reproduce the Studio rendering exactly: same fonts, same balloon positions.
- [ ] PDF text in balloons is selectable and searchable.
- [ ] Web export works offline from `file://`, is responsive, and is keyboard navigable.
- [ ] Web export includes alt text per panel taken from the panel action description.
- [ ] Web export marks reading text with `data-narrate` attributes so mr-audio-smith can narrate it without changes (US-023).
- [ ] Web export makes no network calls and uses no `eval` and no third-party scripts; `--single-file` produces one self-contained HTML file.
- [ ] Export metadata records model and font licenses, and marks non-commercial weights when used.
- [ ] The renderer runs Chromium with network blocked, a fresh profile, and a per-page timeout.
- [ ] Failures exit with code 7 (export failed).
- [ ] The export opens correctly in Preview, Acrobat, Chrome, and iOS Books (PDF), and Chrome, Safari, Firefox (web).

### FR-026 Auto mode

Generate a complete story draft without interaction: the model picks suggestions according to a policy (steer-heavy, balanced, twist-heavy) until the target length, then stops before finalize.

Acceptance criteria:
- [ ] CLI `mr-comic-smith auto <project> [--policy balanced|steer|twist] [--until-target]`.
- [ ] The three policies map to steer-heavy, balanced, and twist-heavy pick weights.
- [ ] Every auto pick is recorded in history with its policy and is reversible with undo.
- [ ] Auto mode stops at the target length and never finalizes on its own.
- [ ] Auto mode passes through all guards (FR-006, FR-007, FR-028); a block stops the run with exit code 4.
- [ ] A partially complete run leaves a valid, resumable project.

### FR-027 Cast and style library

Save characters and styles to a user library and import them into any project.

Acceptance criteria:
- [ ] Characters and styles can be saved to the library from any project.
- [ ] Imported characters keep their sheets and visual DNA.
- [ ] A version is recorded for each library item and for each import.
- [ ] Imported characters keep their stored attestation (FR-007).
- [ ] CLI `library add|list|import` works.
- [ ] Editing an imported character in one project does not alter the library item or other projects.

### FR-028 Content rating guard

Story and image layers respect the audience setting.

Acceptance criteria:
- [ ] System prompts include audience rules for the selected audience value.
- [ ] A moderation pass runs on every generated beat, script, and compiled image prompt.
- [ ] Image outputs are checked by the vision model for audience suitability.
- [ ] Blocked content is explained in plain words, with the audience value cited.
- [ ] The guard is enforced in core; there is no flag to disable it.
- [ ] CLI exits with code 4 on a block.
- [ ] The default audience is `all-ages`.

### FR-029 Studio UI

A local web application served by `mr-comic-smith studio` implementing the core loop, page composer, book builder, and exports (see DESIGN).

Acceptance criteria:
- [ ] Works in current Chrome, Safari, Firefox, and Edge.
- [ ] Installable as a PWA.
- [ ] Binds to `127.0.0.1` by default; default port 7351 (`--port` overrides).
- [ ] Implements all seven core loop steps, the page composer, the book builder, and the export dialog.
- [ ] A child mode shows picture-first choices with 64 px minimum targets (NFR-007).
- [ ] Studio enforces the documented CSP and CSRF protections.
- [ ] No telemetry or analytics (NFR-002).

### FR-030 CLI

Every core action is available from the CLI (see ARCHITECTURE).

Acceptance criteria:
- [ ] Commands exist for: `new`, `cast`, `bible`, `suggest`, `strip`, `render`, `letter`, `approve`, `branch`, `auto`, `finalize`, `pages`, `book`, `export`, `library`, `studio`, `serve`, `mcp`, `doctor`, `gc`.
- [ ] CLI and Studio operate on the same project files.
- [ ] Output supports `--json` where the command returns data.
- [ ] Exit codes are exactly: 0 ok, 2 usage, 3 preflight failed, 4 safety blocked, 5 generation invalid, 6 render failed, 7 export failed, 8 project locked or not found.
- [ ] `new` accepts `--narrative`, repeated `--image`, `--style`, `--audience`, `--strips`, and `--arc`.
- [ ] Every flag, default, and exit code is documented in `--help` and in ARCHITECTURE.
- [ ] `gc <project>` removes unreferenced assets without touching referenced ones.

### FR-031 Doctor

`mr-comic-smith doctor` checks Python, GPU and VRAM, image backend reachability and models, LLM and vision provider, fonts, Chromium for exports, disk space.

Acceptance criteria:
- [ ] All listed checks are performed.
- [ ] Exit 0 when required checks pass; exit 3 (preflight failed) otherwise.
- [ ] Each failure has a fix hint (for example the `models pull` command).
- [ ] `--json` output lists each check with status and hint.
- [ ] Doctor makes no network calls other than to configured local services and, when configured, the selected cloud backend.
- [ ] Doctor reports whether the active image backend's license is non-commercial.

### FR-032 REST server and MCP server

`serve` exposes the REST API; `mcp` exposes MCP tools (Appendix E).

Acceptance criteria:
- [ ] `serve [--host 127.0.0.1] [--port 7350]` exposes the REST API.
- [ ] `mcp [--transport stdio|http]` exposes MCP tools including `mr_comic_smith_list_styles`.
- [ ] Long jobs report progress.
- [ ] A bearer token (`COMIC_SMITH_SERVER_TOKEN`) is required for non-localhost binding.
- [ ] Generation endpoints are rate limited per session.
- [ ] An MCP client can create a strip from a prompt and receive file paths (US-017).
- [ ] REST and MCP paths pass through the same guards as the CLI.

### FR-033 Undo and history

Every mutating action is an event in an append-only project history.

Acceptance criteria:
- [ ] Undo and redo work across script edits, lettering edits, take selection, and layout changes.
- [ ] History survives restart.
- [ ] The history log is append-only; undo appends a compensating event.
- [ ] Undo and redo are available from the Studio (UndoBar) and keyboard.
- [ ] Auto-mode picks (FR-026) appear in history.
- [ ] History events never include secrets (API keys redacted).

### FR-034 Classroom mode

`studio --lan --access-code <code>` serves the Studio on the LAN with per-user workspaces inside one instance.

Acceptance criteria:
- [ ] Access code is required, minimum 8 characters; shorter codes are rejected.
- [ ] A session cookie is issued (`HttpOnly`, `SameSite=Strict`).
- [ ] Users see only their projects unless shared.
- [ ] Per-user workspaces are isolated at the file-path level.
- [ ] All guards (originality, people attestation, audience) apply to every user.
- [ ] The instance does not allow one user to read another user's assets by guessing hashes.

### 5.36 FR coverage check

Every FR from FR-001 to FR-034 appears in at least one row of the section 4.2 matrix, and every US has at least one FR. A test in `docs/TEST_PLAN.md` parses the matrix and fails if any US has an empty FR list or any FR is unreferenced.

---

## 6. Non-functional requirements

| ID | Requirement | Verification method |
|---|---|---|
| NFR-001 | Local-first: with default config (Ollama + ComfyUI), no text or image leaves the machine. Cloud backends are opt-in and shown with a visible "cloud" badge. | Integration test runs the full flagship flow with outbound network blocked (network namespace or firewall rule) and asserts zero connections other than loopback; UI test asserts the cloud badge appears when `gemini` or an OpenAI backend is selected. |
| NFR-002 | Zero telemetry. | Static scan for analytics and beacon code in Studio, reader, and Python; network capture during a full run asserts no unsolicited requests; CI fails on a new third-party host in the Studio bundle. |
| NFR-003 | Responsiveness: plot suggestions (text only) appear within 10 s on a local 14B model; a 4-panel strip renders in under 3 minutes on one 24 GB NVIDIA GPU with the default local backend, and under 90 s on the cloud backends. | Timed benchmark on the reference GPU (qwen3:14b) and on each cloud backend, 10 runs each, p95 must meet the budget; results recorded in `docs/TEST_PLAN.md`. |
| NFR-004 | Consistency: across the flagship test story (8 strips), at least 90 percent of character appearances score 4 or higher on the consistency check after retakes. | Run the 8-strip duck fixture story on three fixture stories; compute the share of scored appearances at 4 or higher from stored QA scores; fail below 90 percent. |
| NFR-005 | Text quality: 0 percent of exported balloons contain model-rendered text; 100 percent of lettering is vector text from the lettering engine. | OCR over all exported art layers (without lettering) finds no text; export inspection asserts every balloon is an SVG text element or embedded-font PDF text; PDF text extraction returns balloon strings. |
| NFR-006 | Reliability: a crash or kill never corrupts a project (SQLite WAL, atomic asset writes); in-flight renders resume or cancel cleanly. | Fault-injection test sends SIGKILL at random points during render, lettering, and approval across 100 iterations; `PRAGMA integrity_check` returns ok and no partial assets exist after restart. |
| NFR-007 | Accessibility: Studio and web reader meet WCAG 2.2 AA; child mode uses 64 px minimum targets and picture-first choices; reader has alt text for every panel. | Automated axe-core run on Studio and reader with zero serious or critical violations; manual keyboard and screen reader pass; layout test measures child mode targets at 64 px or larger; export test asserts every panel image has non-empty alt text. |
| NFR-008 | Portability: macOS Apple Silicon (cloud or MPS-capable backends), Linux x86_64 and arm64 (including NVIDIA Grace systems), Windows 11 via WSL2 or native Python with cloud backends. | CI matrix builds and runs the mock-backend test suite on macOS arm64, Linux x86_64, Linux arm64, and Windows 11; GPU smoke test on one Linux NVIDIA runner. |
| NFR-009 | Export fidelity: exported page images and PDF are pixel-identical to Studio preview at the same resolution (same renderer). | Golden-image test renders the same page through the Studio preview path and the export path at the same dpi and asserts zero pixel difference; PDF rasterized and compared with a defined tolerance of 0. |
| NFR-010 | Print quality: print PDF at 300 dpi effective resolution for panel art; upscale step applied automatically when source art is below target. | Automated check reads image placement sizes in the print PDF and asserts effective dpi of at least 300 for every panel image; fixture with low-resolution art asserts the upscale step ran. |
| NFR-011 | Licensing: every dependency, model weight, and font is recorded with its license; backends whose weights are non-commercial require explicit opt-in and are labeled in exports' metadata. | CI license scan produces `THIRD_PARTY_LICENSES`; test asserts `flux-kontext-dev` is refused unless `COMIC_SMITH_ALLOW_NONCOMMERCIAL=true`; export metadata test asserts a non-commercial label when used. |
| NFR-012 | Safety: originality guard, people attestation, and audience guard are enforced in core, not only in the UI. | API-level and CLI-level tests call core, REST, and MCP directly with blocked inputs and assert exit code 4 or the equivalent error; a code search test asserts no bypass flag or environment variable exists. |

---

## 7. Success metrics

| Metric | Target | How measured |
|---|---|---|
| Flagship completion | A parent and child complete an 8-strip duck story, a 4-page book with cover, and a PDF export in under 60 minutes of wall time on the reference GPU | Timed scripted-plus-manual run recorded in `docs/TEST_PLAN.md` |
| Plot co-writing | Users pick a model suggestion (unedited or lightly edited) for at least 60 percent of beats | Usability tests with at least 5 sessions; count picks versus fully custom beats |
| Consistency | NFR-004 met on three fixture stories | Stored QA scores from fixture runs |
| Export compatibility | 100 percent of exports open correctly in Preview, Acrobat, Chrome, and iOS Books (PDF), and Chrome, Safari, Firefox (web) | Manual matrix before each release |

Usage metrics are gathered only from tests and voluntary feedback, never from telemetry (NFR-002).

---

## 8. Constraints and assumptions

### 8.1 Constraints

- **Language and runtime:** Python 3.12 or 3.13 (`requires-python = ">=3.12,<3.14"`). Dependencies are pinned in lock files (`uv.lock`, `bun.lockb`) and CI installs frozen.
- **Local-first:** default configuration uses Ollama for text and vision and ComfyUI for images, all on localhost. Cloud backends (Gemini, OpenAI, Anthropic) are opt-in and labeled.
- **Zero telemetry:** no analytics in the CLI, Studio, or reader.
- **No bypass flags:** the originality guard, people attestation, and audience guard have no override flag, environment variable, or hidden setting in v1.
- **No model-rendered text:** lettering is always vector text from the lettering engine.
- **No user-uploaded SVG:** all SVG is generated by the lettering and layout engines from typed data.
- **Licensing:** the project is MIT licensed (c) 2026 Serverless Ventures LLC; fonts are open-licensed (OFL-1.1); non-commercial weights require explicit opt-in.
- **Network defaults:** Studio binds to `127.0.0.1`; LAN mode requires an access code of at least 8 characters; server mode on non-localhost requires `COMIC_SMITH_SERVER_TOKEN`.
- **Secrets:** API keys come from environment or OS keyring only, never written to project files, exports, or logs.
- **Distribution:** PyPI `mr-comic-smith`, npm scope `@mr-comic-smith` (reader and Pi extension), container image `ghcr.io/serverless-ventures/mr-comic-smith` (CPU and CUDA variants).

### 8.2 GPU and hardware assumptions

- Reference hardware for performance claims is one 24 GB NVIDIA GPU (the default local workflow targets the 24 GB VRAM class at bf16, with quantized options for less).
- A smaller-GPU fallback (SDXL with IP-Adapter) is available with weaker consistency.
- Apple Silicon is supported via cloud or MPS-capable backends; Windows 11 via WSL2 or native Python with cloud backends.
- The `mock` image backend and `fake` LLM, vision, and embedding providers allow development and CI without a GPU.

### 8.3 Models to verify at implementation time

The licenses and tags below are expected, not guaranteed. Each entry is verified, pinned (revision and SHA-256), and recorded in `THIRD_PARTY_LICENSES` at implementation time.

| Model | Role | Expected license |
|---|---|---|
| Qwen-Image-Edit (via ComfyUI) | Default local panel and sheet generation with references | Apache-2.0 |
| FLUX.1 Kontext [dev] (via ComfyUI) | Optional reference editing workflow, opt-in gate | Non-commercial |
| SDXL + IP-Adapter (via ComfyUI) | Fallback for smaller GPUs | OpenRAIL++ / Apache-2.0 |
| Gemini image generation (cloud) | Default cloud backend | Google API terms |
| OpenAI image generation (cloud) | Second cloud backend | OpenAI API terms |
| qwen3 14B (Ollama) | Story engine (0.6B for CI) | Apache-2.0 |
| Qwen2.5-VL 7B (Ollama) | Vision describe, locate, QA | Apache-2.0 (check per size) |
| nomic-embed-text (Ollama) | Suggestion distinctness | Apache-2.0 |
| RapidOCR (ONNX) | Text-in-image detection | Apache-2.0 |
| Real-ESRGAN (via ComfyUI) | Print upscaling (optional) | BSD-3-Clause |

### 8.4 Assumptions

- Users can install Ollama and ComfyUI, or accept a cloud backend.
- A vision model is capable enough to describe references, locate characters, score consistency, and answer the resemblance question; the QA threshold (`COMIC_SMITH_QA_MIN_SCORE`, default 4) is tunable.
- Exports use Chromium (Playwright) and a PDF toolchain available on the user's machine; `doctor` verifies this.
- v1 exports RGB print PDF only (no CMYK).
- Left-to-right reading order only in v1.
- Environments are `dev`, `stage`, and `prod` (`COMIC_SMITH_ENV`), with data directories `./.comic-smith`, `/var/lib/comic-smith`, and `~/ComicSmith` respectively.
- Defaults: Studio port 7351, server port 7350, default audience `all-ages`, QA minimum score 4, QA maximum retakes 2.

---

## 9. Out of scope for v1

Each item gets a GitHub issue with the `enhancement` label.

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

## 10. Glossary

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
| Arc template | A named story structure (`three-act`, `hero's-journey-lite`, `problem-try-try-succeed`, `gag-a-day`, `mystery`) that defines arc stages |
| Audience | The content and reading level setting (`all-ages`, `kids-5-8`, `kids-9-12`, `teen`, `adult`) |
| Open thread | A story question raised but not yet resolved, tracked in the bible |
| Originality guard | The denylist plus resemblance check that blocks copyrighted characters and living artists' styles |
| Attestation | The user's recorded statement that they have the right to use a person's likeness |
| Backend | A pluggable image generation provider (for example ComfyUI, Gemini) |
| Studio | The local web application for the full workflow |
| Reader | The self-contained web flipbook produced by the web export |

---

## 11. Open questions

1. **Page size ids:** the prompt gives one CLI id (`us-comic`) and names the other sizes in prose. Proposed ids for ARCHITECTURE: `us-letter`, `a4`, `square-8.5`, `web`. Confirm.
2. **Total words per strip by audience:** FR-013 requires a limit per audience, but the prompt only fixes `kids-5-8` balloon limits (10 words, 2 balloons per panel). Limits for the other four audiences need to be set in ARCHITECTURE.
   **Resolved (Sprint 1):** words per balloon / balloons per panel / words per strip (dialogue plus captions): `kids-5-8` 10 / 2 / 60, `kids-9-12` 18 / 3 / 110, `all-ages` 20 / 3 / 130, `teen` 25 / 4 / 170, `adult` 30 / 4 / 220. Constants: `comic_smith/story/writer.py` `LIMITS`.
3. **Rate limits:** the number of generation requests per session per minute is unspecified.
4. **Reference hardware definition:** NFR-003 and the 60-minute flagship target assume "one 24 GB NVIDIA GPU"; the exact reference card and driver should be named in `docs/TEST_PLAN.md`.
5. **Adult audience guard:** what content is allowed for `adult` and `teen` beyond the all-ages baseline, given the moderation pass cannot be disabled, needs an explicit policy table.
6. **Starter denylist ownership:** who curates the starter denylist and how often it is updated.
7. **Library sharing across LAN users (FR-034):** whether shared projects are read-only or editable for classmates.
8. **Model tags:** the Ollama tag for the vision model (`qwen2.5vl:7b`) and embedding model must be verified at implementation time; fallbacks if unavailable are undecided.
