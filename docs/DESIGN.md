# mr-comic-smith: Design Specification

Version: 1.0 (draft for v1). Date: 2026-11-02. Owner: Serverless Ventures LLC.

mr-comic-smith has three visual surfaces:

1. The **Studio**, a local web app (`mr-comic-smith studio`) where comics are made.
2. **Child mode**, a simplified Studio view for young co-creators.
3. The **Reader**, the self-contained web export (flipbook and scroll) that readers open from a file, a server, or a classroom share.

All three share one token set (prefix `--cs-`). Requirements trace to PRD FR-006, FR-007, FR-011, FR-012, FR-017, FR-019, FR-020, FR-023, FR-024, FR-025, FR-029, FR-031, FR-033, FR-034 and the Design System section of the build prompt.

## Contents

1. Design principles
2. Information architecture and navigation
3. Wireframes for every screen
4. Component inventory
5. Design tokens
6. Lettering visual spec
7. Page layout templates
8. Motion and feedback
9. Copy guidelines and microcopy
10. Child mode rules
11. Reader spec
12. Accessibility
13. Anti-patterns
14. Open questions

---

## 1. Design principles

Playful but calm. The art is colorful; the interface is quiet so the art leads. Warm paper tones nod to print comics.

1. **The comic is the interface.** Panels are always the largest thing on screen. Controls sit around them, never over them. The only exception is the lettering handles while a balloon is being edited.
2. **Always a next step.** At every moment the Studio shows exactly one primary action (approve strip, pick a plot, render, export). The primary action is the only filled accent button in the view.
3. **Choices are pictures.** Plot suggestions show a thumbnail and one line before any paragraph. Styles, layouts, and cover art are also picked from pictures, not names.
4. **Undo everything.** No destructive action without undo or a confirmation. Undo and redo are always visible and always work across restarts (FR-033).
5. **Calm while waiting.** Rendering shows progress per panel with a sketch placeholder and a text status, never a blank spinner. Every long job has a visible Stop button.
6. **Design System principle: the interface is quiet, the art leads.** Warm paper surfaces, one accent used sparingly, comic primary trio (blue, red, yellow) reserved for primary action, destructive action, and child-mode highlights. Lettering is artwork and never follows the UI theme.

Supporting rules:

- Status is always icon plus text plus color, never color alone.
- Local-first by default. Anything that leaves the machine is labeled with a persistent cloud badge.
- Plain, warm, specific language. No jargon such as "inference" or "checkpoint" in primary UI.

---

## 2. Information architecture and navigation

### 2.1 Tree

```
Home (projects, library)
 └─ Project
     ├─ Story      (bible, arc progress, open threads, branches)
     ├─ Cast       (characters, sheets, styles)
     ├─ Strips     (timeline + strip editor + plot choices)   <- default view
     ├─ Pages      (page composer)
     ├─ Book       (book builder)
     └─ Export
Global: Settings / Backends, Doctor banner, Kid mode toggle, Undo bar
Classroom: /join (access code + name), then the same tree scoped to the user
```

### 2.2 URL routes

The Studio is a single-page app with history routing. Every view is deep-linkable; the project id is a stable slug plus short hash.

| View | Route | Notes |
|---|---|---|
| Home, projects | `/` | Default landing. Tabs: Projects, Library |
| Home, library | `/library` | Saved characters and styles (FR-027) |
| New project wizard | `/new` | Steps held in query: `/new?step=style` |
| Project root | `/p/:projectId` | Redirects to `/p/:projectId/strips` |
| Story | `/p/:projectId/story` | `?branch=:branchId` |
| Cast | `/p/:projectId/cast` | `/p/:projectId/cast/:characterId` for one character |
| Strips | `/p/:projectId/strips` | `/p/:projectId/strips/:stripId` for a strip; `?panel=3` selects panel |
| Lettering overlay | `/p/:projectId/strips/:stripId?panel=3&letter=1` | Overlay on the Strips view |
| Pages | `/p/:projectId/pages` | `/p/:projectId/pages/:pageNo` |
| Book | `/p/:projectId/book` | `/p/:projectId/book/:pageNo` |
| Export | `/p/:projectId/export` | Opens the Export dialog over the last view |
| Settings / Backends | `/settings` | Also `/settings/backends` |
| Doctor | `/doctor` | Full report; banner links here |
| Classroom join | `/join` | Only when `--lan --access-code` is set |
| Kid mode | any project route with `?kid=1` | Plus a lock state stored locally |
| Reader (export) | `index.html#/page/3` and `#/scroll` | Hash routes, work from `file://` |

### 2.3 Header and navigation

- AppHeader: back to Projects, project title (editable inline), view tabs (Story, Cast, Strips, Pages, Book), Export button, Kid mode toggle, Settings.
- The current tab is marked by underline, bold weight, and `aria-current="page"`.
- Tabs that are not yet available are disabled with a reason on focus or hover (for example "Pages unlock when a story is finalized").

### 2.4 Keyboard shortcuts

A `?` key opens the shortcut sheet. Shortcuts never fire while a text field has focus unless noted.

| Key | Action | Scope |
|---|---|---|
| `J` / `K` | Next / previous panel (or next / previous plot choice when the choice column has focus) | Strips |
| `[` / `]` | Previous / next strip in the timeline | Strips |
| `R` | Retake the selected panel | Strips |
| `A` | Approve strip (when enabled) | Strips |
| `L` | Toggle lettering editor for the selected panel | Strips |
| `1`, `2`, `3`, `4` | Choose plot suggestion 1 to 4 (4 is "end here" when offered) | Strips |
| `W` | Focus "Write my own" | Strips |
| `T` | Cycle takes on the selected panel | Strips |
| `E` | Open Export dialog | Any project view |
| `G` then `S/C/T/P/B` | Go to Story, Cast, Strips, Pages, Book | Any project view |
| `Cmd/Ctrl+Z` | Undo | Global (also in text fields for text only) |
| `Shift+Cmd/Ctrl+Z` | Redo | Global |
| `Cmd/Ctrl+Y` | Redo (Windows alias) | Global |
| `Cmd/Ctrl+K` | Command palette (jump to project, view, action) | Global |
| `Esc` | Close overlay, cancel drag, deselect | Global |
| `Esc` (held 0.5 s) | Cancel running job after confirm | Strips |
| `Arrow keys` | Nudge selected balloon 1 px; `Shift+Arrow` 10 px | Lettering |
| `Alt+Arrow` | Resize selected balloon 1 px | Lettering |
| `Tab` / `Shift+Tab` | Next / previous balloon | Lettering |
| `Enter` | Edit text of selected balloon | Lettering |
| `Delete` | Remove selected balloon (undoable) | Lettering |
| `Space` | Pick up / drop a dragged item (keyboard drag) | Pages, Book, Timeline |
| `?` | Shortcut sheet | Global |

---

## 3. Wireframes for every screen

Conventions: `[ Button ]` is a button; `[x]` is checked; `( )` / `(•)` radio; `▾` select; `░` is skeleton or loading fill; `▓` is progress; `!` marks an error or warning line. States listed under each screen apply to that screen's main region.

### 3.1 Home (projects and library)

```
┌───────────────────────────────────────────────────────────────────────────────┐
│ mr-comic-smith            [Projects] Library            ☁ none   Kid mode  ⚙ │
├───────────────────────────────────────────────────────────────────────────────┤
│ [Doctor banner slot: see 3.12]                                                │
│ Your comics                                              [ + New project ]    │
│ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐           │
│ │ [cover art]  │ │ [cover art]  │ │ [cover art]  │ │ [cover art]  │           │
│ │ Puddle, the  │ │ Moon Garden  │ │ Robot Lunch  │ │ Untitled     │           │
│ │ Duck Who...  │ │ 8 strips     │ │ Finalized    │ │ Draft        │           │
│ │ 4 of ~8      │ │ Edited 2d    │ │ Edited 1w    │ │ Edited 3w    │           │
│ │ [Open]  ⋯    │ │ [Open]  ⋯    │ │ [Open]  ⋯    │ │ [Open]  ⋯    │           │
│ └──────────────┘ └──────────────┘ └──────────────┘ └──────────────┘           │
└───────────────────────────────────────────────────────────────────────────────┘
```

Library tab:

```
│ Characters   [Puddle v2] [Sub v1] [Captain Moss v1]     Styles  [Watercolor]...│
│ Each card: sheet thumbnail, name, version, [Import into project ▾]             │
```

States:

| State | Wireframe note |
|---|---|
| Empty | Centered card: sketch of a blank strip, "Start with a story idea, a photo, or both." and one `[ New project ]` button. Library empty: "Characters you save will live here." |
| Loading | Four skeleton cards (`░`) with the paper-tone sweep; header already usable |
| Error | Inline banner above the grid: "We could not open your projects folder. Check that it still exists, then try again." with `[ Try again ]` and `[ Choose another folder ]`; list stays empty |
| Populated | Grid as above, sorted by last edited; `⋯` menu: Rename, Duplicate, Archive, Delete (moves to trash, undo toast) |
| Disabled backend capability | Cards open normally; a project whose style needs an offline backend shows a small "Needs image backend" tag with a link to Settings |

### 3.2 New project wizard

Five steps in an inline panel (not a modal): Idea, Style, Audience, Length, Check (attestation step appears only when a person is detected).

```
┌───────────────────────────────────────────────────────────────────────────────┐
│ ◂ Projects        New project         1 Idea · 2 Style · 3 Audience · 4 Length│
├───────────────────────────────────────────────────────────────────────────────┤
│ Step 1 of 4: Start with a story idea, a photo, or both.                       │
│ ┌─────────────────────────────────────────┐  ┌────────────────────────────┐   │
│ │ A duck who is scared of water learns... │  │ [ + Add photos (up to 4) ] │   │
│ │                                         │  │ ┌────┐ ┌────┐              │   │
│ │                              142 / 5000 │  │ │ img│ │ img│  remove ×    │   │
│ └─────────────────────────────────────────┘  │ └────┘ └────┘              │   │
│                                              └────────────────────────────┘   │
│ Location data in photos is removed before anything is saved.                  │
│                                                       [ Back ]  [ Next ]      │
└───────────────────────────────────────────────────────────────────────────────┘
```

Step 2, Style (choices are pictures):

```
│ Step 2 of 4: Pick a look.                                                     │
│ ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐ ┌ + Custom ┐│
│ │picture-│ │ bold   │ │ manga  │ │news-   │ │ soft   │ │ pixel  │ │ text +   ││
│ │book    │ │cartoon │ │ ink    │ │paper   │ │ 3d clay│ │ art    │ │ 2 images ││
│ └────────┘ └────────┘ └────────┘ └────────┘ └────────┘ └────────┘ └──────────┘│
│ Preview: your cast in this style (generated after the characters exist).      │
```

