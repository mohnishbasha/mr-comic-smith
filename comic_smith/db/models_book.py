"""Book, export, event, job, asset, workspace, and cache tables (ARCHITECTURE section 4.1).

Split from `models.py` to keep modules small; import everything through `comic_smith.db.models`.
"""

from sqlalchemy import CheckConstraint, Float, ForeignKey, Index, Integer, Text, UniqueConstraint, desc, text
from sqlalchemy.orm import Mapped, mapped_column

from comic_smith.db import base as b
from comic_smith.db.base import JSON_TEXT, Base, JsonArray, JsonObject, one_of

_ZERO = text("0")


class Book(Base):
    """A book assembled from pages."""

    __tablename__ = "book"
    __table_args__ = (Index("ix_book_project", "project_id"),)

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    project_id: Mapped[str] = mapped_column(Text, ForeignKey("project.id", ondelete="CASCADE"))
    title: Mapped[str] = mapped_column(Text)
    subtitle: Mapped[str | None] = mapped_column(Text)
    author: Mapped[str | None] = mapped_column(Text)
    year: Mapped[int | None] = mapped_column(Integer)
    language: Mapped[str] = mapped_column(Text, server_default="en")
    settings_json: Mapped[JsonObject] = mapped_column(JSON_TEXT, server_default="{}")


class Page(Base):
    """A laid-out page with slots referencing strips, panels, or assets."""

    __tablename__ = "page"
    __table_args__ = (
        one_of("kind", b.PAGE_KINDS),
        Index("ix_page_book_idx", "book_id", "idx"),
        Index("ix_page_project", "project_id"),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    project_id: Mapped[str] = mapped_column(Text, ForeignKey("project.id", ondelete="CASCADE"))
    book_id: Mapped[str | None] = mapped_column(Text, ForeignKey("book.id", ondelete="SET NULL"))
    idx: Mapped[int] = mapped_column(Integer)
    kind: Mapped[str] = mapped_column(Text)
    layout_id: Mapped[str] = mapped_column(Text)
    size: Mapped[str] = mapped_column(Text)
    slots_json: Mapped[JsonArray] = mapped_column(JSON_TEXT)
    captions_json: Mapped[JsonArray] = mapped_column(JSON_TEXT, server_default="[]")
    story_id: Mapped[str | None] = mapped_column(Text, ForeignKey("story.id"))


class Export(Base):
    """A record of one export run and the assets it produced."""

    __tablename__ = "export"
    __table_args__ = (
        one_of("target", b.EXPORT_TARGETS),
        one_of("format", b.EXPORT_FORMATS),
        Index("ix_export_project", "project_id", desc("created_at")),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    project_id: Mapped[str] = mapped_column(Text, ForeignKey("project.id", ondelete="CASCADE"))
    target: Mapped[str] = mapped_column(Text)
    format: Mapped[str] = mapped_column(Text)
    options_json: Mapped[JsonObject] = mapped_column(JSON_TEXT, server_default="{}")
    asset_ids: Mapped[JsonArray] = mapped_column(JSON_TEXT, server_default="[]")
    created_at: Mapped[str] = mapped_column(Text)
    target_id: Mapped[str | None] = mapped_column(Text)
    job_id: Mapped[str | None] = mapped_column(Text, ForeignKey("job.id"))


class Event(Base):
    """Append-only event log row (ADR-010); `undone` and `discarded` form the undo cursor."""

    __tablename__ = "event"
    __table_args__ = (
        one_of("actor", b.EVENT_ACTORS),
        Index("ix_event_project_id", "project_id", "id"),
        Index("ix_event_type", "project_id", "type"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[str] = mapped_column(Text)
    ts: Mapped[str] = mapped_column(Text)
    actor: Mapped[str] = mapped_column(Text)
    type: Mapped[str] = mapped_column(Text)
    payload_json: Mapped[JsonObject] = mapped_column(JSON_TEXT)
    inverse_json: Mapped[JsonObject | None] = mapped_column(JSON_TEXT)
    undone: Mapped[int] = mapped_column(Integer, server_default=_ZERO)
    discarded: Mapped[int] = mapped_column(Integer, server_default=_ZERO)
    workspace_id: Mapped[str | None] = mapped_column(Text)


class Job(Base):
    """A queued unit of work (ADR-011)."""

    __tablename__ = "job"
    __table_args__ = (
        one_of("status", b.JOB_STATUSES),
        one_of("worker_class", b.WORKER_CLASSES),
        CheckConstraint("priority BETWEEN 0 AND 9", name="ck_priority"),
        CheckConstraint("progress >= 0 AND progress <= 1", name="ck_progress"),
        Index("ix_job_claim", "status", "worker_class", "priority", "created_at"),
        Index("ix_job_project", "project_id", desc("created_at")),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    project_id: Mapped[str] = mapped_column(Text)
    kind: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, server_default="queued")
    priority: Mapped[int] = mapped_column(Integer, server_default=_ZERO)
    payload_json: Mapped[JsonObject] = mapped_column(JSON_TEXT)
    progress: Mapped[float] = mapped_column(Float, server_default=_ZERO)
    error_json: Mapped[JsonObject | None] = mapped_column(JSON_TEXT)
    created_at: Mapped[str] = mapped_column(Text)
    started_at: Mapped[str | None] = mapped_column(Text)
    finished_at: Mapped[str | None] = mapped_column(Text)
    attempts: Mapped[int] = mapped_column(Integer, server_default=_ZERO)
    worker_class: Mapped[str] = mapped_column(Text, server_default="text")
    cancel_requested: Mapped[int] = mapped_column(Integer, server_default=_ZERO)
    workspace_id: Mapped[str | None] = mapped_column(Text)


class Asset(Base):
    """A content-addressed file; the id is the SHA-256 hex digest of the stored bytes."""

    __tablename__ = "asset"
    __table_args__ = (
        one_of("origin", b.ASSET_ORIGINS),
        CheckConstraint("bytes >= 0", name="ck_bytes"),
        Index("ix_asset_origin", "origin"),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    mime: Mapped[str] = mapped_column(Text)
    width: Mapped[int | None] = mapped_column(Integer)
    height: Mapped[int | None] = mapped_column(Integer)
    bytes: Mapped[int] = mapped_column(Integer)
    origin: Mapped[str] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(Text)


class Workspace(Base):
    """Per-user workspace in classroom mode."""

    __tablename__ = "workspace"
    __table_args__ = (UniqueConstraint("name"),)

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    name: Mapped[str] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(Text)
    last_seen: Mapped[str] = mapped_column(Text)


class CacheEntry(Base):
    """JSON result cache for LLM and vision-QA outputs (section 9)."""

    __tablename__ = "cache_entry"
    __table_args__ = (one_of("kind", b.CACHE_KINDS), Index("ix_cache_kind", "kind", "created_at"))

    key: Mapped[str] = mapped_column(Text, primary_key=True)
    kind: Mapped[str] = mapped_column(Text)
    value_json: Mapped[JsonObject] = mapped_column(JSON_TEXT)
    created_at: Mapped[str] = mapped_column(Text)
    hits: Mapped[int] = mapped_column(Integer, server_default=_ZERO)
