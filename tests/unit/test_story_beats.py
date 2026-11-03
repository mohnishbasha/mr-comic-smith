"""Beat normalization and suggestion edits (S1-T06)."""

from collections.abc import Iterator

import pytest

from comic_smith.context import Ctx
from comic_smith.errors import AudienceBlockedError, OriginalityBlockedError, PrerequisiteError, UsageError
from comic_smith.models import Beat, BeatIntent, BeatSource, Intent, SuggestionOption
from comic_smith.story.beats import beat_from_option, edit_suggestion, normalize_beat
from tests.unit.story_core_support import ScriptedLLM, add_strip, make_bible, story_ctx


@pytest.fixture
def ctx() -> Iterator[Ctx]:
    with story_ctx() as c:
        make_bible(c)
        yield c


def an_option() -> SuggestionOption:
    return SuggestionOption(
        intent=Intent.TWIST,
        beat="The plug is pulled",
        description="A whirlpool forms. Pip is pulled toward the drain.",
        arc_stage="problem",
        characters=["ch_puddle", "ch_pip"],
        thumbnail_prompt="whirlpool in a bathtub",
    )


def test_story_beat_normalize_free_text_to_beat_structure(ctx: Ctx) -> None:
    add_strip(ctx, 1, stage="setup")
    beat = normalize_beat(ctx, "  Puddle finds a soap dish. It could be a raft!  ")
    assert isinstance(beat, Beat)
    assert beat.source is BeatSource.CUSTOM and beat.intent is BeatIntent.CUSTOM
    assert beat.original_text == "Puddle finds a soap dish. It could be a raft!"
    assert beat.beat and beat.description and beat.panels == 4
    assert beat.characters == ["ch_puddle"]
    assert beat.arc_stage == "problem"


def test_story_beat_normalized_returned_for_confirmation() -> None:
    llm = ScriptedLLM({})
    with story_ctx(llm) as c:
        make_bible(c)
        beat = normalize_beat(c, "Pip hides in the sponge.")
        with c.project.session(readonly=True) as s:
            from comic_smith.db.models import Strip

            assert s.query(Strip).count() == 0  # nothing is written until the user accepts
    system, user, temperature = llm.for_template("beat_normalize")[0]
    assert temperature == 0.0 and "<<<BEGIN author idea>>>" in user and "## Audience rules" in system
    assert beat.characters == ["ch_pip"]


def test_story_beat_edit_suggestion_keeps_other_fields() -> None:
    option = an_option()
    beat = edit_suggestion(option, {"beat": "The plug is pulled by a cat"})
    assert beat.beat == "The plug is pulled by a cat"
    assert (beat.description, beat.arc_stage, beat.characters) == (
        option.description,
        option.arc_stage,
        option.characters,
    )
    assert beat.source is BeatSource.SUGGESTION and beat.intent is BeatIntent.TWIST
    assert edit_suggestion(option, {"panels": 3}).panels == 3
    plain = beat_from_option(option)
    assert plain.beat == option.beat and plain.original_text is None and plain.panels == 4


def test_story_beat_empty_text_rejected(ctx: Ctx) -> None:
    for text in ("", "   \n"):
        with pytest.raises(UsageError):
            normalize_beat(ctx, text)
    with pytest.raises(UsageError):
        normalize_beat(ctx, "x" * 2001)


def test_story_beat_requires_bible_and_passes_guards() -> None:
    with story_ctx() as c, pytest.raises(PrerequisiteError):
        normalize_beat(c, "Anything")
    with story_ctx() as c:
        make_bible(c)
        with pytest.raises(OriginalityBlockedError):
            normalize_beat(c, "Puddle meets Mickey Mouse.")
        with pytest.raises(AudienceBlockedError):
            normalize_beat(c, "Puddle is [[blocked]] today.")


def test_story_beat_edit_suggestion_rejects_unknown_and_invalid_changes(ctx: Ctx) -> None:
    option = an_option()
    with pytest.raises(UsageError):
        edit_suggestion(option, {"intent": "end"})
    with pytest.raises(UsageError):
        edit_suggestion(option, {"panels": 9})
    assert edit_suggestion(option, {"description": "Calm."}, ctx=ctx).description == "Calm."
    with pytest.raises(OriginalityBlockedError):
        edit_suggestion(option, {"beat": "Batman arrives"}, ctx=ctx)
