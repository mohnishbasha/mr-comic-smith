"""SQLAlchemy 2 models for every table in ARCHITECTURE section 4.1.

The Alembic revision `0001_initial` holds the authoritative DDL (including `json_valid` and boolean
CHECKs). These models mirror its columns, keys, and indexes so services get typed access, and a unit
test compares the two so they cannot drift. Enum CHECKs are repeated here for `create_all` users.
"""

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    Text,
    UniqueConstraint,
    desc,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from comic_smith.db import base as b
from comic_smith.db.base import JSON_TEXT, Base, JsonObject, one_of
from comic_smith.db.models_book import (
    Asset,
    Book,
    CacheEntry,
    Event,
    Export,
    Job,
    Page,
    Workspace,
)

__all__ = [
    "Asset",
    "Base",
    "Bible",
    "Book",
    "Branch",
    "CacheEntry",
    "Character",
    "Event",
    "Export",
    "Job",
    "Page",
    "Panel",
    "Project",
    "Story",
    "Strip",
    "Style",
    "SuggestionSet",
    "Take",
    "Workspace",
]

_ZERO = text("0")


def _deferred_fk(target: str) -> ForeignKey:
    """Foreign key checked at commit, needed where tables reference each other in a cycle."""
    return ForeignKey(target, deferrable=True, initially="DEFERRED")


class Project(Base):
    """One row per project database."""

    __tablename__ = "project"
    __table_args__ = (one_of("audience", b.AUDIENCES),)

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    name: Mapped[str] = mapped_column(Text)
    slug: Mapped[str] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(Text)
    updated_at: Mapped[str] = mapped_column(Text)
    audience: Mapped[str] = mapped_column(Text, server_default="all-ages")
    style_id: Mapped[str | None] = mapped_column(Text, _deferred_fk("style.id"))
    schema_version: Mapped[int] = mapped_column(Integer)
    archived: Mapped[int] = mapped_column(Integer, server_default=_ZERO)
    noncommercial_opt_in: Mapped[int] = mapped_column(Integer, server_default=_ZERO)
    metadata_json: Mapped[JsonObject] = mapped_column(JSON_TEXT, server_default="{}")


class Bible(Base):
    """Versioned story bible; the highest version per project is current."""

    __tablename__ = "bible"
    __table_args__ = (UniqueConstraint("project_id", "version"),)

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    project_id: Mapped[str] = mapped_column(Text, ForeignKey("project.id", ondelete="CASCADE"))
    version: Mapped[int] = mapped_column(Integer)
    json: Mapped[JsonObject] = mapped_column(JSON_TEXT)
    created_at: Mapped[str] = mapped_column(Text)


Index("ix_bible_project_version", Bible.project_id, Bible.version.desc())