Step 3, Audience: five large radio cards (All ages, Kids 5 to 8, Kids 9 to 12, Teen, Adult), each with one line on reading level and a lettering sample. Step 4, Length: slider 1 to 40 strips with the text "About 8 strips, around 10 minutes to read" and an arc template picker with a mini arc diagram (problem-try-try-succeed is the default for kids).

Attestation step (shown only when the vision model detects a person):

```
┌───────────────────────────────────────────────────────────────────────────────┐
│ Step 5: One quick check about the person in your photo                        │
│ ┌────────┐  We will turn this person into a cartoon character.                │
│ │ [photo]│  Photorealistic looks are turned off for this character.           │
│ └────────┘  [ ] I have the right to use this person's likeness.               │
│             (For a child, a parent or guardian should confirm.)               │
│                        [ Use a different photo ]   [ Continue ] (disabled)    │
└───────────────────────────────────────────────────────────────────────────────┘
```

States:

| State | Wireframe note |
|---|---|
| Empty | Text box with placeholder "Start with a story idea, a photo, or both."; Next disabled with reason "Add an idea or a photo" |
| Loading | After Next on step 1: "Looking at your photo..." with sketch silhouette; text still editable |
| Error | Under the field: unsupported file ("That file type is not supported. Use PNG, JPG, WebP, or HEIC."), too big ("That photo is over 20 MB. Try a smaller one."), originality text hit (see 3.4) |
| Populated | All steps filled; final button reads `[ Create project ]` |
| Disabled backend capability | Photo drop zone shows "Photo upload needs a vision model. Open Settings to connect one." and stays disabled; text-only path remains open. Photoreal style card is never offered when a person is detected |

### 3.3 Story view

```
┌──────────────────────────────────────────────────────────────────────────────┐
│ ◂ Projects  Puddle, the Duck...        [Story] Cast Strips Pages Book    ⇪   │
├──────────────────────────────────┬───────────────────────────────────────────┤
│ BIBLE (v7)                       │ ARC  problem-try-try-succeed              │
│ Title    [Puddle, the Duck Who..]│ ▓▓▓▓▓▓░░░░░░  42%                         │
│ Logline  [A shy duck...        ] │ [setup]─[try 1 ●]─[try 2]─[success]─[end] │
│ Audience [Kids 5 to 8 ▾]         │                                           │
│ Tone     [gentle, funny]         │ OPEN THREADS                              │
│ Setting  [a puddle-filled park]  │ • Sub near the drain       (strip 3)      │
│ Themes   [courage] [friends] [+] │ • Red bandana is missing   (strip 3)      │
│ Cast     (o)Puddle (o)Sub  [+]   │                                           │
│ [Version history ▾]              │ BRANCHES  main ▾   [ + Branch from here ] │
│                                  │ main ─●─●─●─●                             │
│                                  │        └─●─●  what-if-raft                │
└──────────────────────────────────┴───────────────────────────────────────────┘
```

| State | Note |
|---|---|
| Empty | Bible generating prompt: "Writing your story bible..." then fields appear; if no LLM: "Story writing needs a language model. Open Settings to connect one." |
| Loading | Field skeletons, arc meter at 0 with text "Planning the arc..." |
| Error | Inline above bible: "The story model did not answer. Your idea is saved. [ Try again ]" |
| Populated | As above; every edit creates a bible version (shown in history) |
| Disabled backend capability | Bible fields editable by hand; `[ Regenerate ]` disabled with tooltip naming the missing capability |
| Finalized | Banner: "This story is finalized and read-only. [ Reopen as new version ]". Finalize flow shows continuity findings, each with `[ Jump to strip ]`, and "Finalize anyway" as a secondary action |

### 3.4 Cast view

Sheet approval (extends the prompt wireframe):

```
┌───────────────────────────────────────────────────────────────────────────────┐
│ Cast:  (o) Puddle ✓   (o) Sub ✓   (o) Captain Moss (draft)   [ + Add ]        │
├───────────────────────────────────────────────────────────────────────────────┤
│ Reference           Sheet (picture-book-watercolor)                           │
│ ┌─────────┐   ┌──────┬──────┬──────┐  ┌───┬───┬───┬───┬───┬───┐               │
│ │ [photo] │   │front │ side │ 3/4  │  │ :)│ :(│ :O│ >:│ :|│ D:│               │
│ └─────────┘   └──────┴──────┴──────┘  └───┴───┴───┴───┴───┴───┘               │
│ Name [Puddle]  Visual DNA: small yellow duck, orange flat beak,               │
│ Palette ■■■■   round body, red bandana, one feather tuft…        [edit]       │
│ Originality ✓ Checked   Person: none                                          │
│ [Regenerate view ▾]                                [ Approve character ]      │
└───────────────────────────────────────────────────────────────────────────────┘
```

Originality blocked state (no override in v1):

```
┌───────────────────────────────────────────────────────────────────────────────┐
│ ! Originality  Blocked                                                        │
│ That character looks a lot like a famous cartoon. Let's give Puddle a look    │
│ that is all yours.                                                            │
│ Rule that triggered: resembles a well-known copyrighted character.            │
│ [ Change the design ]   [ Regenerate with new details ]                       │
│                                       [ Approve character ] (disabled)        │
└───────────────────────────────────────────────────────────────────────────────┘
```

Attestation state (character derived from a person):

```
│ Person-derived character   Likeness confirmed 2026-11-02 by Mo                 │
│ Style locked to cartoon looks. Photoreal presets are off for this character.   │
│ [ View attestation ]                                                           │
│ Not yet confirmed:  [ ] I have the right to use this likeness. [ Confirm ]     │
│ Sheet generation and Approve stay disabled until this is confirmed.           │
```

| State | Note |
|---|---|
| Empty | "Add your first character from a photo or a description." with two buttons |
| Loading | Sheet slots show sketch placeholders with ink sweep, text "Drawing Puddle's front view..." per view |
| Error | Failed view tile shows "This view did not draw. [ Try this view again ]"; other views stay usable |
| Populated | As above |
| Blocked | Originality block above; the same pattern is used for audience-unsuitable images ("That image is not right for ages 5 to 8, so we redrew it.") |
| Disabled backend capability | If the backend does not support image conditioning: note "This image backend cannot use your photo directly. Puddle is drawn from the description instead." and the reference photo is shown as reference only |

### 3.5 Story to Strips: Strips view (core screen)

Base wireframe:

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

Layout rules: the center column is at least 56 percent of viewport width at 1280 px and never narrower than the strip at 640 px. Left and right columns collapse to icon rails below 1100 px; below 760 px the right column becomes a bottom sheet.

#### 3.5.1 Suggestions loading

```
│ WHAT HAPPENS NEXT?                │
│ ┌────────────────────────────┐    │
│ │ ░░░░░░  Continue           │    │
│ │ ░░░░░░  thinking...        │    │
│ └────────────────────────────┘    │
│ ┌────────────────────────────┐    │
│ │ ░░░░░░  Twist              │    │
│ └────────────────────────────┘    │
│ ┌────────────────────────────┐    │
│ │ ░░░░░░  Steer              │    │
│ └────────────────────────────┘    │
│ Thinking of three ideas...  [Stop]│
```

Each card shows its intent label immediately; the thumbnail slot is a sketch placeholder; the one-line beat fills in first, then the thumbnail. If thumbnails are skipped (slow backend), cards show a line-art icon for the intent and the text "No preview, backend is busy."

#### 3.5.2 Plot choice selected and custom beat normalization

```
│ ┌────────────────────────────┐  <- selected, lifted 4 px, accent border + ✓ │
│ │ [thumb] Continue           │                                              │
│ │ Puddle builds a raft       │   other cards at 60 percent                  │
│ └────────────────────────────┘                                              │
│ ✎ Write my own: [Puddle meets a frog who gives swimming lessons_______]     │
│ ┌ We tidied your idea into a beat ─────────────────────────────────────┐    │
│ │ Beat: Puddle meets a swimming-teacher frog.                          │    │
│ │ Moves story to: try-2   Characters: Puddle, Frog (new)               │    │
│ │ [ Use this beat ]   [ Edit ]   [ Keep my words ]                      │    │
│ └──────────────────────────────────────────────────────────────────────┘    │
```

The normalized beat is shown beside the user's text and must be accepted before the strip is written. A new character in the beat shows "Frog is new. Add to cast?" with `[ Add and draw ]`.

#### 3.5.3 End-here card

```
│ ┌────────────────────────────┐                                              │
│ │ [thumb: sunset, all smiles]│                                              │
│ │ End here                   │                                              │
│ │ This feels like a good     │                                              │
│ │ ending. End the story here?│                                              │
│ │ [ End the story ]          │                                              │
│ └────────────────────────────┘  (fourth card, outlined in --cs-pop-yellow)  │
```

Shown when the arc is in its final stage or the target length is reached. Choosing it opens the finalize flow (continuity review on the Story view).

#### 3.5.4 Panel states in the strip

```
 empty          sketch          rendering        rendered        flagged
┌────────┐   ┌────────┐      ┌────────┐       ┌────────┐      ┌────────┐
│  + add │   │ ○  ▢   │      │ ○  ▢ ▒▒│       │ [art]  │      │ [art]  │
│  panel │   │  ╲_    │      │  ╲_▒▒  │       │  "Hi!" │      │  "Hi!" │
│        │   │ (shapes)│     │ ink    │       │        │      │ ! QA 3/5│
└────────┘   └────────┘      │ sweep  │       └────────┘      └────────┘
                             └────────┘
                             Drawing 3 of 4

 stale            approved (strip level)
┌────────┐       ┌───────────────────────────┐
│ [art]  │       │ ✓ Approved  [Unapprove]   │
│ dimmed │       │ panels locked, timeline ✓ │
│ ↻ Out  │       └───────────────────────────┘
│ of date│
└────────┘
```

| Panel state | Visual | Status text (always present) |
|---|---|---|
| empty | dashed border, plus icon | "Empty panel" |
| sketch | pencil placeholder from composition | "Sketch ready" |
| rendering | sketch plus ink sweep | "Drawing panel 3 of 4..." |
| rendered | art with lettering layer | "Drawn" |
| flagged | art with warning corner badge and `!` icon | "Check this one: Sub looked different (3 of 5)" |
| stale | art at 70 percent opacity with `↻` badge | "Out of date: the script changed. [ Redraw ]" |
| approved | solid ink border, check badge on the strip header | "Approved" |

#### 3.5.5 QA flagged

