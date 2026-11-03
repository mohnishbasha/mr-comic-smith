"""Story documents: bible, suggestions, beat, arc diff (ARCHITECTURE 5.1, 5.2, 5.6)."""

from typing import Literal, Self

from pydantic import Field, model_validator

from comic_smith.models._base import (
    ARC_STAGES,
    ArcTemplate,
    Audience,
    BeatIntent,
    BeatSource,
    Id,
    Intent,
    Opt200,
    Str30,
    Str60,
    Str100,
    Str120,
    Str200,
    Str300,
    Str400,
    Str2000,
    Strict,
    schema_field,
)

BIBLE_SCHEMA = "comic-smith/bible@1"
SUGGESTIONS_SCHEMA = "comic-smith/suggestions@1"
BEAT_SCHEMA = "comic-smith/beat@1"
SUGGESTION_ORDER = (Intent.CONTINUE, Intent.TWIST, Intent.STEER)


class Setting(Strict):
    """Where and in what world the story happens."""

    world: Str300
    rules: list[Str200] = Field(default_factory=list, max_length=10)


class CastEntry(Strict):
    """One character's role in the story; `character_id` must exist in the character table."""

    character_id: Id
    role: Str30
    want: Opt200 = ""
    need: Opt200 = ""


class Arc(Strict):
    """Arc template, length, and stage list."""

    template: ArcTemplate
    target_strips: int = Field(ge=1, le=40)
    stages: list[Str30] = Field(default_factory=list, max_length=12)

    @model_validator(mode="after")
    def _stages_match_template(self) -> Self:
        """Fill the template's stages when omitted; reject a list that differs from it.

        Why: stage lists are data owned by the template (ARCHITECTURE 5.1), so a bible whose stages
        drifted from its template would break arc progress maths later.
        """
        expected = list(ARC_STAGES[self.template])
        if not self.stages:
            self.stages = expected
        elif self.stages != expected:
            raise ValueError(f"stages must equal the {self.template.value} template stages: {expected}")
        return self


class OpenThread(Strict):
    """A plot thread that has been raised and not yet paid off."""

    id: Id
    text: Str200
    opened_in_strip: int = Field(ge=1)
    closed_in_strip: int | None = Field(default=None, ge=1)


class Bible(Strict):
    """The story bible (`comic-smith/bible@1`)."""

    schema_id: Literal["comic-smith/bible@1"] = schema_field(BIBLE_SCHEMA)
    working_title: Str120
    logline: Str300
    premise: Str2000
    audience: Audience
    tone: list[Str30] = Field(min_length=1, max_length=6)
    setting: Setting
    cast: list[CastEntry] = Field(min_length=1, max_length=12)
    themes: list[Str60] = Field(default_factory=list, max_length=8)
    arc: Arc
    open_threads: list[OpenThread] = Field(default_factory=list)
    style_id: Id

    @model_validator(mode="after")
    def _unique_threads(self) -> Self:
        """Thread ids are referenced by diffs and continuity issues, so they must be unique."""
        ids = [t.id for t in self.open_threads]
        if len(ids) != len(set(ids)):
            raise ValueError("open_threads ids must be unique")
        return self


class SuggestionOption(Strict):
    """One plot option the user can pick."""

    intent: Intent
    beat: Str100
    description: Str300
    arc_stage: Str30
    characters: list[Id] = Field(min_length=1, max_length=6)
    thumbnail_prompt: Str400


class SuggestionSet(Strict):
    """Three options (continue, twist, steer) plus an optional `end` option (FR-011)."""

    schema_id: Literal["comic-smith/suggestions@1"] = schema_field(SUGGESTIONS_SCHEMA)
    after_strip: int | None = Field(ge=0)
    arc_progress: float = Field(ge=0.0, le=1.0)
    options: list[SuggestionOption] = Field(min_length=3, max_length=3)
    end_here: SuggestionOption | None

    @model_validator(mode="after")
    def _intents_in_order(self) -> Self:
        """Options are exactly continue, twist, steer in that order; `end_here` has intent end."""
        if tuple(o.intent for o in self.options) != SUGGESTION_ORDER:
            raise ValueError("options must have intents continue, twist, steer in that order")
        if self.end_here is not None and self.end_here.intent != Intent.END:
            raise ValueError("end_here must have intent end")
        return self


class Beat(Strict):
    """A chosen or normalized story beat (`comic-smith/beat@1`)."""

    schema_id: Literal["comic-smith/beat@1"] = schema_field(BEAT_SCHEMA)
    source: BeatSource
    intent: BeatIntent
    beat: Str100
    description: Str300
    arc_stage: Str30
    characters: list[Id]
    panels: int = Field(default=4, ge=1, le=6)
    original_text: str | None = None


class ArcDiff(Strict):
    """Structured result of the post-approval arc update (FR-010)."""

    threads_opened: list[Str200] = Field(default_factory=list)
    threads_closed: list[Id] = Field(default_factory=list)
    stage: Str30
