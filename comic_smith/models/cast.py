"""Character and style preset documents (ARCHITECTURE 5.4, 5.5)."""

from datetime import datetime
from typing import Any, Literal

from pydantic import Field

from comic_smith.models._base import (
    Audience,
    CharacterSource,
    CheckResult,
    HexColor,
    Id,
    LetterCase,
    LineWeight,
    Str30,
    Str60,
    Str200,
    Strict,
    schema_field,
)

CHARACTER_SCHEMA = "comic-smith/character@1"
STYLE_SCHEMA = "comic-smith/style@1"


class CharacterReference(Strict):
    """User-editable description extracted from a photo or text (FR-003)."""

    subject: Str200
    palette: list[HexColor] = Field(min_length=1, max_length=8)
    features: list[Str200] = Field(min_length=1, max_length=12)
    accessories: list[Str200] = Field(default_factory=list, max_length=8)


class SheetViews(Strict):
    """Asset ids (sha256) of the three turnaround views; None until generated."""

    front: str | None = None
    side: str | None = None
    three_quarter: str | None = None


class SheetExpressions(Strict):
    """Asset ids of the six expression images; None until generated."""

    neutral: str | None = None
    happy: str | None = None
    sad: str | None = None
    surprised: str | None = None
    angry: str | None = None
    scared: str | None = None


class CharacterSheet(Strict):
    """The reference sheet assets."""

    views: SheetViews = Field(default_factory=SheetViews)
    expressions: SheetExpressions = Field(default_factory=SheetExpressions)
    composed: str | None = None


class Attestation(Strict):
    """Person-likeness attestation, required when the reference contains a person (FR-007)."""

    person_detected: bool
    right_to_use_likeness: bool
    attested_at: datetime | None = None


class Originality(Strict):
    """Originality guard outcome (ADR-013)."""

    denylist: CheckResult = CheckResult.PENDING
    resemblance: CheckResult = CheckResult.PENDING
    rule: str | None = None
    checked_at: datetime | None = None


class Character(Strict):
    """A cast member (`comic-smith/character@1`)."""

    schema_id: Literal["comic-smith/character@1"] = schema_field(CHARACTER_SCHEMA)
    id: Id = Field(pattern=r"^ch_")
    slug: Id
    name: Str60
    source: CharacterSource
    reference: CharacterReference | None = None
    visual_dna: str | None = Field(default=None, min_length=50, max_length=800)
    sheet: CharacterSheet = Field(default_factory=CharacterSheet)
    approved_at: datetime | None = None
    attestation: Attestation | None = None
    originality: Originality = Field(default_factory=Originality)


class StyleLettering(Strict):
    """Lettering defaults of a style: case and font registry ids."""

    case: LetterCase
    font: Str30
    caption_font: Str30


class StylePreset(Strict):
    """An art style preset (`comic-smith/style@1`)."""

    schema_id: Literal["comic-smith/style@1"] = schema_field(STYLE_SCHEMA)
    id: Id = Field(pattern=r"^st_")
    name: Str60
    description: str = Field(default="", max_length=200)
    audiences: list[Audience] = Field(default_factory=lambda: list(Audience))
    positive_tokens: list[Str60] = Field(min_length=1, max_length=20)
    negative_tokens: list[Str60] = Field(min_length=1, max_length=20)
    palette_hints: list[HexColor] = Field(default_factory=list, max_length=8)
    line_weight: LineWeight
    photoreal: bool
    lettering: StyleLettering
    backend_params: dict[str, dict[str, Any]] = Field(default_factory=dict)
    reference_assets: list[Id] = Field(default_factory=list, max_length=2)