```
│  Panel 2 ▸ ! Needs a look                                                    │
│  QA: Puddle 5/5 ✓   Sub 3/5 !  Missing: red bandana   Text in image: none ✓  │
│  Sub looked a little different, redrawing. (retake 1 of 2)       [ Stop ]    │
│  After retakes:  [ Keep this take ]  [ Retake ]  [ Pick another take ]       │
```

Auto-retakes run first (FR-017). If scores stay below 4 after the limit, the best take is selected and the badge stays with reasons; the strip can still be approved only when the user clicks `Keep this take` on each flagged panel.

#### 3.5.6 Strip states summary

| State | Note |
|---|---|
| Empty (no strips yet) | Center: "Pick what happens first." with three plot cards on the right. Timeline shows `[ + ]` only |
| Loading | Writing: "Writing strip 4..." with four empty sketch slots; rendering: ink sweep per panel |
| Error | Panel tile: "This panel did not draw after 2 tries. [ Try again ] [ Change the shot ]"; the other panels remain |
| Populated | As above; Approve enabled only when all panels are rendered and lettered |
| Disabled backend capability | "Edit region" disabled with tooltip "This image backend cannot edit part of a picture."; Crop stays enabled; thumbnails off shows icon cards |

### 3.6 Lettering editor overlay

Opens over the selected panel inside the strip canvas (inline, not a modal). Handles appear on art during editing, the single allowed exception to "no controls over art".

```
┌───────────────────────────────────────────────────────────────────────────────┐
│ Lettering: panel 2    [Speech▾] [Thought] [Shout] [Whisper] [Caption] [SFX]   │
│ ┌───────────────────────────────────────────────┐   Text                      │
│ │       ╭────────────────────╮                  │   [Jump in! It's warm!   ]  │
│ │      ◻│ Jump in! It's warm!│◻                 │   Speaker [Sub ▾]           │
│ │       ╰──────╲─────────────╯                  │   Size  [auto ▾] 16 px      │
│ │               ╲                               │   Tail  [to Sub ▾]          │
│ │                ◉ (speaker head box)           │   Reading order: 1          │
│ │   [art]       ◻  ◻  corner/edge handles ◻     │   ! Text is 8 words (max 10)│
│ └───────────────────────────────────────────────┘                             │
│ [ Auto-place all ]   [ Reset this balloon ]                  [ Done ]         │
└───────────────────────────────────────────────────────────────────────────────┘
```

| State | Note |
|---|---|
| Empty | Panel without dialogue: "No words in this panel. [ + Add a balloon ] [ + Add a caption ]" |
| Loading | While auto-placement runs: balloons appear faint at default spots, "Placing balloons..." |
| Error | "Could not find a clear spot for this balloon. Drag it where you like." Balloon placed at fallback and outlined as needing review |
| Populated | Handles on selected balloon only; tail has a draggable tip; overflow guard clamps to panel |
| Warning | Over audience word limit shows warning line with count; does not block, but the strip's QA row repeats it |
| Disabled backend capability | Auto-placement needs head boxes from the vision model; if none, "Auto-place" is disabled and balloons start at reading-order defaults |

### 3.7 Pages view

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

Layout picker shows a small diagram per template (see section 7), not only the name.

| State | Note |
|---|---|
| Empty (story not finalized) | "Pages unlock when your story is finalized. [ Go to Story ]" |
| Empty (finalized, no pages) | "Ready to lay out your comic. [ Auto-paginate ]" |
| Loading | Page canvas skeleton; "Laying out pages..." |
| Error | "Strip 5 does not fit this layout. Try grid-2x2 or allow splitting strips. [ Allow split ]" |
| Populated | As above; drag a panel to a slot (keyboard: Space to pick up, arrows to move, Space to drop) |
| Disabled capability | `vertical-scroll` layout disabled for print page sizes with tooltip "Scroll layout is for the web page size." |

### 3.8 Book view (spread)

```
┌───────────────────────────────────────────────────────────────────────────────┐
│                  ┌───────────────────┬───────────────────┐   BOOK INSPECTOR  │
│                  │                   │                   │   Page kind       │
│                  │   page 2          │   page 3          │   [Story page ▾]  │
│                  │   (left)          │   (right)         │   Title [        ]│
│                  │                   │                   │   Subtitle [     ]│
│                  │                   │                   │   Author [       ]│
│                  └───────────────────┴───────────────────┘   Cover art       │
│                       ◂  Spread 2 of 6  ▸                    [thumb][thumb]   │
│ PAGE STRIP: [cover][title][ded.][1][2●][3][4][about][back]   [ + Add page ▾]  │
└───────────────────────────────────────────────────────────────────────────────┘
```

| State | Note |
|---|---|
| Empty | "A book needs a cover and at least one story. [ Start with a cover ]" |
| Loading | Spread skeleton; cover art generation shows ink sweep |
| Error | "Cover art did not draw. You can pick a panel instead. [ Pick from panels ]" |
| Populated | Odd pages on the right, cover alone on the right at the first spread, back cover alone on the left at the last |
| Disabled | "About the characters" page disabled when no approved sheets exist; table of contents appears only with two or more stories |

### 3.9 Export dialog (with progress and done)

One of the two places a modal is allowed.

```
┌─ Export ──────────────────────────────────────────────────────────────┐
│ What     (•) Book   ( ) Story   ( ) Page 2                            │
│ Format   [PNG] [PDF] [Web] [CBZ] [Long strip]      (cards with icons) │
│ Options (PDF)  Quality (•) Screen ( ) Print   DPI [300 ▾]             │
│                [x] Add 0.125 in bleed   [ ] Trim marks                │
│                [x] Single file                                        │
│ Folder  ~/Comics/puddle/exports                       [ Choose ]      │
│ About 18 MB, 24 pages                                                 │
│                                         [ Cancel ]  [ Export ]        │
└───────────────────────────────────────────────────────────────────────┘
```

Progress:

```
│ Exporting your PDF...                                                 │
│ ▓▓▓▓▓▓▓▓░░░░░░░░  page 13 of 24                                       │
│                                                         [ Stop ]      │
```

Done:

```
│ Your PDF is ready. 24 pages, 18 MB.                                   │
│ ~/Comics/puddle/exports/puddle-book.pdf                               │
│              [ Copy path ]  [ Open folder ]  [ Done ]                 │
```

| State | Note |
|---|---|
| Empty | Nothing to export: "Finish a strip first, then export." and Export disabled |
| Loading | Estimating size shows `░░` |
| Error | "The export stopped at page 13: not enough disk space (needs 420 MB). [ Choose another folder ] [ Try again ]" |
| Populated | As above |
| Disabled capability | PDF disabled with "PDF export needs Chromium. Run doctor to install it. [ Open Doctor ]"; print options disabled for Screen quality; Web is always available |

After export, a JobToast confirms in the corner if the dialog was closed.

### 3.10 Settings and Backends panel

```
┌───────────────────────────────────────────────────────────────────────────────┐
│ Settings   [Backends] Appearance Fonts Library Classroom                      │
├───────────────────────────────────────────────────────────────────────────────┤
│ IMAGE   ( ) Mock         (•) ComfyUI (this computer) ●ok    [Test]            │
│         ( ) Cloud image  ☁ Cloud                            [Test]            │
│ STORY   (•) Ollama (this computer) ●ok      ( ) Cloud model ☁ Cloud           │
│ VISION  (•) Ollama vision ●ok                                                 │
│ Capabilities:  image conditioning ✓  inpainting ✓  fast thumbnails ✗          │
│ API keys are read from your environment or keyring, never saved in projects.  │
│ Key status:  OPENAI_API_KEY  found in environment (value hidden)              │
└───────────────────────────────────────────────────────────────────────────────┘
```

Cloud badge: a persistent `☁ Cloud` pill (text plus icon) appears in AppHeader on every screen whenever any active backend is cloud. Hover or focus shows which stages are cloud.

First-use cloud notice (inline panel at the moment a cloud backend is first selected, blocks the switch until accepted):

```
┌─ Before you use a cloud service ──────────────────────────────────────┐
│ If you turn this on, these things leave your computer:                │
│  • your story text and prompts                                        │
│  • your reference images (photos have location data removed first)    │
│ Nothing is sent until you press Use cloud. You can switch back any    │
│ time. Your API key stays on this computer.                            │
│                      [ Keep it on my computer ]   [ Use cloud ]       │
└───────────────────────────────────────────────────────────────────────┘
```

| State | Note |
|---|---|
| Empty | No backend configured: "No image backend yet. Use the mock backend to try the Studio, or connect ComfyUI." |
| Loading | Test button shows "Checking..." with status text |
| Error | Row: "ComfyUI did not answer at 127.0.0.1:8188. [ Run doctor ]" |
| Populated | As above |
| Disabled capability | Capability rows list each feature as available or unavailable with the affected UI named, for example "Inpainting unavailable: Edit region is hidden" |

### 3.11 Doctor and preflight banner

Banner at top of every Studio view when a required check fails; collapsible when only advisories remain.

```
┌───────────────────────────────────────────────────────────────────────────────┐
│ ! Setup needs attention: no image backend is reachable.   [ See details ] [×] │
└───────────────────────────────────────────────────────────────────────────────┘
```

Full report at `/doctor`:

```
│ Python 3.12             ✓ ok                                                  │
│ GPU / VRAM              ✓ 24 GB                                               │
│ Image backend           ! ComfyUI not reachable   Fix: start ComfyUI, then Retest│
│ Story model             ✓ ollama llama3                                       │
│ Vision model            ✓ ollama llava                                        │
│ Fonts                   ✓ Comic Neue, Bangers, Atkinson Hyperlegible          │
│ Chromium (PDF export)   ! missing   Fix: run `mr-comic-smith doctor --fix`    │
│ Disk space              ✓ 120 GB free                                         │
│                                                          [ Run checks again ] │
```

| State | Note |
|---|---|
| Empty | Not applicable (always has checks); before first run: "Checking your setup..." |
| Loading | Each row shows `░ checking` |
| Error | Row-level failures with a fix hint each (FR-031); required failures use the banner, optional ones use a quiet note |
| Populated | All green: banner is hidden; report shows "All set." |
| Disabled capability | Features that depend on a failed check show the same reason as a tooltip, and link back to this report |

### 3.12 Classroom join screen

Shown at `/join` when the Studio runs with `--lan --access-code`.

```
┌───────────────────────────────────────────┐
│          mr-comic-smith Classroom         │
│                                           │
│ Class code   [ ______ ]                   │
│ Your name    [ ______________ ]           │
│                                           │
│               [ Join ]                    │
│ Your comics are private to you unless you │
│ share them.                               │
└───────────────────────────────────────────┘
```

