"""Beats: normalize free text, convert a suggestion, edit a suggestion (S1-T06, FR-012).

Nothing here writes a strip. `normalize_beat` returns the structured beat for the user to confirm;
the writer stores it when the strip is made.
"""

from typing import Any

from pydantic import Field, ValidationError

from comic_smith.backends.llm.base import TEMPERATURE_DETERMINISTIC
from comic_smith.context import Ctx
from comic_smith.errors import PrerequisiteError, UsageError
from comic_smith.models import Beat, BeatIntent, BeatSource, SuggestionOption
from comic_smith.models._base import Id, Str30, Str100, Str300, Strict
from comic_smith.story._history import approved_strips
from comic_smith.story._llm import call_model
from comic_smith.story._wire import context_block
from comic_smith.story.arc import arc_state, fit_stage
from comic_smith.story.bible import current_bible, fit_characters, project_audience
from comic_smith.story.moderation import check_texts
from comic_smith.story.prompts import wrap_untrusted

MAX_BEAT_CHARS = 2000
EDITABLE = {"beat", "description", "arc_stage", "characters", "panels"}


class BeatDraft(Strict):
    """What the LLM returns for a free-text beat."""

    beat: Str100
    description: Str300
    arc_stage: Str30
    characters: list[Id] = Field(default_factory=list, max_length=12)
    panels: int = Field(default=4, ge=1, le=6)


def normalize_beat(ctx: Ctx, text: str, *, branch: str = "main") -> Beat:
    """Turn the author's own words into a structured beat to show for confirmation.

    Raises:
        UsageError: Empty or too long text.
        PrerequisiteError: No bible yet.
        OriginalityBlockedError, AudienceBlockedError: The text or the beat failed a guard.
    """
    cleaned = text.strip()
    if not cleaned:
        raise UsageError("Write what happens next, in your own words.")
    if len(cleaned) > MAX_BEAT_CHARS:
        raise UsageError("That idea is a bit long. Keep it under 2,000 characters.")
    with ctx.project.session(readonly=True) as s:
        bible = current_bible(s, ctx.project_id)
        if bible is None:
            raise PrerequisiteError("There is no story bible yet.", hint="Create the story first.")
        state = arc_state(bible, approved_strips(s, ctx.project_id, branch))
    facts = {
        "audience": bible.audience.value,
        "cast": [c.character_id for c in bible.cast],
        "stages": bible.arc.stages,
        "arc_stage": state.stage,
        "logline": bible.logline,
    }
    user = f"{context_block(facts)}\n\n{wrap_untrusted('author idea', cleaned)}"
    draft = call_model(
        ctx,
        "beat_normalize",
        BeatDraft,
        audience=bible.audience.value,
        user=user,
        temperature=TEMPERATURE_DETERMINISTIC,
    )
    check_texts(ctx, "beat", [cleaned, draft.beat, draft.description], bible.audience.value)
    return Beat(
        source=BeatSource.CUSTOM,
        intent=BeatIntent.CUSTOM,
        beat=draft.beat,
        description=draft.description,
        arc_stage=fit_stage(bible, draft.arc_stage, state.stage),
        characters=fit_characters(bible, draft.characters),
        panels=draft.panels,
        original_text=cleaned,
    )


def beat_from_option(option: SuggestionOption) -> Beat:
    """The beat for a picked suggestion, unchanged."""
    return Beat(
        source=BeatSource.SUGGESTION,
        intent=BeatIntent(option.intent.value),
        beat=option.beat,
        description=option.description,
        arc_stage=option.arc_stage,
        characters=list(option.characters),
        panels=4,
        original_text=None,
    )


def edit_suggestion(option: SuggestionOption, changes: dict[str, Any], *, ctx: Ctx | None = None) -> Beat:
    """Beat from `option` with `changes` applied; every field not named stays as it was.

    Editable keys: beat, description, arc_stage, characters, panels. When `ctx` is given the edited
    text is moderated for the project's audience.

    Raises:
        UsageError: Unknown key or an invalid value.
    """
    unknown = sorted(set(changes) - EDITABLE)
    if unknown:
        raise UsageError(
            f"You can edit {', '.join(sorted(EDITABLE))}, not {', '.join(unknown)}.",
            hint="Remove the other fields and try again.",
        )
    base = beat_from_option(option).model_dump(mode="json")
    try:
        edited = Beat.model_validate({**base, **changes})
    except ValidationError as e:
        raise UsageError(
            f"That change does not fit a beat ({e.errors()[0]['msg']}).", hint="Check the value."
        ) from e
    if ctx is not None:
        with ctx.project.session(readonly=True) as s:
            audience = project_audience(ctx, s)
        check_texts(ctx, "beat", [edited.beat, edited.description], audience)
    return edited