class Character(Base):
    """A cast member with an approved reference sheet."""

    __tablename__ = "character"
    __table_args__ = (
        UniqueConstraint("project_id", "slug"),
        one_of("source", b.CHARACTER_SOURCES),
        Index("ix_character_project", "project_id"),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    project_id: Mapped[str] = mapped_column(Text, ForeignKey("project.id", ondelete="CASCADE"))
    slug: Mapped[str] = mapped_column(Text)
    name: Mapped[str] = mapped_column(Text)
    source: Mapped[str] = mapped_column(Text)
    reference_json: Mapped[JsonObject | None] = mapped_column(JSON_TEXT)
    visual_dna: Mapped[str | None] = mapped_column(Text)
    sheet_asset_ids: Mapped[JsonObject] = mapped_column(JSON_TEXT, server_default="{}")
    approved: Mapped[int] = mapped_column(Integer, server_default=_ZERO)
    person_attested: Mapped[int] = mapped_column(Integer, server_default=_ZERO)
    library_ref: Mapped[str | None] = mapped_column(Text)
    approved_at: Mapped[str | None] = mapped_column(Text)
    originality_json: Mapped[JsonObject | None] = mapped_column(JSON_TEXT)
    sheet_version: Mapped[int] = mapped_column(Integer, server_default=_ZERO)


class Style(Base):
    """A style preset; project_id is NULL for built-ins."""

    __tablename__ = "style"
    __table_args__ = (Index("ix_style_project", "project_id"),)

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    project_id: Mapped[str | None] = mapped_column(Text, ForeignKey("project.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(Text)
    preset_json: Mapped[JsonObject] = mapped_column(JSON_TEXT)
    builtin: Mapped[int] = mapped_column(Integer, server_default=_ZERO)


class Branch(Base):
    """A story branch; exactly one is active per project."""

    __tablename__ = "branch"
    __table_args__ = (
        UniqueConstraint("project_id", "name"),
        Index("ux_branch_one_active", "project_id", unique=True, sqlite_where=text("active = 1")),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    project_id: Mapped[str] = mapped_column(Text, ForeignKey("project.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(Text)
    parent_branch_id: Mapped[str | None] = mapped_column(Text, ForeignKey("branch.id"))
    fork_strip_id: Mapped[str | None] = mapped_column(Text, _deferred_fk("strip.id"))
    active: Mapped[int] = mapped_column(Integer, server_default=_ZERO)


class Strip(Base):
    """One strip (up to six panels) within a branch."""

    __tablename__ = "strip"
    __table_args__ = (
        UniqueConstraint("branch_id", "idx"),
        one_of("status", b.STRIP_STATUSES),
        Index("ix_strip_status", "status"),
        Index("ix_strip_project_branch", "project_id", "branch_id", "idx"),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    project_id: Mapped[str] = mapped_column(Text, ForeignKey("project.id", ondelete="CASCADE"))
    branch_id: Mapped[str] = mapped_column(Text, ForeignKey("branch.id", ondelete="CASCADE"))
    idx: Mapped[int] = mapped_column(Integer)
    beat_json: Mapped[JsonObject] = mapped_column(JSON_TEXT)
    arc_stage: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, server_default="scripted")
    created_at: Mapped[str] = mapped_column(Text)
    approved_at: Mapped[str | None] = mapped_column(Text)


class Panel(Base):
    """A panel with its spec, selected take, and lettering."""

    __tablename__ = "panel"
    __table_args__ = (
        UniqueConstraint("strip_id", "idx"),
        Index("ix_panel_strip", "strip_id", "idx"),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    strip_id: Mapped[str] = mapped_column(Text, ForeignKey("strip.id", ondelete="CASCADE"))
    idx: Mapped[int] = mapped_column(Integer)
    spec_json: Mapped[JsonObject] = mapped_column(JSON_TEXT)
    selected_take_id: Mapped[str | None] = mapped_column(Text, _deferred_fk("take.id"))
    stale: Mapped[int] = mapped_column(Integer, server_default=_ZERO)
    lettering_json: Mapped[JsonObject | None] = mapped_column(JSON_TEXT)
    crop_json: Mapped[JsonObject | None] = mapped_column(JSON_TEXT)


class Take(Base):
    """One generated image for a panel."""

    __tablename__ = "take"
    __table_args__ = (Index("ix_take_panel", "panel_id", "created_at"), Index("ix_take_asset", "asset_id"))

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    panel_id: Mapped[str] = mapped_column(Text, ForeignKey("panel.id", ondelete="CASCADE"))
    asset_id: Mapped[str] = mapped_column(Text, ForeignKey("asset.id"))
    seed: Mapped[int | None] = mapped_column(Integer)
    backend: Mapped[str] = mapped_column(Text)
    model: Mapped[str] = mapped_column(Text)
    prompt_json: Mapped[JsonObject] = mapped_column(JSON_TEXT)
    qa_json: Mapped[JsonObject | None] = mapped_column(JSON_TEXT)
    created_at: Mapped[str] = mapped_column(Text)


class SuggestionSet(Base):
    """Four plot suggestions offered after a strip, and the choice made."""

    __tablename__ = "suggestion_set"
    __table_args__ = (
        CheckConstraint("chosen_idx IS NULL OR chosen_idx BETWEEN 0 AND 3", name="ck_chosen_idx"),
        Index("ix_suggestion_branch", "project_id", "branch_id", desc("created_at")),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    project_id: Mapped[str] = mapped_column(Text, ForeignKey("project.id", ondelete="CASCADE"))
    branch_id: Mapped[str] = mapped_column(Text, ForeignKey("branch.id", ondelete="CASCADE"))
    after_strip_id: Mapped[str | None] = mapped_column(Text, ForeignKey("strip.id"))
    json: Mapped[JsonObject] = mapped_column(JSON_TEXT)
    chosen_idx: Mapped[int | None] = mapped_column(Integer)
    custom_beat_json: Mapped[JsonObject | None] = mapped_column(JSON_TEXT)
    created_at: Mapped[str] = mapped_column(Text)


class Story(Base):
    """A finalized chapter of a branch."""

    __tablename__ = "story"
    __table_args__ = (UniqueConstraint("branch_id", "version"), Index("ix_story_project", "project_id"))

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    project_id: Mapped[str] = mapped_column(Text, ForeignKey("project.id", ondelete="CASCADE"))
    branch_id: Mapped[str] = mapped_column(Text, ForeignKey("branch.id"))
    title: Mapped[str] = mapped_column(Text)
    blurb: Mapped[str] = mapped_column(Text, server_default="")
    finalized_at: Mapped[str | None] = mapped_column(Text)
    continuity_json: Mapped[JsonObject | None] = mapped_column(JSON_TEXT)
    version: Mapped[int] = mapped_column(Integer, server_default=text("1"))