| State | Note |
|---|---|
| Empty | Join disabled until both fields have text |
| Loading | Button reads "Joining..." |
| Error | "That code did not match. Check with your teacher and try again." After repeated tries: "Too many tries. Wait a minute, then try again." |
| Populated | After joining, the Home view shows only the learner's own projects plus those shared with them; name appears in the header |
| Disabled | If the Studio is not in classroom mode, `/join` shows "This Studio is not set up for a class." and a link to Home |

### 3.13 Child mode screens

Child mode screens use 64 px minimum targets, 24 px labels, and the yellow accent. See section 10 for rules.

**Child home / strip screen:**

```
┌───────────────────────────────────────────────────────────────────────────────┐
│ (🔒 lock)                     Our comic: Puddle                  [ Read our comic ]│
├───────────────────────────────────────────────────────────────────────────────┤
│  ┌─────────────────────────────────────────────────────────────────────────┐  │
│  │              the current strip, shown large                             │  │
│  └─────────────────────────────────────────────────────────────────────────┘  │
│  What happens next?                                                           │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐                                     │
│  │ 240 px   │  │ 240 px   │  │ 240 px   │                                     │
│  │ picture  │  │ picture  │  │ picture  │                                     │
│  ├──────────┤  ├──────────┤  ├──────────┤                                     │
│  │Build raft│  │Frog says │  │Find the  │                                     │
│  │          │  │ hello    │  │ big pond │                                     │
│  └──────────┘  └──────────┘  └──────────┘                                     │
│                         [   Make it!   ]                                      │
└───────────────────────────────────────────────────────────────────────────────┘
```

(The lock icon is a vector icon in the product; the sketch above uses a glyph only for the document. No emoji ships in UI chrome.)

| Child state | Note |
|---|---|
| Empty | A grown-up has not started a story: big sketch picture and "Ask a grown-up to start our comic." |
| Loading choices | Three sketch cards with ink sweep and "Thinking of ideas..." read aloud only when tapped |
| Picked | Chosen card lifts and gets a thick yellow border; others fade to 60 percent; `Make it!` becomes active |
| Rendering | Large strip with sketch panels; "Drawing panel 3 of 4..." in 24 px text |
| Error | Friendly, no codes: "Oops, the picture did not finish. Let's try again." with one big `Try again` button; a grown-up sees details after the lock is opened |
| Backend unavailable | "The drawing helper is asleep. Ask a grown-up to wake it up." |
| End of story | "The end! Want to read our comic?" with one big `Read our comic` button |

**Lock exit:** pressing and holding the lock icon for 2 seconds shows a ring filling around it; on completion a grown-up gate (see section 10) appears.

### 3.14 Reader: flipbook and scroll (desktop and phone)

**Desktop flipbook (spread):**

```
┌───────────────────────────────────────────────────────────────────────────────┐
│ Puddle, the Duck Who Would Not Swim              [Flipbook] [Scroll]   ?      │
├───────────────────────────────────────────────────────────────────────────────┤
│        ┌──────────────────────┬──────────────────────┐                        │
│   ◂    │                      │                      │    ▸                   │
│        │       page 2         │       page 3         │                        │
│        │                      │                      │                        │
│        └──────────────────────┴──────────────────────┘                        │
│                         2 to 3 of 12                                          │
└───────────────────────────────────────────────────────────────────────────────┘
```

**Desktop scroll:**

```
┌───────────────────────────────────────────────────────────────────────────────┐
│ Puddle, the Duck Who Would Not Swim              [Flipbook] [Scroll]          │
├───────────────────────────────────────────────────────────────────────────────┤
│                  ┌──────────────────────────────┐                             │
│                  │ panel 1                      │                             │
│                  ├──────────────────────────────┤                             │
│                  │ panel 2                      │                             │
│                  ├──────────────────────────────┤                             │
│                  │ panel 3                      │                    7 of 24  │
│                  └──────────────────────────────┘                             │
└───────────────────────────────────────────────────────────────────────────────┘
```

**Phone (portrait):** flipbook shows one page, fit to width; scroll mode stacks panels full width.

```
┌─────────────────────┐   ┌─────────────────────┐
│ Puddle...  [F] [S]  │   │ Puddle...  [F] [S]  │
├─────────────────────┤   ├─────────────────────┤
│ ┌─────────────────┐ │   │ ┌─────────────────┐ │
│ │                 │ │   │ │ panel 1         │ │
│ │     page 2      │ │   │ ├─────────────────┤ │
│ │   (one page)    │ │   │ │ panel 2         │ │
│ │                 │ │   │ ├─────────────────┤ │
│ └─────────────────┘ │   │ │ panel 3         │ │
│  ◂   2 of 12   ▸    │   │ └─────────────────┘ │
│  swipe to turn      │   │       7 of 24       │
└─────────────────────┘   └─────────────────────┘
      flipbook                    scroll
```

| State | Note |
|---|---|
| Empty | Export with no pages is not allowed; if opened empty, "This comic has no pages yet." |
| Loading | Page-shaped skeleton and "Opening your comic..."; images load lazily; first page eager |
| Error | Missing image: panel shows alt text in a framed box with "Picture not found." and the rest keeps working |
| Populated | As above |
| Disabled capability | If JavaScript is off, the page renders as plain scroll HTML (the markup is complete without script); "Flipbook needs JavaScript. Showing scroll view." |

---

## 4. Component inventory

Shared props conventions: `id`, `disabled`, `busy`, `onChange`. All components accept `aria-label` overrides. Keyboard column lists keys when the component has focus.

### 4.1 Studio components

| Component | Props | States | Keyboard |
|---|---|---|---|
| AppHeader | `project`, `view`, `cloud: bool`, `kidMode`, `doctorStatus` | default, cloud, kid, offline | `Tab` across tabs; `Left/Right` between view tabs; `G` chords |
| ProjectCard | `project`, `progress`, `onOpen`, `onMenu` | default, hover, focus, archived, needs-backend | `Enter` open; `Shift+F10` or `Menu` opens menu; `Delete` asks trash with undo |
| WizardStep | `index`, `title`, `valid`, `children` | current, done, locked, error | `Enter` Next when valid; `Esc` back one step |
| CharacterCard | `character`, `selected`, `status` | draft, approved, blocked, person-derived, loading | `Enter` open; arrows move between cards |
| SheetGrid | `views[]`, `expressions[]`, `onRegenerate` | empty, rendering (sketch), partial error, approved | Arrows move across tiles; `R` regenerate tile; `Enter` enlarge |
| StylePicker | `styles[]`, `value`, `disabledStyles[]` | default, selected, disabled (with reason), custom | Arrows; `Space` select |
| BibleEditor | `bible`, `version`, `readOnly` | editing, saving, read-only (finalized), error | `Tab` fields; `Cmd/Ctrl+Enter` save version |
| ArcMeter | `percent`, `stages[]`, `current` | default, final-stage, complete | Not focusable; has `role="progressbar"` and text value |
| ThreadList | `threads[]`, `onJump` | empty ("No open threads."), populated, resolved | `Enter` jumps to the strip where thread was opened |
| BranchSelect | `branches[]`, `current` | default, creating, renaming | Arrows; `Enter` switch; `F2` rename |
| PlotChoiceCard | `intent` (continue, twist, steer, end), `beat`, `thumb`, `state` | loading, ready, selected, dimmed, no-preview | `1` to `4` select; `Enter` select; `Space` expand description |
| CustomBeatInput | `value`, `normalized`, `onAccept` | idle, normalizing, review, error | `Enter` submit; `Esc` clear |
| StripCanvas | `strip`, `selectedPanel`, `mode` | empty, writing, rendering, ready, approved, read-only | `J/K` panel; `Enter` open inspector; `A` approve |
| PanelSlot | `panel`, `state`, `onRetake` | empty, sketch, rendering, rendered, flagged, stale, approved | `R` retake; `L` lettering; `Enter` inspect |
| PanelInspector | `panel`, `fields` (shot, angle, setting, action, characters, poses, expressions, dialogue, caption, sfx) | clean, dirty-visual (marks stale), dirty-text (no redraw) | `Tab` fields; `Cmd/Ctrl+Enter` apply |
| TakesCarousel | `takes[]`, `current` | single, multiple, best-marked | `T` or `Left/Right` cycle; `Enter` pick |
| QABadge | `scores`, `textDetected`, `reasons` | ok, flagged, retrying, kept-by-user | Focus shows reasons popover; `Esc` closes |
| LetteringLayer | `balloons[]`, `editing` | display, editing, overflow-warning | `Tab` balloons; arrows nudge; `Enter` edit text |
| BalloonHandle | `balloon`, `handle` (move, resize, tail) | idle, hover, dragging | Arrows 1 px, `Shift` 10 px, `Alt` resize |
| Timeline | `strips[]`, `current` | empty, populated, drag-reorder (only before finalize) | `Left/Right`; `Enter` open; `Space` pick up for reorder |
| PageList | `pages[]`, `current` | default, reorder | `Up/Down`; `Space` reorder |
| PageCanvas | `page`, `layout`, `size` | empty, populated, drag-over slot, overflow warning | Slot focus with `Tab`; `Space` pick up |
| LayoutPicker | `templates[]`, `value` | default, selected, disabled | Arrows; `Space` select |
| UnplacedTray | `strips[]` | empty (hidden), populated | `Enter` places into the current page |
| SpreadView | `left`, `right`, `index` | normal, cover (right only), back cover (left only) | `Left/Right` spreads |
| BookInspector | `page`, `metadata` | per page kind, invalid field | `Tab` fields |
| ExportDialog | `target`, `format`, `options`, `job` | configure, estimating, running, done, error, capability-disabled | `Esc` cancel (or Stop if running); `Enter` Export; focus trapped |
| JobToast | `job`, `onStop` | running, success, error | `Enter` open; `Esc` dismiss (not stop) |
| UndoBar | `canUndo`, `canRedo`, `label` | default, disabled (no history), just-did ("Moved panel. Undo") | `Cmd/Ctrl+Z`; `Shift+Cmd/Ctrl+Z` |
| KidModeLock | `locked`, `holdMs=2000` | locked, holding (ring), gate | Hold `Space` or `Enter` 2 s; gate shows a sum problem |
| CloudBadge | `stages[]` | hidden, visible | Focus reads "Cloud: story and images are sent to a service." |
| DoctorBanner | `checks[]` | hidden, error, advisory, expanded | `Enter` details; `Esc` dismiss advisory |
| FirstUseCloudNotice | `provider`, `sends[]` | pending, accepted | Focus trapped inline; `Enter` on chosen button |
| AttestationBox | `person`, `checked` | unchecked, checked, recorded | `Space` toggle; Continue disabled until checked |
| ClassroomJoinForm | `code`, `name` | idle, joining, wrong code, rate limited | `Enter` submit |

