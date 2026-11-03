"""API-facing records returned by services (not stored documents, so no `schema` field)."""

from datetime import datetime
from pathlib import Path

from comic_smith.models._base import Audience, Strict


class ProjectInfo(Strict):
    """A project as the API, CLI, and Studio see it."""

    id: str
    name: str
    slug: str
    audience: Audience
    style_id: str | None
    created_at: str
    path: Path
    archived: bool = False


class StoryInfo(Strict):
    """A story (one finalized or in-progress branch run) as the API sees it."""

    id: str
    project_id: str
    branch_id: str
    title: str
    blurb: str = ""
    version: int = 1
    finalized_at: datetime | None = None


class EventInfo(Strict):
    """One history entry (payloads are left out: they can be large and are internal)."""

    id: int
    type: str
    actor: str
    ts: str
    undone: bool = False
