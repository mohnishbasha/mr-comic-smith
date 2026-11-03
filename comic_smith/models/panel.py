"""Panel spec, strip script, continuity report, moderation verdict (ARCHITECTURE 5.3, 5.7)."""

from datetime import datetime
from typing import Literal, Self

from pydantic import Field, model_validator

from comic_smith.models._base import (
    Angle,
    BalloonSpace,
    DialogueType,
    Facing,
    Id,
    IssueKind,
    Position,
    Severity,
    Shot,
    Str20,
    Str30,
    Str60,
    Str80,
    Str120,
    Str160,
    Str200,
    Str300,
    Strict,
    schema_field,
)

PANEL_SCHEMA = "comic-smith/panel@1"
CONTINUITY_SCHEMA = "comic-smith/continuity@1"


class PanelCharacter(Strict):
    """A character placed in a panel; `expression` is one of the known six or short free text."""

    id: Id
    position: Position
    pose: Str120
    expression: Str30
    facing: Facing


class Dialogue(Strict):
    """One balloon of text spoken by a cast member."""

    speaker: Id
    type: DialogueType
    text: Str200


class Sfx(Strict):
    """A sound effect word, optionally near a character."""

    text: Str20
    near: Id | None = None


class PanelSpec(Strict):
    """Everything the renderer and lettering engine need for one panel (`comic-smith/panel@1`)."""

    schema_id: Literal["comic-smith/panel@1"] = schema_field(PANEL_SCHEMA)
    idx: int = Field(ge=1, le=6)
    shot: Shot
    angle: Angle
    setting: Str300
    characters: list[PanelCharacter] = Field(max_length=5)
    action: Str300
    dialogue: list[Dialogue]
    caption: Str160 | None
    sfx: list[Sfx]
    continuity: list[Str160] = Field(max_length=8)
    mood: Str60
    balloon_space: BalloonSpace


class StripScript(Strict):
    """The LLM's script for one strip: 1 to 6 panels numbered from 1."""

    panels: list[PanelSpec] = Field(min_length=1, max_length=6)

    @model_validator(mode="after")
    def _consecutive_idx(self) -> Self:
        """Panel `idx` must match its position, since it becomes `panel.idx`."""
        if [p.idx for p in self.panels] != list(range(1, len(self.panels) + 1)):
            raise ValueError("panel idx values must be 1..n in order")
        return self


class ContinuityIssue(Strict):
    """One problem found by the finalize check."""

    id: Id
    kind: IssueKind
    severity: Severity
    strip: int | None = None
    text: Str300
    thread_id: Id | None = None
    character_id: Id | None = None
    panel_idx: int | None = Field(default=None, ge=1, le=6)


class ContinuityReport(Strict):
    """Finalize report stored in `story.continuity_json` (`comic-smith/continuity@1`)."""

    schema_id: Literal["comic-smith/continuity@1"] = schema_field(CONTINUITY_SCHEMA)
    story_id: Id
    checked_at: datetime
    issues: list[ContinuityIssue]
    titles: list[Str80] = Field(min_length=3, max_length=3)
    blurb: Str160


class ModerationVerdict(Strict):
    """Result of a safety check (ADR-013); `rule` names the triggering rule when blocked."""

    allowed: bool
    category: Str60 | None = None
    reason: Str200 | None = None
    rule: Str60 | None = None