### 4.2 Reader components

| Component | Props | States | Keyboard |
|---|---|---|---|
| ReaderShell | `title`, `mode`, `pages[]`, `lang` | loading, ready, no-script (plain scroll) | Global reader keys (see 11.2) |
| PageView | `page`, `index` | loading, ready, image-missing (alt text frame) | Not focusable by itself; page region labeled |
| Spread | `left`, `right` | two-up, cover (single right), back (single left), collapsed to one on narrow screens | Same as flipbook keys |
| ScrollStrip | `panels[]` | loading, ready, current-marked | `Up/Down`, `PgUp/PgDn`, `Home/End` native scrolling |
| BalloonText | `text`, `kind`, `x,y,w,h`, `lang`, `narrate` | normal, selected text, high-contrast | Text selectable; in tab order only for the panel region |
| ModeToggle | `mode` | flipbook, scroll | `Tab` to focus; `Space/Enter` toggles; `M` shortcut |
| PageCounter | `current`, `total`, `spread` | single ("3 of 12"), spread ("2 to 3 of 12") | Not focusable; `aria-live="polite"` announces page changes |

---

## 5. Design tokens

### 5.1 Color

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
:root[data-theme="dark"] {
  --cs-bg: #15130F; --cs-surface: #1E1B16; --cs-surface-2: #27231D; --cs-border: #3A342B;
  --cs-canvas: #0F0D0A; --cs-text: #F2ECE3; --cs-text-muted: #B5AA9C;
  --cs-accent: #6F8DFF; --cs-accent-hover: #8AA2FF;
}
```

**Lettering colors never follow the UI theme.** `--cs-balloon-fill`, `--cs-balloon-ink`, and `--cs-caption` are not redefined in the dark blocks. Balloons stay white with black ink in dark mode because they are part of the artwork, and the same pixels must appear in the Studio, in exports, and in the Reader. The Reader's chrome (header, counter, toggle) follows the theme; the page and balloon artwork does not.

Contrast notes: `--cs-text` on `--cs-bg` is above 15:1; `--cs-text-muted` on `--cs-bg` is above 5:1; `--cs-text-inverse` on `--cs-accent` is above 5:1 in light and `#15130F` text is used on the dark accent. Status colors are always paired with an icon and a word.

Token usage map:

| Token | Used for | Not used for |
|---|---|---|
| `--cs-accent` | The one primary button per view, selected plot card border, focus on Approve | Body links in dense text, decorations |
| `--cs-pop-red` | Destructive confirmations, Delete | Errors (use `--cs-error`) |
| `--cs-pop-yellow` | Child mode highlights, end-here card outline | Warnings (use `--cs-warn`) |
| `--cs-canvas` | Area behind pages and strips | Cards |
| `--cs-focus` | 2 px focus ring, 2 px offset, on every focusable control | Anything else |

### 5.2 Typography

- UI: `Inter` (400, 500, 600). Scale: 12, 14, 16, 20, 24, 32 px. Tabular numerals for counters (`font-variant-numeric: tabular-nums`).
- Lettering: Comic Neue (dialogue), Bangers (SFX and shouts), Atkinson Hyperlegible (kids reading styles and captions for early readers). All bundled and embedded; no web font requests.
- Child mode labels: 24 px, 600 weight.

| Role | Font | Size | Weight | Line height |
|---|---|---|---|---|
| Page title | Inter | 32 | 600 | 1.2 |
| Section heading | Inter | 20 | 600 | 1.3 |
| Body | Inter | 16 | 400 | 1.5 |
| Dense UI, labels | Inter | 14 | 500 | 1.4 |
| Caption, meta | Inter | 12 | 400 | 1.4 |
| Child label | Inter | 24 | 600 | 1.25 |
| Counters | Inter, tabular | 14 | 500 | 1.2 |

### 5.3 Spacing, radius, borders

- Spacing is a 4 px base: 4, 8, 12, 16, 24, 32, 48, 64 (`--cs-space-1` to `--cs-space-8`).
- Radius: 10 px for cards, 6 px for inputs, full for avatar chips (`--cs-radius-card`, `--cs-radius-input`, `--cs-radius-full`).
- Panel borders default to 3 px ink with 2 px radius; a style can override width and radius.
- UI borders are 1 px `--cs-border`; focus ring is 2 px `--cs-focus` with 2 px offset.
- Elevation: none beyond a 1 px border and a single 4 px lift transform for selected cards. No gradients, no glass blur.

### 5.4 Signature element: the ink sweep

**Purpose.** Turns waiting into anticipation and doubles as a preview of composition.

**Anatomy.**

1. **Sketch placeholder.** Generated from the panel's composition: simple outline shapes for characters at their layout positions, a horizon line, and a rough balloon zone, drawn in `--cs-text-muted` at 1.5 px line weight on `--cs-surface-2`.
2. **Sweep.** A soft diagonal band (about 30 degrees from vertical, 24 percent of panel width) of `--cs-text` at 8 percent opacity moves left to right, looping. It is a flat band with a 6 px feathered edge produced by a mask, not a gradient fill.
3. **Landing.** When art arrives, the band completes one last pass (240 ms), then the art fades in over 200 ms and the sketch fades out.

```
 sketch + sweep position over time
 t0         t1         t2         t3 (land)
┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐
│▒ ○  ▢  │ │  ▒○  ▢ │ │  ○ ▒▢  │ │ [art]  │
│▒  ╲_   │ │  ▒╲_   │ │  ╲_▒   │ │ fades  │
└────────┘ └────────┘ └────────┘ └────────┘
```

**Spec.**

| Property | Value |
|---|---|
| Sweep loop duration | 1800 ms, `linear`, per panel, offset 150 ms between panels |
| Land | 240 ms `ease-out` final pass |
| Art fade | 200 ms `ease-out` |
| Text status | Always shown with the sweep: "Drawing panel 3 of 4..." |
| Stop | A visible Stop button for the job while any sweep runs |
| Reduced motion | Static sketch only; status text and a "Drawing" label remain; art swaps in without fade |
| Print / export | The sweep never appears in exports |
| Child mode | Same element, larger status text (24 px) |

---

## 6. Lettering visual spec

Lettering is vector SVG layered over the panel art (FR-019), embedded in exports, and live text in the Reader. All sizes below are at the Studio reference panel width of 480 px and scale with the panel (`em` units); the minimum rules in 6.5 apply to the scaled result.

### 6.1 Common properties

| Property | Value |
|---|---|
| Stroke | 2 px `--cs-balloon-ink` at reference width (scales with panel) |
| Fill | `--cs-balloon-fill` (white) |
| Padding | 0.6 em on all sides inside the shape's inscribed text box |
| Line height | 1.15 |
| Text alignment | Centered for speech, thought, shout, whisper; left for captions |
| Font size range | Auto-fit between min and max (6.4); never below the minimum |
| Overflow | Balloon grows (up to 40 percent of panel width) before font shrinks; never leaves the panel bounds |
| Safe margin | 8 px from panel edge |

### 6.2 Balloon shapes and SVG geometry

Geometry is defined in a local box `w x h` after text layout; shapes are built from that box.

**Speech.** Rounded ellipse (default) or rounded rectangle (when text is 3 or more lines and wider than tall).

```
   ╭──────────────────────╮
  (   Jump in! It's warm!  )
   ╰───────────╲──────────╯
                ╲
                 ◂ tail tip at the speaker's head box
```

- Ellipse: `<ellipse rx="w/2 + 0.5em" ry="h/2 + 0.4em">`. Text inscribed in a rectangle of 0.8w by 0.8h (padding applies inside this).
- Rounded rectangle: `<rect rx="min(0.7em, h/3)">`.
- Tail: a tapered quadratic curve path. Base on the balloon outline, 0.9 em wide, centered on the point closest to the target; control point offset 35 percent of the base-to-tip distance perpendicular to the line, bending toward the panel center; tip is a point (0 width). Path: `M b1 Q c tip Q c2 b2 Z`, filled white with the same 2 px stroke; the stroke is clipped so no line crosses the base (draw the fill over the stroke at the base).
- Tail tip lands 0.25 em short of the head box edge, never covering the face.

**Thought.** Cloud outline of 9 to 14 scalloped arcs along the text box perimeter (each arc a circle segment with radius about 0.55 em), plus three trailing circles toward the thinker, diameters 0.9 em, 0.6 em, 0.35 em, spaced 0.5 em apart along the line to the head box.

```
    .~~~~~~~~~~~~~~.
  (  Maybe water    )
   (  is not so     )
    '~~~~~~~~~~~~~'
        o
      o
     .
```

**Shout.** Spiky burst: a polygon with 14 to 22 points alternating outer radius `R` and inner radius `0.78R`, with +/- 6 percent random-but-seeded jitter per point so the shape is stable between renders. Stroke 3 px, join `miter`, miter limit 4. Font weight bold (Bangers, or Comic Neue 700 in picture-book styles), size 115 percent of dialogue size. Tail is a straight-edged wedge.

```
      \  |  /
   ─── JUMP IN! ───
      /  |  \
```

**Whisper.** Same shape as speech, stroke dashed `stroke-dasharray: 5 4`, text color `#555555` (lettering color, not theme-driven), size 90 percent of dialogue.

```
   ╭ ─ ─ ─ ─ ─ ─ ─ ╮
  ( psst, over here )
   ╰ ─ ─ ─ ─ ╲─ ─ ─╯
```

**Caption.** Rectangle, no radius (0 to 2 px), fill `--cs-caption` (`#FFF4C2`), 2 px ink stroke, anchored top-left of the panel by default with 8 px offset, left-aligned, max width 60 percent of panel width, no tail. Multiple captions stack with 4 px gap.

```
┌────────────────────────┐
│ Later that afternoon…  │
└────────────────────────┘
```

**SFX.** Display font (Bangers), fill a style-accent color with a dark outline: `paint-order: stroke fill; stroke: #111; stroke-width: 0.12em; stroke-linejoin: round`. Rotation between -8 and 8 degrees (seeded from the panel and SFX id so it is stable), size 2 to 3 times dialogue size, placed near its source (within 1.5 character head-box widths of the source object), never over a face. Fill color options come from the style palette (for example `#F5C542`, `#E5484D`, `#2F5BEA` with sufficient contrast against its outline), not from the UI theme.

```
    SPLISH!        (rotated -6 deg, fill yellow, dark outline)
```

