"""Story bible: generation, versions, edits, undo (S1-T03)."""

from collections.abc import Iterator
from typing import Any

import pytest

from comic_smith.config import Settings
from comic_smith.context import Ctx
from comic_smith.errors import PrerequisiteError, UsageError
from comic_smith.models import ARC_STAGES, ArcTemplate, Audience, Bible, CastEntry
from comic_smith.story.bible import (
    arc_templates,
    bible_history,
    current_bible,
    default_arc,
    edit_bible,
    fit_characters,
    generate_bible,
)
from comic_smith.story.prompts import load_prompt
from tests.unit.story_core_support import NARRATIVE, ScriptedLLM, make_bible, story_ctx


@pytest.fixture
def ctx() -> Iterator[Ctx]:
    with story_ctx() as c:
        yield c


def test_story_bible_target_strips_out_of_range_rejected(ctx: Ctx) -> None:
    for bad in (0, 41, -3):
        with pytest.raises(UsageError):
            generate_bible(ctx, narrative=NARRATIVE, audience="kids-5-8", target_strips=bad)
    make_bible(ctx)
    for bad in (0, 41):
        with pytest.raises(UsageError):
            edit_bible(ctx, {"arc": {"target_strips": bad}})


def test_story_bible_generate_from_narrative_fake_provider_validates(ctx: Ctx) -> None:
    bible = generate_bible(ctx, narrative=NARRATIVE, audience="kids-5-8", target_strips=6)
    assert Bible.model_validate(bible.model_dump(mode="json")) == bible
    assert bible.arc.target_strips == 6
    assert bible.working_title and bible.logline and bible.cast
    assert bible.cast[0].character_id == "ch_puddle"
    assert bible.style_id == "st_picture_book_watercolor"
    assert bible.open_threads == []


def test_story_bible_audience_values_enum_with_all_ages_default(ctx: Ctx) -> None:
    assert {a.value for a in Audience} == {"all-ages", "kids-5-8", "kids-9-12", "teen", "adult"}
    assert Settings().default_audience == "all-ages"
    with pytest.raises(UsageError):
        generate_bible(ctx, narrative=NARRATIVE, audience="toddler", target_strips=4)
    bible = generate_bible(ctx, narrative=NARRATIVE, audience="teen", target_strips=4)
    assert bible.audience is Audience.TEEN


def test_story_bible_edit_creates_new_version(ctx: Ctx) -> None:
    assert make_bible(ctx) == 1
    edited = edit_bible(ctx, {"logline": "A duck learns to float.", "setting": {"world": "a pond"}})
    assert edited.logline == "A duck learns to float."
    assert edited.setting.world == "a pond"
    with ctx.project.session() as s:
        assert current_bible(s, ctx.project_id) == edited
        history = bible_history(s, ctx.project_id)
    assert [h.version for h in history] == [1, 2]
    assert history[0].bible.logline != edited.logline


def test_story_bible_edit_is_undoable_event(ctx: Ctx) -> None:
    make_bible(ctx)
    with ctx.project.session() as s:
        original = current_bible(s, ctx.project_id)
    edit_bible(ctx, {"themes": ["kindness"]})
    with ctx.project.session() as s:
        record = ctx.events(s).undo()
        assert record is not None and record.type == "bible.updated"
        assert current_bible(s, ctx.project_id) == original
        assert [h.version for h in bible_history(s, ctx.project_id)] == [1]
        ctx.events(s).redo()
        redone = current_bible(s, ctx.project_id)
    assert redone is not None and redone.themes == ["kindness"]


def test_story_bible_undo_first_version_removes_bible(ctx: Ctx) -> None:
    make_bible(ctx)
    with ctx.project.session() as s:
        ctx.events(s).undo()
        assert current_bible(s, ctx.project_id) is None


def test_story_arc_templates_five_templates_load_with_stages() -> None:
    templates = arc_templates()
    assert set(templates) == set(ArcTemplate) and len(templates) == 5
    assert templates[ArcTemplate.PROBLEM_TRY_TRY_SUCCEED][0] == "setup"
    assert templates[ArcTemplate.GAG_A_DAY] == ()
    assert all(templates[t] for t in ArcTemplate if t is not ArcTemplate.GAG_A_DAY)
    assert templates == dict(ARC_STAGES)


