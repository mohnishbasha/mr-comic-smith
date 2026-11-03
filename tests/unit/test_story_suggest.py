"""Plot suggestions (S1-T05)."""

import logging
from collections.abc import Iterator
from typing import Any

import pytest

from comic_smith.context import Ctx
from comic_smith.db.models import Branch
from comic_smith.db.models import SuggestionSet as SuggestionRow
from comic_smith.errors import AudienceBlockedError, PrerequisiteError, UsageError
from comic_smith.models import Intent, SuggestionOption, SuggestionSet
from comic_smith.story.suggest import (
    SUGGESTION_MAX_SIMILARITY,
    cosine,
    max_pairwise_similarity,
    option_text,
    suggest_next,
)
from tests.unit.story_core_support import (
    ScriptedLLM,
    VectorEmbeddings,
    add_strip,
    make_bible,
    option,
    story_ctx,
)


@pytest.fixture
def ctx() -> Iterator[Ctx]:
    with story_ctx() as c:
        make_bible(c, target=8)
        yield c


def opts(a: str = "alpha", b: str = "beta", c: str = "gamma") -> dict[str, Any]:
    return {
        "options": [
            option("continue", f"{a} one", f"{a} two three."),
            option("twist", f"{b} one", f"{b} two three."),
            option("steer", f"{c} one", f"{c} two three."),
        ],
        "end_here": None,
    }


def test_story_suggest_returns_three_distinct_intents(ctx: Ctx) -> None:
    result = suggest_next(ctx)
    assert [o.intent for o in result.options] == [Intent.CONTINUE, Intent.TWIST, Intent.STEER]
    assert result.end_here is None and result.after_strip == 0
    assert len({option_text(o) for o in result.options}) == 3
    with ctx.project.session() as s:
        row = s.query(SuggestionRow).one()
        assert SuggestionSet.model_validate(row.json) == result
        assert row.after_strip_id is None
        ctx.events(s).undo()
        assert s.query(SuggestionRow).count() == 0


def test_story_suggest_similar_options_regenerated_once() -> None:
    llm = ScriptedLLM({"suggest": [opts("same", "same", "same"), opts()]})
    vectors = [[[1.0, 0.0], [1.0, 0.0], [0.0, 1.0]], [[1.0, 0.0], [0.0, 1.0], [-1.0, 0.0]]]
    with story_ctx(llm, VectorEmbeddings(vectors)) as c:
        make_bible(c)
        result = suggest_next(c)
    assert len(llm.for_template("suggest")) == 2
    assert "retry_hint" in llm.for_template("suggest")[1][1]
    assert result.options[0].beat.startswith("alpha")


def test_story_suggest_final_stage_includes_end_here(ctx: Ctx) -> None:
    add_strip(ctx, 1, stage="home")
    result = suggest_next(ctx)
    assert result.end_here is not None
    assert result.end_here.intent is Intent.END and result.end_here.arc_stage == "home"


def test_story_suggest_target_length_reached_includes_end_here() -> None:
    with story_ctx() as c:
        make_bible(c, target=2)
        add_strip(c, 1, stage="setup")
        assert suggest_next(c).end_here is None
        add_strip(c, 2, stage="problem")
        result = suggest_next(c)
    assert result.end_here is not None and result.arc_progress > 0.5


def test_story_suggest_end_here_fallback_when_model_omits_it() -> None:
    llm = ScriptedLLM({"suggest": [opts()]})
    with story_ctx(llm) as c:
        make_bible(c, target=1)
        add_strip(c, 1, stage="home")
        result = suggest_next(c)
    assert result.end_here is not None and result.end_here.beat == "Wrap up the story here"


def test_story_suggest_option_has_required_fields(ctx: Ctx) -> None:
    add_strip(ctx, 1, stage="setup")
    for o in suggest_next(ctx).options:
        assert isinstance(o, SuggestionOption)
        assert o.beat and o.description and o.thumbnail_prompt
        assert o.arc_stage in {"setup", "problem", "try-1", "try-2", "dark-moment", "success", "home"}
        assert o.characters and all(c.startswith("ch_") for c in o.characters)


def test_story_suggest_context_includes_bible_last_three_summaries_threads() -> None:
    llm = ScriptedLLM({"suggest": [opts()]})
    with story_ctx(llm) as c:
        make_bible(c)
        for i in range(1, 6):
            add_strip(c, i, beat=f"Marker beat {i}")
        add_strip(c, 6, status="scripted", beat="Marker beat 6")
        suggest_next(c)
    system, user, temperature = llm.for_template("suggest")[0]
    assert temperature == 0.8
    assert "Marker beat 5" in user and "Marker beat 4" in user and "Marker beat 3" in user
    assert "Marker beat 2" not in user and "Marker beat 6" not in user
    assert '"working_title"' in user and '"open_threads"' in user
    assert "kids-5-8" in user and "## Audience rules" in system