### 6.3 Fonts per style

| Style | Dialogue | SFX and shouts | Captions | Case |
|---|---|---|---|---|
| picture-book-watercolor | Comic Neue 400 (kids audiences: Atkinson Hyperlegible 400) | Bangers | Atkinson Hyperlegible for kids-5-8, else Comic Neue italic | Mixed case |
| bold-cartoon | Comic Neue 700 | Bangers | Comic Neue 700 | Uppercase |
| manga-ink | Comic Neue 400 | Bangers | Comic Neue 400 | Mixed case (configurable) |
| newspaper-strip | Comic Neue 700 | Bangers | Comic Neue 700 | Uppercase |
| soft-3d-clay | Comic Neue 400 | Bangers | Atkinson Hyperlegible | Mixed case |
| pixel-art | Comic Neue 700 (not a pixel font, for legibility) | Bangers | Comic Neue 700 | Mixed case |

### 6.4 Uppercase rules

- Uppercase is on by default for bold-cartoon and newspaper-strip; mixed case for the other presets. It is a per-style setting the user can change.
- Applied by `text-transform: uppercase` in display and by uppercasing at export for PDF and Reader text so that copy, search, and narration (`data-narrate`) use the original, mixed-case text.
- Never uppercase captions for audiences kids-5-8 (early readers).
- SFX are always uppercase.

### 6.5 Sizes and limits

| Property | Value |
|---|---|
| Dialogue size at reference | 16 px at 480 px panel width (3.3 percent of width) |
| Auto-fit range | 12 px to 22 px at reference width |
| Minimum on web | 14 px (Studio and Reader, after scaling) |
| Minimum at print size | 9 pt |
| Kids-5-8 minimum | 18 px web, 11 pt print |
| Shout size | 115 percent of dialogue |
| Whisper size | 90 percent of dialogue (never below the minimum) |
| Caption size | 100 percent of dialogue |
| SFX size | 200 to 300 percent of dialogue |
| Line height | 1.15 |
| Padding | 0.6 em |
| Max balloon width | 40 percent of panel width (caption 60 percent) |
| Audience cap (kids-5-8) | 10 words per balloon, 2 balloons per panel |

### 6.6 Placement rules

1. Reading order is top-left to bottom-right; the reading order number is stored and shown in the editor.
2. Balloons avoid character bounding boxes from the vision model. If no clear zone exists, the balloon overlaps the least important background region and a review flag is raised.
3. Tail points at the speaker's head box; for off-panel speakers the tail exits at the nearest panel edge with a small tick.
4. Balloons never overlap each other (minimum 6 px gap) and never leave the safe margin.

---

## 7. Page layout templates

Each diagram shows slot rectangles with reading order numbers (1 is first). Slots are panels (or whole strips for strip-stack). Proportions are approximate; real slots are computed from page size, margins, and gutter.

### 7.1 strip-stack (3 strips per page by default)

```
┌───────────────────────────────┐
│ ┌──────┬──────┬──────┬──────┐ │
│ │  1   │  2   │  3   │  4   │ │   strip A
│ └──────┴──────┴──────┴──────┘ │
│ ┌──────┬──────┬──────┬──────┐ │
│ │  5   │  6   │  7   │  8   │ │   strip B
│ └──────┴──────┴──────┴──────┘ │
│ ┌──────┬──────┬──────┬──────┐ │
│ │  9   │  10  │  11  │  12  │ │   strip C
│ └──────┴──────┴──────┴──────┘ │
└───────────────────────────────┘
```

Strips are never split across pages by default. Panels in a strip keep their authored widths.

### 7.2 classic-three-tier

```
┌───────────────────────────────┐
│ ┌───────────┬───────────────┐ │
│ │     1     │       2       │ │   tier 1: 30 percent height
│ └───────────┴───────────────┘ │
│ ┌─────────┬─────────┬───────┐ │
│ │    3    │    4    │   5   │ │   tier 2: 35 percent
│ └─────────┴─────────┴───────┘ │
│ ┌───────────────────────────┐ │
│ │             6             │ │   tier 3: 35 percent (wide)
│ └───────────────────────────┘ │
└───────────────────────────────┘
```

### 7.3 grid-2x2

```
┌───────────────────────────────┐
│ ┌─────────────┬─────────────┐ │
│ │      1      │      2      │ │
│ ├─────────────┼─────────────┤ │
│ │      3      │      4      │ │
│ └─────────────┴─────────────┘ │
└───────────────────────────────┘
```

### 7.4 grid-3x3

```
┌───────────────────────────────┐
│ ┌───────┬───────┬───────┐     │
│ │   1   │   2   │   3   │     │
│ ├───────┼───────┼───────┤     │
│ │   4   │   5   │   6   │     │
│ ├───────┼───────┼───────┤     │
│ │   7   │   8   │   9   │     │
│ └───────┴───────┴───────┘     │
└───────────────────────────────┘
```

### 7.5 splash-plus-two

```
┌───────────────────────────────┐
│ ┌───────────────────────────┐ │
│ │                           │ │
│ │            1              │ │   splash: 60 percent height
│ │          (splash)         │ │
│ │                           │ │
│ └───────────────────────────┘ │
│ ┌─────────────┬─────────────┐ │
│ │      2      │      3      │ │   two panels: 40 percent
│ └─────────────┴─────────────┘ │
└───────────────────────────────┘
```

### 7.6 vertical-scroll (web)

```
┌───────────────────┐
│ ┌───────────────┐ │
│ │       1       │ │
│ └───────────────┘ │
│         ↓         │  gutter 24 px, no page breaks
│ ┌───────────────┐ │
│ │       2       │ │
│ └───────────────┘ │
│         ↓         │
│ ┌───────────────┐ │
│ │       3       │ │
│ └───────────────┘ │
│         ⋮         │
└───────────────────┘
  one continuous column, width 720 px max, panels full column width
```

Reading order rule for every template: left to right, top to bottom, with tiers and rows resolved before columns, and a wide slot spanning columns reads before the next row.

### 7.8 Page sizes and defaults

Gutter is the space between slots; margin is the page edge to the content area; bleed is extra art beyond the trim edge used only in print exports (PDF print adds 0.125 in).

| Page size | Trim size | Margins (top / outer / bottom / inner) | Gutter | Bleed (print) | Notes |
|---|---|---|---|---|---|
| US comic | 6.625 x 10.25 in | 0.375 / 0.375 / 0.375 / 0.4375 in | 0.125 in | 0.125 in | Default for print books; inner margin larger for binding |
| US Letter | 8.5 x 11 in | 0.5 / 0.5 / 0.5 / 0.625 in | 0.15 in | 0.125 in | Home printing |
| A4 | 210 x 297 mm | 12 / 12 / 12 / 16 mm | 4 mm | 3 mm | International; bleed 3 mm in print |
| Square | 8.5 x 8.5 in | 0.4 / 0.4 / 0.4 / 0.5 in | 0.125 in | 0.125 in | Picture-book format |
| Web | 1200 px wide, height by content | 24 px | 12 px (24 px in vertical-scroll) | none | Reader pages; responsive scale |

Notes: the gutter default in the Studio control is shown in the unit of the page size (px for web). Bleed `on` means panel art extends into the bleed on outer edges; borders are kept inside the trim. Safe area for balloons is 0.25 in inside the trim in print and 8 px in web.

---

## 8. Motion and feedback

All durations assume 60 fps; `ease-out` is `cubic-bezier(0.2, 0, 0, 1)`, `ease-in-out` is `cubic-bezier(0.4, 0, 0.2, 1)`.

| Interaction | Motion | Duration | Easing | Reduced motion |
|---|---|---|---|---|
| Panel render (ink sweep) | Sketch with diagonal sweep loops | 1800 ms loop | linear | Static sketch with text status |
| Art lands | Final sweep pass, then fade art in | 240 ms + 200 ms | ease-out | Instant swap |
| Plot choice select | Card lifts 4 px; others fade to 60 percent | 150 ms | ease-out | Border change and opacity only, no lift |
| Approve strip | Strip slides into the timeline | 250 ms | ease-in-out | Instant move, timeline item flashes outline once (no motion) |
| Take change | Cross-fade between takes | 120 ms | ease-out | Instant |
| Balloon drag | Follows pointer, no easing; snaps to 4 px grid on release | 0 ms; snap 80 ms | ease-out | Snap instant |
| Panel drag in Pages | Item lifts with 2 px offset; slot highlights | 120 ms | ease-out | No lift |
| Page turn (Reader flipbook) | Horizontal slide of 16 px plus fade | 220 ms | ease-in-out | Instant swap |
| Toast in/out | Fade and 8 px rise | 160 ms | ease-out | Fade only |
| Undo toast | Appears for 6 s with a visible countdown bar | 6000 ms | linear | Text countdown, no bar animation |
| Child mode choice tap | Card lifts 8 px and border thickens | 150 ms | ease-out | Border only |
| Lock hold ring | Ring fills around lock | 2000 ms | linear | Ring still fills (it is a progress indicator, not decoration), no pulse |
| Skeletons | Soft opacity pulse 0.6 to 1 | 1400 ms | ease-in-out | Static at 0.8 |

Feedback rules:

- Every action acknowledges within 100 ms (pressed state at minimum).
- Jobs over 1 second show a text status; over 5 seconds also show progress counts (for example "page 13 of 24") and a Stop button.
- Sound: none in the Studio. In child mode, speech synthesis plays only when a choice is tapped.
- Under `prefers-reduced-motion: reduce`, all transforms, fades longer than 100 ms, sweeps, and pulses are disabled. State changes remain visible through borders, icons, and text.
- Under `prefers-reduced-motion`, the Reader disables page-turn animation and smooth scrolling.

---

## 9. Copy guidelines and microcopy

### 9.1 Voice

- Plain, warm, specific. Say what happened and what to do next.
- Short sentences. Active voice. First person plural only in child mode ("our comic").
- Name things: "Puddle", "panel 3", "strip 4", not "the item".
- No blame ("You entered..."). No jargon ("inference", "checkpoint", "LoRA", "seed") in primary UI; those appear only in advanced details.
- Sentence case for buttons and headings. No exclamation marks in errors. Occasional warmth in success states.
- No emoji in UI chrome. Lettering may contain user-typed emoji only when the font supports it.
- Avoid hype and marketing words.
- Numbers: use digits; ranges written "5 to 8", never with a dash.
- Errors say what, why (if known), and the fix. Every error offers one action.

### 9.2 Examples from the build prompt

