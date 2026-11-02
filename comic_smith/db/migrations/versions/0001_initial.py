"""Initial schema (ARCHITECTURE section 4.1, plus the additional tables).

Revision ID: 0001
Revises:
Create Date: 2026-11-02

The DDL is frozen SQL rather than a call into the ORM models: a migration must keep producing the
same schema even after the models evolve. `event.discarded` is a Sprint 0 addition that marks a
redo tail dropped by a new mutation (section 4.4).
"""

from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

STATEMENTS: tuple[str, ...] = (
    """
CREATE TABLE project (
  id              TEXT PRIMARY KEY,
  name            TEXT NOT NULL,
  slug            TEXT NOT NULL,
  created_at      TEXT NOT NULL,
  updated_at      TEXT NOT NULL,
  audience        TEXT NOT NULL DEFAULT 'all-ages'
                  CHECK (audience IN ('all-ages','kids-5-8','kids-9-12','teen','adult')),
  style_id        TEXT NULL REFERENCES style(id) DEFERRABLE INITIALLY DEFERRED,
  schema_version  INTEGER NOT NULL,
  archived        INTEGER NOT NULL DEFAULT 0 CHECK (archived IN (0,1)),
  noncommercial_opt_in INTEGER NOT NULL DEFAULT 0 CHECK (noncommercial_opt_in IN (0,1)),
  metadata_json   TEXT NOT NULL DEFAULT '{}' CHECK (json_valid(metadata_json))
)
    """,
    """
CREATE TABLE bible (
  id          TEXT PRIMARY KEY,
  project_id  TEXT NOT NULL REFERENCES project(id) ON DELETE CASCADE,
  version     INTEGER NOT NULL CHECK (version >= 1),
  json        TEXT NOT NULL CHECK (json_valid(json)),
  created_at  TEXT NOT NULL,
  UNIQUE (project_id, version)
)
    """,
    """
CREATE INDEX ix_bible_project_version ON bible(project_id, version DESC)
    """,
    """
CREATE TABLE character (
  id              TEXT PRIMARY KEY,
  project_id      TEXT NOT NULL REFERENCES project(id) ON DELETE CASCADE,
  slug            TEXT NOT NULL,
  name            TEXT NOT NULL,
  source          TEXT NOT NULL CHECK (source IN ('photo','text','library')),
  reference_json  TEXT NULL CHECK (reference_json IS NULL OR json_valid(reference_json)),
  visual_dna      TEXT NULL,
  sheet_asset_ids TEXT NOT NULL DEFAULT '{}' CHECK (json_valid(sheet_asset_ids)),
  approved        INTEGER NOT NULL DEFAULT 0 CHECK (approved IN (0,1)),
  person_attested INTEGER NOT NULL DEFAULT 0 CHECK (person_attested IN (0,1)),
  library_ref     TEXT NULL,
  approved_at     TEXT NULL,
  originality_json TEXT NULL CHECK (originality_json IS NULL OR json_valid(originality_json)),
  sheet_version   INTEGER NOT NULL DEFAULT 0,
  UNIQUE (project_id, slug)
)
    """,
    """
CREATE INDEX ix_character_project ON character(project_id)
    """,
    """
CREATE TABLE style (
  id          TEXT PRIMARY KEY,
  project_id  TEXT NULL REFERENCES project(id) ON DELETE CASCADE,
  name        TEXT NOT NULL,
  preset_json TEXT NOT NULL CHECK (json_valid(preset_json)),
  builtin     INTEGER NOT NULL DEFAULT 0 CHECK (builtin IN (0,1))
)
    """,
    """
CREATE INDEX ix_style_project ON style(project_id)
    """,
    """
CREATE TABLE branch (
  id               TEXT PRIMARY KEY,
  project_id       TEXT NOT NULL REFERENCES project(id) ON DELETE CASCADE,
  name             TEXT NOT NULL,
  parent_branch_id TEXT NULL REFERENCES branch(id),
  fork_strip_id    TEXT NULL REFERENCES strip(id) DEFERRABLE INITIALLY DEFERRED,
  active           INTEGER NOT NULL DEFAULT 0 CHECK (active IN (0,1)),
  UNIQUE (project_id, name)
)
    """,
    """
CREATE UNIQUE INDEX ux_branch_one_active ON branch(project_id) WHERE active = 1
    """,
    """
CREATE TABLE strip (
  id          TEXT PRIMARY KEY,
  project_id  TEXT NOT NULL REFERENCES project(id) ON DELETE CASCADE,
  branch_id   TEXT NOT NULL REFERENCES branch(id) ON DELETE CASCADE,
  idx         INTEGER NOT NULL CHECK (idx >= 1),
  beat_json   TEXT NOT NULL CHECK (json_valid(beat_json)),
  arc_stage   TEXT NOT NULL,
  status      TEXT NOT NULL DEFAULT 'scripted'
              CHECK (status IN ('scripted','rendering','rendered','lettered','approved')),
  created_at  TEXT NOT NULL,
  approved_at TEXT NULL,
  UNIQUE (branch_id, idx)
)
    """,
    """
CREATE INDEX ix_strip_project_branch ON strip(project_id, branch_id, idx)
    """,
    """
CREATE INDEX ix_strip_status ON strip(status)
    """,
    """
CREATE TABLE panel (
  id               TEXT PRIMARY KEY,
  strip_id         TEXT NOT NULL REFERENCES strip(id) ON DELETE CASCADE,
  idx              INTEGER NOT NULL CHECK (idx >= 1 AND idx <= 6),
  spec_json        TEXT NOT NULL CHECK (json_valid(spec_json)),
  selected_take_id TEXT NULL REFERENCES take(id) DEFERRABLE INITIALLY DEFERRED,
  stale            INTEGER NOT NULL DEFAULT 0 CHECK (stale IN (0,1)),
  lettering_json   TEXT NULL CHECK (lettering_json IS NULL OR json_valid(lettering_json)),
  crop_json        TEXT NULL CHECK (crop_json IS NULL OR json_valid(crop_json)),
  UNIQUE (strip_id, idx)
)
    """,
    """
CREATE INDEX ix_panel_strip ON panel(strip_id, idx)
    """,
    """
CREATE TABLE take (
  id          TEXT PRIMARY KEY,
  panel_id    TEXT NOT NULL REFERENCES panel(id) ON DELETE CASCADE,
  asset_id    TEXT NOT NULL REFERENCES asset(id),
  seed        INTEGER NULL,
  backend     TEXT NOT NULL,
  model       TEXT NOT NULL,
  prompt_json TEXT NOT NULL CHECK (json_valid(prompt_json)),
  qa_json     TEXT NULL CHECK (qa_json IS NULL OR json_valid(qa_json)),
  created_at  TEXT NOT NULL
)
    """,
    """
CREATE INDEX ix_take_panel ON take(panel_id, created_at)
    """,
    """
CREATE INDEX ix_take_asset ON take(asset_id)
    """,
    """
CREATE TABLE suggestion_set (
  id                TEXT PRIMARY KEY,
  project_id        TEXT NOT NULL REFERENCES project(id) ON DELETE CASCADE,
  branch_id         TEXT NOT NULL REFERENCES branch(id) ON DELETE CASCADE,
  after_strip_id    TEXT NULL REFERENCES strip(id),
  json              TEXT NOT NULL CHECK (json_valid(json)),
  chosen_idx        INTEGER NULL CHECK (chosen_idx IS NULL OR chosen_idx BETWEEN 0 AND 3),
  custom_beat_json  TEXT NULL CHECK (custom_beat_json IS NULL OR json_valid(custom_beat_json)),
  created_at        TEXT NOT NULL
)
    """,
    """
CREATE INDEX ix_suggestion_branch ON suggestion_set(project_id, branch_id, created_at DESC)
    """,
    """
CREATE TABLE story (
  id              TEXT PRIMARY KEY,
  project_id      TEXT NOT NULL REFERENCES project(id) ON DELETE CASCADE,
  branch_id       TEXT NOT NULL REFERENCES branch(id),
  title           TEXT NOT NULL,
  blurb           TEXT NOT NULL DEFAULT '',
  finalized_at    TEXT NULL,
  continuity_json TEXT NULL CHECK (continuity_json IS NULL OR json_valid(continuity_json)),
  version         INTEGER NOT NULL DEFAULT 1 CHECK (version >= 1),
  UNIQUE (branch_id, version)
)
    """,
    """
CREATE INDEX ix_story_project ON story(project_id)
    """,
    """
CREATE TABLE book (
  id            TEXT PRIMARY KEY,
  project_id    TEXT NOT NULL REFERENCES project(id) ON DELETE CASCADE,
  title         TEXT NOT NULL,
  subtitle      TEXT NULL,
  author        TEXT NULL,
  year          INTEGER NULL,
  language      TEXT NOT NULL DEFAULT 'en',
  settings_json TEXT NOT NULL DEFAULT '{}' CHECK (json_valid(settings_json))
)
    """,
    """
CREATE INDEX ix_book_project ON book(project_id)
    """,
    """
CREATE TABLE page (
  id            TEXT PRIMARY KEY,
  project_id    TEXT NOT NULL REFERENCES project(id) ON DELETE CASCADE,
  book_id       TEXT NULL REFERENCES book(id) ON DELETE SET NULL,
  idx           INTEGER NOT NULL CHECK (idx >= 1),
  kind          TEXT NOT NULL CHECK (kind IN ('story','cover','title','dedication','cast','back','custom')),
  layout_id     TEXT NOT NULL,
  size          TEXT NOT NULL,
  slots_json    TEXT NOT NULL CHECK (json_valid(slots_json)),
  captions_json TEXT NOT NULL DEFAULT '[]' CHECK (json_valid(captions_json)),
  story_id      TEXT NULL REFERENCES story(id)
)
    """,
    """
CREATE INDEX ix_page_book_idx ON page(book_id, idx)
    """,
    """
CREATE INDEX ix_page_project ON page(project_id)
    """,
    """
CREATE TABLE export (
  id           TEXT PRIMARY KEY,
  project_id   TEXT NOT NULL REFERENCES project(id) ON DELETE CASCADE,
  target       TEXT NOT NULL CHECK (target IN ('page','story','book')),
  format       TEXT NOT NULL CHECK (format IN ('png','jpg','webp','pdf','cbz','web','strip')),
  options_json TEXT NOT NULL DEFAULT '{}' CHECK (json_valid(options_json)),
  asset_ids    TEXT NOT NULL DEFAULT '[]' CHECK (json_valid(asset_ids)),
  created_at   TEXT NOT NULL,
  target_id    TEXT NULL,
  job_id       TEXT NULL REFERENCES job(id)
)
    """,
    """
CREATE INDEX ix_export_project ON export(project_id, created_at DESC)
    """,
    """
CREATE TABLE event (
  id           INTEGER PRIMARY KEY AUTOINCREMENT,
  project_id   TEXT NOT NULL,
  ts           TEXT NOT NULL,
  actor        TEXT NOT NULL CHECK (actor IN ('user','auto','agent')),
  type         TEXT NOT NULL,
  payload_json TEXT NOT NULL CHECK (json_valid(payload_json)),
  inverse_json TEXT NULL CHECK (inverse_json IS NULL OR json_valid(inverse_json)),
  undone       INTEGER NOT NULL DEFAULT 0 CHECK (undone IN (0,1)),
  discarded    INTEGER NOT NULL DEFAULT 0 CHECK (discarded IN (0,1)),
  workspace_id TEXT NULL
)
    """,
    """
CREATE INDEX ix_event_project_id ON event(project_id, id)
    """,
    """
CREATE INDEX ix_event_type ON event(project_id, type)
    """,
    """
CREATE TABLE job (
  id            TEXT PRIMARY KEY,
  project_id    TEXT NOT NULL,
  kind          TEXT NOT NULL,
  status        TEXT NOT NULL DEFAULT 'queued'
                CHECK (status IN ('queued','running','done','failed','cancelled')),
  priority      INTEGER NOT NULL DEFAULT 0 CHECK (priority BETWEEN 0 AND 9),
  payload_json  TEXT NOT NULL CHECK (json_valid(payload_json)),
  progress      REAL NOT NULL DEFAULT 0 CHECK (progress >= 0 AND progress <= 1),
  error_json    TEXT NULL CHECK (error_json IS NULL OR json_valid(error_json)),
  created_at    TEXT NOT NULL,
  started_at    TEXT NULL,
  finished_at   TEXT NULL,
  attempts      INTEGER NOT NULL DEFAULT 0,
  worker_class  TEXT NOT NULL DEFAULT 'text'
                CHECK (worker_class IN ('gpu','text','cloud_image','export')),
  cancel_requested INTEGER NOT NULL DEFAULT 0 CHECK (cancel_requested IN (0,1)),
  workspace_id  TEXT NULL
)
    """,
    """
CREATE INDEX ix_job_claim ON job(status, worker_class, priority, created_at)
    """,
    """
CREATE INDEX ix_job_project ON job(project_id, created_at DESC)
    """,
    """
CREATE TABLE asset (
  id         TEXT PRIMARY KEY,
  mime       TEXT NOT NULL,
  width      INTEGER NULL,
  height     INTEGER NULL,
  bytes      INTEGER NOT NULL CHECK (bytes >= 0),
  origin     TEXT NOT NULL CHECK (origin IN ('upload','render','export','derived')),
  created_at TEXT NOT NULL
)
    """,
    """
CREATE INDEX ix_asset_origin ON asset(origin)
    """,
    """
CREATE TABLE workspace (
  id         TEXT PRIMARY KEY,
  name       TEXT NOT NULL,
  created_at TEXT NOT NULL,
  last_seen  TEXT NOT NULL,
  UNIQUE (name)
)
    """,
    """
CREATE TABLE cache_entry (
  key        TEXT PRIMARY KEY,
  kind       TEXT NOT NULL CHECK (kind IN ('llm','vision_qa','embedding','compiled_prompt')),
  value_json TEXT NOT NULL CHECK (json_valid(value_json)),
  created_at TEXT NOT NULL,
  hits       INTEGER NOT NULL DEFAULT 0
)
    """,
    """
CREATE INDEX ix_cache_kind ON cache_entry(kind, created_at)
    """,
)

TABLES_DROP_ORDER: tuple[str, ...] = (
    "cache_entry",
    "workspace",
    "asset",
    "job",
    "event",
    "export",
    "page",
    "book",
    "story",
    "suggestion_set",
    "take",
    "panel",
    "strip",
    "branch",
    "style",
    "character",
    "bible",
    "project",
)


def upgrade() -> None:
    """Create every table and index."""
    for statement in STATEMENTS:
        op.execute(statement)


def downgrade() -> None:
    """Drop everything; children first so foreign keys never dangle."""
    op.execute("PRAGMA defer_foreign_keys = ON")
    for table in TABLES_DROP_ORDER:
        op.execute(f'DROP TABLE IF EXISTS "{table}"')
