"""Shared declarative base, enum value lists, and column helpers for the project database.

The enum lists mirror ARCHITECTURE section 4.2. They are stored as TEXT with CHECK constraints
(not native enums) so the on-disk schema stays plain SQL that any SQLite tool can read.
"""

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import JSON, CheckConstraint, MetaData
from sqlalchemy.orm import DeclarativeBase

AUDIENCES = ("all-ages", "kids-5-8", "kids-9-12", "teen", "adult")
CHARACTER_SOURCES = ("photo", "text", "library")
STRIP_STATUSES = ("scripted", "rendering", "rendered", "lettered", "approved")
PAGE_KINDS = ("story", "cover", "title", "dedication", "cast", "back", "custom")
EXPORT_TARGETS = ("page", "story", "book")
EXPORT_FORMATS = ("png", "jpg", "webp", "pdf", "cbz", "web", "strip")
EVENT_ACTORS = ("user", "auto", "agent")
JOB_STATUSES = ("queued", "running", "done", "failed", "cancelled")
WORKER_CLASSES = ("gpu", "text", "cloud_image", "export")
ASSET_ORIGINS = ("upload", "render", "export", "derived")
CACHE_KINDS = ("llm", "vision_qa", "embedding", "compiled_prompt")

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "pk": "pk_%(table_name)s",
}

# NULL (not the JSON text 'null') for Python None, matching "col IS NULL OR json_valid(col)".
JSON_TEXT = JSON(none_as_null=True)

JsonObject = dict[str, Any]
JsonArray = list[Any]


class Base(DeclarativeBase):
    """Declarative base for every project-database table."""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)


def one_of(column: str, values: tuple[str, ...]) -> CheckConstraint:
    """Build the CHECK (column IN (...)) constraint for an enum-like TEXT column."""
    quoted = ", ".join(f"'{v}'" for v in values)
    return CheckConstraint(f"{column} IN ({quoted})", name=f"ck_{column}_enum")


def utc_now_iso() -> str:
    """Current UTC time as ISO 8601 text with a Z suffix (ARCHITECTURE section 4 rules)."""
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