def test_story_suggest_still_similar_after_regen_returns_with_warning(
    caplog: pytest.LogCaptureFixture,
) -> None:
    llm = ScriptedLLM({"suggest": [opts()]})
    same = [[1.0, 0.0], [1.0, 0.0], [1.0, 0.0]]
    with story_ctx(llm, VectorEmbeddings([same])) as c:
        make_bible(c)
        with caplog.at_level(logging.WARNING):
            result = suggest_next(c)
    assert len(llm.for_template("suggest")) == 2
    assert "distinctness_warning" in caplog.text
    assert len(result.options) == 3


def test_story_suggest_embeddings_cosine_threshold_085() -> None:
    assert SUGGESTION_MAX_SIMILARITY == 0.85
    assert cosine([1.0, 0.0], [0.0, 0.0]) == 0.0
    near = [1.0, 0.0], [0.86, (1 - 0.86**2) ** 0.5]
    far = [1.0, 0.0], [0.84, (1 - 0.84**2) ** 0.5]
    assert cosine(*near) == pytest.approx(0.86)
    assert max_pairwise_similarity([near[0], near[1], [-1.0, 0.0]]) > SUGGESTION_MAX_SIMILARITY
    assert max_pairwise_similarity([far[0], far[1], [-1.0, 0.0]]) < SUGGESTION_MAX_SIMILARITY
    assert max_pairwise_similarity([[1.0, 0.0]]) == 0.0
    # 0.84 pair: accepted without regeneration; 0.86 pair: regenerated
    for pair, calls in ((far, 1), (near, 2)):
        llm = ScriptedLLM({"suggest": [opts()]})
        vectors = [[pair[0], pair[1], [-1.0, 0.0]], [[1.0, 0.0], [0.0, 1.0], [-1.0, 0.0]]]
        with story_ctx(llm, VectorEmbeddings(vectors)) as c:
            make_bible(c)
            suggest_next(c)
        assert len(llm.for_template("suggest")) == calls


def test_story_suggest_unknown_ids_and_stage_are_corrected() -> None:
    bad = opts()
    bad["options"][0]["characters"] = ["ch_ghost"]
    bad["options"][1]["arc_stage"] = "act9"
    bad["options"] = list(reversed(bad["options"]))
    with story_ctx(ScriptedLLM({"suggest": [bad]})) as c:
        make_bible(c)
        result = suggest_next(c)
    assert [o.intent for o in result.options] == [Intent.CONTINUE, Intent.TWIST, Intent.STEER]
    assert result.options[0].characters == ["ch_puddle"]
    assert result.options[1].arc_stage == "setup"


def test_story_suggest_missing_intent_rejected() -> None:
    from comic_smith.errors import SchemaValidationError

    bad = opts()
    bad["options"][2]["intent"] = "twist"
    with story_ctx(ScriptedLLM({"suggest": [bad]})) as c:
        make_bible(c)
        with pytest.raises(SchemaValidationError):
            suggest_next(c)


def test_story_suggest_preconditions_and_moderation() -> None:
    with story_ctx() as c:
        with pytest.raises(PrerequisiteError):
            suggest_next(c)
        make_bible(c)
        with pytest.raises(UsageError):
            suggest_next(c, branch="nope")
    blocked = opts("[[blocked]]", "b", "c")
    with story_ctx(ScriptedLLM({"suggest": [blocked]})) as c:
        make_bible(c)
        with pytest.raises(AudienceBlockedError):
            suggest_next(c)


def test_story_suggest_follows_branch_parent_chain() -> None:
    with story_ctx() as c:
        make_bible(c)
        main = add_strip(c, 1, stage="setup")
        add_strip(c, 2, stage="problem", beat="Main only two")
        with c.project.session() as s:
            fork = Branch(
                id="br_fork",
                project_id=c.project_id,
                name="alt",
                parent_branch_id=main.branch_id,
                fork_strip_id=main.id,
            )
            s.add(fork)
        add_strip(c, 2, stage="try-1", branch_id="br_fork", beat="Alt two")
        llm = ScriptedLLM({"suggest": [opts()]})
        c.llm = llm
        result = suggest_next(c, branch="alt")
    user = llm.for_template("suggest")[0][1]
    assert "Alt two" in user and "Beat number 1" in user and "Main only two" not in user
    assert result.after_strip == 2