| Context | String |
|---|---|
| Empty project | Start with a story idea, a photo, or both. |
| Rendering | Drawing panel 3 of 4... |
| QA retake | Sub looked a little different, redrawing. |
| End-here suggestion | This feels like a good ending. End the story here? |
| Originality block | That character looks a lot like a famous cartoon. Let's give Puddle a look that is all yours. |

### 9.3 Additional microcopy

| # | Context | String |
|---|---|---|
| 1 | Home, empty library | Characters you save will live here. |
| 2 | Home, projects folder error | We could not open your projects folder. Check that it still exists, then try again. |
| 3 | Wizard, text too long | Your idea is a bit long. Keep it under 5,000 characters. |
| 4 | Wizard, unsupported photo | That file type is not supported. Use PNG, JPG, WebP, or HEIC. |
| 5 | Wizard, photo too big | That photo is over 20 MB. Try a smaller one. |
| 6 | Wizard, photo privacy | Location data in photos is removed before anything is saved. |
| 7 | Wizard, analyzing photo | Looking at your photo... |
| 8 | Attestation | I have the right to use this person's likeness. |
| 9 | Attestation explanation | We will turn this person into a cartoon character. Photorealistic looks are turned off for this character. |
| 10 | Public figure decline | We cannot draw real public figures. Describe a new character instead. |
| 11 | Named franchise block | That name belongs to someone else's character. Describe your own character and we will draw it. |
| 12 | Artist style block | We do not copy living artists. Pick one of our looks or describe your own. |
| 13 | Audience safety block | That idea is not right for ages 5 to 8, so we skipped it. Try a gentler twist. |
| 14 | Image audience block | That picture was not right for ages 5 to 8, so we redrew it. |
| 15 | Moderation block, specific | We could not use that beat because it asks for something unsafe. Change it and try again. |
| 16 | Suggestions loading | Thinking of three ideas... |
| 17 | Custom beat prompt | Write what happens next, in your own words. |
| 18 | Beat normalized | We tidied your idea into a beat. Use it, or edit it. |
| 19 | New character in beat | Frog is new. Add to the cast? |
| 20 | Panel failed | This panel did not draw after 2 tries. Try again, or change the shot. |
| 21 | Stale panel | Out of date: the script changed. Redraw to match. |
| 22 | Text drawn in image | We found letters drawn inside the picture, so we redrew it. Words are added later as lettering. |
| 23 | Approve disabled | Approve unlocks when every panel is drawn and lettered. |
| 24 | Strip approved | Strip 4 approved. Here are three ideas for strip 5. |
| 25 | Unapprove confirm | Unapprove strip 4? Its panels become editable again. |
| 26 | Delete project confirm | Move Puddle to the trash? You can restore it from the trash folder. |
| 27 | Undo toast | Moved panel 2. Undo |
| 28 | Lettering overflow | This balloon has 14 words. Kids 5 to 8 works best with 10 or fewer. |
| 29 | Lettering no spot | We could not find a clear spot for this balloon. Drag it where you like. |
| 30 | Pages locked | Pages unlock when your story is finalized. |
| 31 | Auto-paginate | Ready to lay out your comic. |
| 32 | Layout overflow | Strip 5 does not fit this layout. Try grid-2x2, or allow splitting strips. |
| 33 | Book empty | A book needs a cover and at least one story. |
| 34 | Cover failed | Cover art did not draw. You can pick a panel instead. |
| 35 | Finalize review | We found 2 things to look at before you finish. Jump to each, or finalize anyway. |
| 36 | Finalized banner | This story is finalized and read-only. Reopen it to make a new version. |
| 37 | Export estimate | About 18 MB, 24 pages. |
| 38 | Export running | Exporting your PDF... page 13 of 24 |
| 39 | Export done | Your PDF is ready. 24 pages, 18 MB. |
| 40 | Export failed, disk | The export stopped at page 13: not enough disk space (needs 420 MB). Choose another folder, or try again. |
| 41 | PDF capability | PDF export needs Chromium. Run doctor to install it. |
| 42 | Web export done | Your comic is ready to share. Open index.html in any browser, even offline. |
| 43 | Cloud badge tooltip | Cloud: your story text and prompts are sent to a service. |
| 44 | First-use cloud notice | If you turn this on, your story text, prompts, and reference images leave your computer. Photos have location data removed first. Nothing is sent until you press Use cloud. |
| 45 | Keys note | API keys are read from your environment or keyring. They are never saved in projects. |
| 46 | Backend unreachable | ComfyUI did not answer at 127.0.0.1:8188. Run doctor to see what to fix. |
| 47 | Doctor banner | Setup needs attention: no image backend is reachable. |
| 48 | Doctor all clear | All set. Everything the Studio needs is ready. |
| 49 | Classroom wrong code | That code did not match. Check with your teacher and try again. |
| 50 | Classroom rate limit | Too many tries. Wait a minute, then try again. |
| 51 | Classroom privacy | Your comics are private to you unless you share them. |
| 52 | Job stop | Stop drawing? Finished panels are kept. |
| 53 | Offline notice | You are offline. Drawing with a cloud service will wait until you are back. |
| 54 | Child, start | Ask a grown-up to start our comic. |
| 55 | Child, error | Oops, the picture did not finish. Let's try again. |
| 56 | Child, backend asleep | The drawing helper is asleep. Ask a grown-up to wake it up. |
| 57 | Child, end | The end! Want to read our comic? |
| 58 | Reader, image missing | Picture not found. |
| 59 | Reader, no script | Flipbook needs JavaScript. Showing scroll view. |
| 60 | Reader, page counter | Page 3 of 12 |

---

## 10. Child mode rules

Child mode is a simplified Studio view for young co-creators, toggled with "Kid mode" in the header. A parent or teacher turns it on; leaving it requires the lock.

### 10.1 What is shown

Only:

1. The current strip, large (at least 60 percent of viewport height).
2. Three big picture choices: each a 240 px thumbnail plus a 3 to 5 word label, 24 px, 600 weight. The label is read aloud with the browser's speech synthesis when the card is tapped.
3. One big `Make it!` button (at least 64 px high, full-width on phones).
4. A `Read our comic` button that opens the Reader.
5. The lock icon.

### 10.2 What is never shown

No settings, no text fields, no delete, no export, no backend or cloud details, no raw error text, no undo history, no free-text custom beat, no Cast or Pages or Book. Prompts, seeds, and QA scores are hidden. The End-here option appears as a fourth picture card with the label "The end".

### 10.3 Rules

| Rule | Detail |
|---|---|
| Targets | 64 px minimum in both dimensions, 16 px minimum gap between targets |
| Labels | 24 px, 600 weight, 3 to 5 words, Atkinson Hyperlegible for reading-level text in the strip |
| Sound | No autoplay. Speech synthesis only when a choice is tapped; a speaker icon on each card allows replay. Never background music |
| Reading level | Labels follow the audience setting; kids-5-8 uses words of one or two syllables where possible |
| Choice behavior | Tap once to select and hear it; tap `Make it!` to commit. Selecting another card replaces the first. No timers |
| Errors | One friendly sentence and one big `Try again` button. No codes. Details are visible to a grown-up after unlocking |
| Safety | Audience rules stay in force. The audience setting cannot be changed from child mode. Content blocks show a soft message ("Let's pick a different idea.") and refresh choices |
| Cloud | If a cloud backend is active, child mode requires that the grown-up accepted the first-use cloud notice before the toggle is enabled |
| Colors | Uses `--cs-pop-yellow` for selection highlights; same UI surfaces; no flashing |
| Motion | Same reduced-motion rules; no more than one animated element at a time |
| Focus | Visible focus ring, thick (3 px) for keyboard users; tap highlights for touch |

### 10.4 Lock and grown-up exit

- The lock icon is in the top-left, 64 px target.
- Press and hold for 2 seconds. A ring fills around the icon. Releasing early cancels with no message.
- On completion a gate asks a simple sum ("What is 7 + 6?") with a numeric keypad and `Cancel`. A correct answer returns to the full Studio. This prevents accidental exit, not determined exit; the gate is not a security boundary.
- Keyboard: hold `Space` or `Enter` on the focused lock for 2 seconds.
- Screen readers: announce "Grown-up lock. Press and hold for two seconds to open."
- In classroom mode, the teacher's access code can also unlock.

---

## 11. Reader spec

The Reader is the self-contained web export (FR-025). It reproduces the Studio rendering exactly (same fonts, same balloon positions).

### 11.1 Modes

| Mode | Behavior |
|---|---|
| Flipbook | One page, or a two-page spread on wide screens, with arrow keys, swipe, buttons, and a page counter |
| Scroll | Vertical column, panels stacked, ideal on phones; progress shown as "7 of 24" |

- Header shows the title and a mode toggle. The default mode is flipbook on viewports 900 px wide or more and scroll on narrower ones; the choice is remembered in `localStorage` when available (wrapped in try/catch) and never required.
- URL hash reflects position (`#/page/3`, `#/scroll`) so a link opens the right place.

### 11.2 Keyboard

| Key | Action |
|---|---|
| `Right` / `PageDown` / `Space` | Next page or spread (flipbook); scroll down (scroll) |
| `Left` / `PageUp` / `Shift+Space` | Previous page or spread; scroll up |
| `Home` / `End` | First / last page |
| `M` | Toggle mode |
| `+` / `-` | Zoom in / out (flipbook), 100 to 200 percent |
| `F` | Fullscreen |
| `?` | Show shortcuts |
| `Tab` | Moves through header controls, then page region, then footer |

### 11.3 Swipe and touch

- Horizontal swipe turns pages in flipbook (threshold 48 px or 20 percent of width, with velocity bonus). Vertical gestures are never captured, so scrolling a zoomed page still works.
- Edge tap zones (outer 20 percent) turn pages; the center does nothing so text can be selected.
- Pinch zoom is browser-native; double-tap zooms to the tapped panel in flipbook.
- Buttons for previous and next are at least 44 px; 64 px is not required outside child mode, but the Reader's own child-friendly variant uses 64 px (open question 14.4).

### 11.4 Spreads on wide screens

- At 900 px or wider (landscape), flipbook shows spreads: cover alone on the right, then pairs (2 to 3, 4 to 5), back cover alone on the left.
- Below 900 px, one page is shown, fit to width (portrait) or fit to height (landscape phone).
- Page size is preserved; the spread never crops pages. If the viewport height is too small, the spread scales down uniformly.
- The counter reads "2 to 3 of 12" for a spread and "Page 3 of 12" for a single page.

### 11.5 Balloons as DOM text

