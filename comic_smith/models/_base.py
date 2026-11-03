"""Shared base class, enums, and constrained string types for every document model.

Why one base: ADR-007 says the story engine writes JSON validated against JSON Schemas, so every
model forbids unknown keys (stricter for LLM output, and it makes `additionalProperties: false`
appear in the published schemas). Documents carry a `schema` field; pydantic's `BaseModel` has a
deprecated `schema` method, so the Python attribute is `schema_id` with the JSON alias `schema`.
"""

from enum import StrEnum
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field


class Strict(BaseModel):
    """Base for all models: no unknown keys, aliases honoured on input and output."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True, serialize_by_alias=True)


def schema_field(schema_id: str) -> Any:
    """Field for the `schema` const; each model narrows the annotation to a Literal."""
    return Field(default=schema_id, alias="schema")


Str20 = Annotated[str, Field(min_length=1, max_length=20)]
Str30 = Annotated[str, Field(min_length=1, max_length=30)]
Str60 = Annotated[str, Field(min_length=1, max_length=60)]
Str80 = Annotated[str, Field(min_length=1, max_length=80)]
Str100 = Annotated[str, Field(min_length=1, max_length=100)]
Str120 = Annotated[str, Field(min_length=1, max_length=120)]
Str160 = Annotated[str, Field(min_length=1, max_length=160)]
Str200 = Annotated[str, Field(min_length=1, max_length=200)]
Str300 = Annotated[str, Field(min_length=1, max_length=300)]
Str400 = Annotated[str, Field(min_length=1, max_length=400)]
Str2000 = Annotated[str, Field(min_length=1, max_length=2000)]
Opt200 = Annotated[str, Field(max_length=200)]
Id = Annotated[str, Field(min_length=1, max_length=64)]
HexColor = Annotated[str, Field(pattern=r"^#[0-9A-Fa-f]{6}$")]
Unit = Annotated[float, Field(ge=0.0, le=1.0)]


class Audience(StrEnum):
    """Who the story is for; drives moderation and lettering limits (FR-013)."""

    ALL_AGES = "all-ages"
    KIDS_5_8 = "kids-5-8"
    KIDS_9_12 = "kids-9-12"
    TEEN = "teen"
    ADULT = "adult"


class ArcTemplate(StrEnum):
    """Story arc templates (ARCHITECTURE 4.2; `heros-journey-lite` per Sprint 1 decision)."""

    THREE_ACT = "three-act"
    HEROS_JOURNEY_LITE = "heros-journey-lite"
    PROBLEM_TRY_TRY_SUCCEED = "problem-try-try-succeed"
    GAG_A_DAY = "gag-a-day"
    MYSTERY = "mystery"


ARC_STAGES: dict[ArcTemplate, tuple[str, ...]] = {
    ArcTemplate.PROBLEM_TRY_TRY_SUCCEED: (
        "setup",
        "problem",
        "try-1",
        "try-2",
        "dark-moment",
        "success",
        "home",
    ),
    ArcTemplate.THREE_ACT: (
        "act1-setup",
        "act1-turn",
        "act2-rise",
        "midpoint",
        "act2-fall",
        "act3-climax",
        "resolution",
    ),
    ArcTemplate.HEROS_JOURNEY_LITE: ("ordinary-world", "call", "threshold", "trials", "ordeal", "return"),
    ArcTemplate.MYSTERY: ("hook", "clue-1", "clue-2", "red-herring", "reveal", "resolution"),
    ArcTemplate.GAG_A_DAY: (),
}


class Intent(StrEnum):
    """What a suggestion option does to the plot."""

    CONTINUE = "continue"
    TWIST = "twist"
    STEER = "steer"
    END = "end"


class BeatIntent(StrEnum):
    """Intent of a stored beat: a suggestion intent or a free-text `custom` one."""

    CONTINUE = "continue"
    TWIST = "twist"
    STEER = "steer"
    END = "end"
    CUSTOM = "custom"


class BeatSource(StrEnum):
    """Where a beat came from."""

    SUGGESTION = "suggestion"
    CUSTOM = "custom"
    AUTO = "auto"


class Shot(StrEnum):
    """Camera distance (ARCHITECTURE 5.3, open question 5)."""

    EXTREME_WIDE = "extreme-wide"
    WIDE = "wide"
    MEDIUM = "medium"
    CLOSE_UP = "close-up"
    EXTREME_CLOSE_UP = "extreme-close-up"


class Angle(StrEnum):
    """Camera angle."""

    EYE_LEVEL = "eye-level"
    HIGH = "high"
    LOW = "low"
    BIRDS_EYE = "birds-eye"
    DUTCH = "dutch"


class Position(StrEnum):
    """Where a character stands in the frame."""

    LEFT = "left"
    CENTER = "center"
    RIGHT = "right"
    FOREGROUND = "foreground"
    BACKGROUND = "background"


class Facing(StrEnum):
    """Which way a character looks."""

    LEFT = "left"
    RIGHT = "right"
    CAMERA = "camera"


class DialogueType(StrEnum):
    """Balloon kinds."""

    SPEECH = "speech"
    THOUGHT = "thought"
    SHOUT = "shout"
    WHISPER = "whisper"


class BalloonSpace(StrEnum):
    """Where the image should leave room for balloons."""

    TOP = "top"
    BOTTOM = "bottom"
    LEFT = "left"
    RIGHT = "right"
    NONE = "none"


KNOWN_EXPRESSIONS = ("neutral", "happy", "sad", "surprised", "angry", "scared")


class IssueKind(StrEnum):
    """Continuity issue categories (FR-022)."""

    UNRESOLVED_THREAD = "unresolved_thread"
    VANISHED_CHARACTER = "vanished_character"
    INCONSISTENT_PROP = "inconsistent_prop"
    TONE_BREAK = "tone_break"


class Severity(StrEnum):
    """How loudly a continuity issue is shown."""

    INFO = "info"
    WARN = "warn"
    ERROR = "error"


class CharacterSource(StrEnum):
    """How a character was created."""

    PHOTO = "photo"
    TEXT = "text"
    LIBRARY = "library"


class CheckResult(StrEnum):
    """Outcome of an originality check."""

    PASS = "pass"  # noqa: S105
    BLOCKED = "blocked"
    PENDING = "pending"


class LineWeight(StrEnum):
    """Outline weight of a style preset."""

    THIN = "thin"
    MEDIUM = "medium"
    BOLD = "bold"
    NONE = "none"


class LetterCase(StrEnum):
    """Lettering case of a style preset."""

    UPPER = "upper"
    MIXED = "mixed"


class PageSize(StrEnum):
    """Page size keys (ARCHITECTURE 4.2)."""

    US_COMIC = "us-comic"
    US_LETTER = "us-letter"
    A4 = "a4"
    SQUARE = "square"
    WEB = "web"


class PageKind(StrEnum):
    """Kinds of book page."""

    STORY = "story"
    COVER = "cover"
    TITLE = "title"
    DEDICATION = "dedication"
    CAST = "cast"
    BACK = "back"
    CUSTOM = "custom"