def test_story_bible_default_arc_for_kids_is_problem_try_try_succeed(ctx: Ctx) -> None:
    for aud in ("kids-5-8", "kids-9-12"):
        assert default_arc(aud) is ArcTemplate.PROBLEM_TRY_TRY_SUCCEED
    for aud in ("all-ages", "teen", "adult"):
        assert default_arc(aud) is ArcTemplate.THREE_ACT
    kids = generate_bible(ctx, narrative=NARRATIVE, audience="kids-5-8", target_strips=4)
    assert kids.arc.template is ArcTemplate.PROBLEM_TRY_TRY_SUCCEED
    assert kids.arc.stages == list(ARC_STAGES[ArcTemplate.PROBLEM_TRY_TRY_SUCCEED])
    adult = generate_bible(ctx, narrative=NARRATIVE, audience="adult", target_strips=4)
    assert adult.arc.template is ArcTemplate.THREE_ACT
    mystery = generate_bible(ctx, narrative=NARRATIVE, audience="adult", target_strips=4, arc="mystery")
    assert mystery.arc.template is ArcTemplate.MYSTERY
    with pytest.raises(UsageError):
        generate_bible(ctx, narrative=NARRATIVE, audience="adult", target_strips=4, arc="epic")


def test_story_prompts_bible_template_version_recorded() -> None:
    template = load_prompt("bible")
    assert template.version == 1 and template.key == "bible@1"
    llm = ScriptedLLM({})
    with story_ctx(llm) as ctx:
        generate_bible(ctx, narrative=NARRATIVE, audience="kids-5-8", target_strips=4)
    first_system = llm.for_template("bible")[0][0]
    assert first_system.startswith("<!-- template: bible@1 -->")
    assert "## Audience rules" in first_system
    assert llm.for_template("bible")[0][2] == 0.8


def test_story_bible_empty_or_long_narrative_rejected(ctx: Ctx) -> None:
    with pytest.raises(UsageError):
        generate_bible(ctx, narrative="   ", audience="kids-5-8", target_strips=4)
    with pytest.raises(UsageError):
        generate_bible(ctx, narrative="x" * 5001, audience="kids-5-8", target_strips=4)


def test_story_bible_cast_hints_are_used_as_given(ctx: Ctx) -> None:
    hint = CastEntry(character_id="ch_real1", role="protagonist", want="a", need="b")
    bible = generate_bible(ctx, narrative=NARRATIVE, audience="all-ages", target_strips=3, cast_hints=[hint])
    assert bible.cast == [hint]


def test_story_bible_duplicate_names_get_unique_ids() -> None:
    reply: dict[str, Any] = {
        "working_title": "T",
        "logline": "L",
        "premise": "P",
        "tone": ["warm"],
        "setting": {"world": "w", "rules": []},
        "cast": [
            {"name": "Al", "role": "friend"},
            {"name": "Al", "role": "friend"},
            {"name": "!!", "role": "x"},
        ],
    }
    with story_ctx(ScriptedLLM({"bible": [reply]})) as ctx:
        bible = generate_bible(ctx, narrative=NARRATIVE, audience="adult", target_strips=2)
    assert [c.character_id for c in bible.cast] == ["ch_al", "ch_al_2", "ch_hero"]


def test_story_bible_edit_errors_and_template_change(ctx: Ctx) -> None:
    with pytest.raises(PrerequisiteError):
        edit_bible(ctx, {"themes": ["x"]})
    make_bible(ctx)
    with pytest.raises(UsageError):
        edit_bible(ctx, {"audience": "toddler"})
    changed = edit_bible(ctx, {"arc": {"template": "mystery"}})
    assert changed.arc.stages == list(ARC_STAGES[ArcTemplate.MYSTERY])
    assert changed.arc.target_strips == 8
    assert edit_bible(ctx, {"arc": {"target_strips": 5}}).arc.target_strips == 5


def test_story_bible_fit_characters_keeps_known_ids(ctx: Ctx) -> None:
    make_bible(ctx)
    with ctx.project.session() as s:
        bible = current_bible(s, ctx.project_id)
    assert bible is not None
    assert fit_characters(bible, ["nobody", "ch_pip", "ch_pip", "ch_puddle"]) == ["ch_pip", "ch_puddle"]
    assert fit_characters(bible, []) == ["ch_puddle"]