- Balloon shapes are inline SVG; balloon text is real text in the DOM (`<text>` in SVG or absolutely positioned HTML laid over the SVG), not rasterized.
- Text is selectable, translatable (`lang` set on the element and on the document; text nodes stay whole), and narratable.
- Reading order in the DOM matches visual reading order (top-left to bottom-right), per panel and per page.
- Fonts are embedded as base64 `@font-face` subsets (only the glyphs used); no network requests.
- Uppercase is applied through CSS `text-transform`, so copy and search return the original case.

Sample markup:

```html
<section class="cs-page" aria-label="Page 2" data-page="2">
  <figure class="cs-panel" data-panel="2-1" role="group" aria-labelledby="p2-1-alt">
    <img src="data:image/webp;base64,..." alt="" aria-hidden="true">
    <figcaption id="p2-1-alt" class="cs-sr">Sub waves Puddle into the water.</figcaption>
    <svg class="cs-balloon cs-speech" viewBox="0 0 220 90" role="presentation">...</svg>
    <p class="cs-balloon-text" lang="en"
       data-narrate="dialogue" data-speaker="Sub" data-order="1">Jump in! It's warm!</p>
    <p class="cs-sfx" lang="en" data-narrate="sfx" data-order="2">Splish!</p>
  </figure>
</section>
```

### 11.6 data-narrate markup (mr-audio-smith)

Reading text carries `data-narrate` attributes so mr-audio-smith can narrate the comic.

| Attribute | Values | Meaning |
|---|---|---|
| `data-narrate` | `title`, `caption`, `dialogue`, `thought`, `sfx`, `alt` | Kind of reading text |
| `data-order` | integer | Order within the panel |
| `data-speaker` | character name | For dialogue and thought |
| `data-panel` | `page-index` | Panel id |
| `lang` | BCP 47 | Language of the text |

- Reading order for narration is page, then panel, then `data-order`.
- Panel action descriptions (the alt text) are marked `data-narrate="alt"` and are skipped by default (narrated only when the listener chooses described mode).
- SFX are narrated only when enabled.

### 11.7 Alt text

- Each panel image has an accessible description from the panel's action description (FR-025), for example "Sub waves Puddle into the water. Puddle looks nervous."
- The image carries `alt=""` with `aria-hidden="true"` when the same text is exposed once in a visually hidden `figcaption` (shown in the sample above), so screen readers read the description once.
- Cover and title pages get descriptive alt text from the book metadata.
- Balloon text is not repeated in the alt.

### 11.8 Offline and size

- Works from `file://`: no external requests, no fetch to relative files (the single-file variant embeds everything; the folder variant uses relative `<img src>` only).
- No service worker is required. The Reader works with scripts disabled as a plain scroll page.
- Reader code (HTML shell, CSS, JS) must stay under 25 KB gzipped, excluding images and embedded font subsets. Font subsets and images are budgeted separately and listed in the export summary.
- No frameworks. Vanilla JS, one file, no dependencies. Lazy-load images below the first two pages (`loading="lazy"` in the folder variant).
- Print stylesheet: prints pages one per sheet, hides chrome.

### 11.9 Reader chrome and theming

Chrome follows `prefers-color-scheme` using the same `--cs-` tokens; page and balloon artwork do not. A visible light/dark switch is not offered in the Reader (the OS decides), keeping the footprint small.

---

## 12. Accessibility

Target: WCAG 2.2 AA across Studio, Child mode, and Reader.

### 12.1 Checklist

| Criterion | Requirement | Where verified |
|---|---|---|
| 1.1.1 Non-text content | Panel images have alt text from the action description; decorative sketches are `aria-hidden` | Reader, Strips |
| 1.3.1 Info and relationships | Landmarks (header, nav, main, complementary), headings in order, labeled form controls | All |
| 1.3.4 Orientation | No orientation lock | Reader, Child mode |
| 1.4.1 Use of color | Never the only signal: status = icon + text + color | All |
| 1.4.3 Contrast (minimum) | Text 4.5:1, large text 3:1 | Tokens in both themes |
| 1.4.4 Resize text | Usable to 200 percent without loss | All |
| 1.4.10 Reflow | No two-dimensional scroll at 320 px width (Studio columns collapse) | Studio, Reader |
| 1.4.11 Non-text contrast | UI component borders and focus rings 3:1 | Tokens |
| 1.4.12 Text spacing | Layout survives user spacing overrides | UI chrome (lettering excluded; it is artwork, but is real text in Reader) |
| 1.4.13 Content on hover or focus | Popovers dismissible (`Esc`), hoverable, persistent | QA badge, tooltips |
| 2.1.1 Keyboard | Every action has a keyboard path, including drag (Space pick up, arrows, Space drop) | All |
| 2.1.2 No keyboard trap | Dialog traps focus but `Esc` always exits | Export dialog |
| 2.2.1 Timing adjustable | No timed actions; the 6 s undo toast has an always-available Undo button and history | Toasts |
| 2.2.2 Pause, stop, hide | Ink sweep stops with reduced motion; every job has Stop | Strips |
| 2.3.1 Three flashes | None | All |
| 2.4.3 Focus order | Matches visual order | All |
| 2.4.7 Focus visible | 2 px `--cs-focus` ring, 2 px offset | All |
| 2.4.11 Focus not obscured | Sticky header and bottom bars never cover the focused element (scroll-padding) | Studio |
| 2.5.1 Pointer gestures | Swipe has button equivalents; drag has keyboard equivalent | Reader, Pages |
| 2.5.7 Dragging movements | Every drag has a click or keyboard alternative | Pages, Book, Timeline, Lettering |
| 2.5.8 Target size (minimum) | See 12.2 | All |
| 3.2.6 Consistent help | Help (`?`) and Doctor in the same place on every screen | Studio |
| 3.3.1, 3.3.3 Error identification and suggestion | Text errors with a fix | All forms |
| 3.3.7 Redundant entry | Wizard keeps previous answers when going back | Wizard |
| 3.3.8 Accessible authentication | Classroom code accepts paste; no cognitive test (the child-mode gate is not an authentication step and offers a keyboard path) | Join, lock |
| 4.1.2 Name, role, value | ARIA roles for custom controls (tabs, listbox, progressbar, dialog) | All |
| 4.1.3 Status messages | Job progress and results announced through `aria-live="polite"`; errors `role="alert"` | Jobs, Reader counter |

### 12.2 Target sizes

| Surface | Minimum | Notes |
|---|---|---|
| Studio | 32 x 32 px | Meets and exceeds the WCAG 2.2 24 px minimum; spacing 8 px between targets |
| Child mode | 64 x 64 px | 16 px spacing; choice cards 240 px |
| Reader | 44 x 44 px | Header toggle and page buttons |

### 12.3 Focus and keyboard

- One visible focus style everywhere; never removed.
- Focus moves into overlays (lettering editor, dialogs) on open and returns to the invoker on close.
- Roving tabindex for grids and lists (SheetGrid, PlotChoiceCard group, Timeline); arrow keys move within, `Tab` moves out.
- Skip link "Skip to the comic" at the top of every Studio view.
- Shortcuts are single keys only when no text field is focused, and can be disabled in Settings (WCAG 2.1.4).

### 12.4 Screen reader and language

- Live regions announce "Drawing panel 3 of 4", "Panel 3 drawn", "Strip 4 approved", and "Exported 24 pages".
- The strip is a list of panels; each panel has an accessible name with its state ("Panel 2, drawn, checked") and the lettering text is readable in the Panel Inspector.
- The document and balloon text have `lang`; right-to-left text uses `dir` and mirrors the reading order metadata.

### 12.5 Color and motion

- Status uses icon and text plus color (for example check icon + "Approved", warning icon + "Check this one").
- Reduced motion rules in section 8; `prefers-contrast: more` increases borders to 2 px and removes muted text colors.
- Dark mode contrast verified separately; lettering artwork stays light-on-white regardless.

---

## 13. Anti-patterns

These must not appear anywhere in the product.

- Text drawn by the image model anywhere in approved art.
- Controls overlaid on panel art (except lettering handles during editing).
- Blank spinners without a sketch placeholder or text status.
- Modal dialogs for routine actions. Use inline panels; modals only for export and destructive confirmations.
- Gradients and glassmorphism in UI chrome.
- Emoji in UI chrome. Lettering may contain user-typed emoji only if the font supports it; default fonts do not.
- Autoplaying sound in child mode, except when a choice is tapped.
- Infinite generation without a visible stop button.
- Tiny targets: under 32 px in Studio, under 64 px in child mode.
- Color as the only status signal. Always pair with icon and text.

Additional guardrails derived from the principles:

- More than one filled primary button in a view.
- Hiding Undo, or any destructive action without undo or confirmation.
- Cloud use without the persistent cloud badge and the first-use notice.
- Lettering colors that follow the UI theme.
- Reader external requests (fonts, scripts, analytics).
- Hype words and exclamation-heavy error copy.

---

## 14. Open questions

1. **Studio below 760 px.** Is a phone-width Studio in scope for v1, or is the minimum a tablet (768 px)? The spec collapses columns to a bottom sheet but does not require full parity.
2. **Grown-up gate.** Is a sum problem enough for child mode exit, or should classroom mode require the teacher code only? The current spec does both (10.4).
3. **Plot thumbnails on slow backends.** The default is to skip thumbnails after a configurable timeout. What is the default timeout (proposed: 8 s) and should the user be told per card?
4. **Reader child variant.** Should the Reader have a 64 px "kid" variant for early readers (larger buttons, read-aloud button wired to mr-audio-smith), or is the 44 px default enough for v1?
5. **Right-to-left comics.** Manga-ink readers may expect right-to-left page order. Do we ship an RTL flipbook flag in v1, and does it flip the lettering reading order?
6. **Font coverage.** Comic Neue and Atkinson Hyperlegible cover Latin well; which additional scripts must v1 support for lettering, and under which open licenses?
7. **Dark Reader artwork.** Pages stay light in dark mode (decided). Should the Reader chrome offer a dimmed-page option for night reading that does not alter balloons?
8. **Keyboard conflicts.** Single-letter shortcuts (`J`, `K`, `R`, `A`) conflict with some screen readers' quick keys. Do we ship a "reader-friendly" profile that moves them behind a modifier?
9. **Classroom visibility.** Can a teacher see all learner projects, or only shared ones? The join screen copy says private unless shared; the teacher view is not yet specified.
10. **Copy review.** The strings in section 9 need review by an educator for the kids-5-8 audience and by a native speaker per supported UI language (v1 is English only).
11. **Reader size budget.** The 25 KB gz budget excludes images and font subsets. Is a separate cap (for example 400 KB for fonts) worth enforcing in CI?
12. **Undo toast duration.** 6 s is the draft; some users may need longer. Should this be a setting, given that history undo is always available?
