"""Arc stage, progress, open threads (S1-T04)."""

from collections.abc import Iterator
from typing import Any

import pytest

from comic_smith.context import Ctx
from comic_smith.db.models import Strip
from comic_smith.errors import PrerequisiteError
from comic_smith.models import ArcDiff, ArcTemplate, Bible
from comic_smith.story.arc import (
    GAG_STAGE,
    apply_strip_approval,
    arc_progress,
    arc_state,
    fit_stage,
    is_final_stage,
    next_stage,
    open_threads,
)
from comic_smith.story.bible import bible_history, current_bible, generate_bible
from tests.unit.story_core_support import NARRATIVE, ScriptedLLM, add_strip, make_bible, story_ctx


@pytest.fixture
def ctx() -> Iterator[Ctx]:
    with story_ctx() as c:
        make_bible(c, target=8)
        yield c


def bible_of(ctx: Ctx) -> Bible:
    with ctx.project.session() as s:
        bible = current_bible(s, ctx.project_id)
    assert bible is not None
    return bible


def approve(ctx: Ctx, idx: int, **kw: Any) -> tuple[Strip, ArcDiff]:
    strip = add_strip(ctx, idx, **kw)
    with ctx.project.session() as s:
        return strip, apply_strip_approval(ctx, s, strip)


def test_story_arc_progress_updates_after_approval(ctx: Ctx) -> None:
    before = arc_state(bible_of(ctx), [])
    assert before.progress == 0.0 and before.stage is None
    strip, _ = approve(ctx, 1)
    bible = bible_of(ctx)
    with ctx.project.session() as s:
        row = s.get(Strip, strip.id)
        assert row is not None
        after = arc_state(bible, [row])
    assert after.progress > before.progress and after.strips_approved == 1


def test_story_arc_progress_computed_from_stage_index_and_target(ctx: Ctx) -> None:
    bible = bible_of(ctx)
    assert arc_progress(bible, 0) == 0.0
    assert arc_progress(bible, 4) == 0.5  # no stage: strips over target
    # stage 4 of 7 and 2 of 8 strips: mean of 4/7 and 1/4
    assert arc_progress(bible, 2, "try-2") == pytest.approx((4 / 7 + 0.25) / 2)
    assert arc_progress(bible, 2, "not-a-stage") == 0.25


def test_story_arc_threads_opened_and_closed_from_diff(ctx: Ctx) -> None:
    _, first = approve(ctx, 1, intent="twist", beat="The plug is pulled")
    assert len(first.threads_opened) == 1
    threads = bible_of(ctx).open_threads
    assert [t.id for t in threads] == ["t1"] and threads[0].opened_in_strip == 1
    _, second = approve(ctx, 2, intent="steer")
    assert second.threads_closed == ["t1"]
    bible = bible_of(ctx)
    assert open_threads(bible) == []
    assert bible.open_threads[0].closed_in_strip == 2


def test_story_arc_diff_unknown_thread_close_ignored(ctx: Ctx) -> None:
    llm = ScriptedLLM({"arc_update": [{"threads_opened": [], "threads_closed": ["t99"], "stage": "problem"}]})
    ctx.llm = llm
    _, diff = approve(ctx, 1)
    assert diff.threads_closed == ["t99"]
    with ctx.project.session() as s:
        assert len(bible_history(s, ctx.project_id)) == 1  # nothing changed, no new version


def test_story_arc_gag_a_day_has_no_stage_progress() -> None:
    with story_ctx() as ctx:
        bible = generate_bible(ctx, narrative=NARRATIVE, audience="adult", target_strips=10, arc="gag-a-day")
        assert bible.arc.stages == []
        assert arc_progress(bible, 3) == pytest.approx(0.3)
        assert arc_progress(bible, 3, "setup") == pytest.approx(0.3)
        assert fit_stage(bible, "anything") == GAG_STAGE
        assert next_stage(bible, None) == GAG_STAGE
        assert not is_final_stage(bible, GAG_STAGE)
        assert bible.arc.template is ArcTemplate.GAG_A_DAY


def test_story_arc_each_strip_tagged_with_stage(ctx: Ctx) -> None:
    stages = []
    for idx in range(1, 4):
        strip, diff = approve(ctx, idx, stage="setup")
        stages.append(diff.stage)
        with ctx.project.session() as s:
            row = s.get(Strip, strip.id)
            assert row is not None and row.arc_stage == diff.stage
    assert stages == ["setup", "setup", "problem"]
    with ctx.project.session() as s:
        ctx.events(s).undo()  # the tag is its own undoable event
        last = s.get(Strip, strip.id)
        assert last is not None and last.arc_stage == "setup"


def test_story_arc_progress_clamped_0_to_100(ctx: Ctx) -> None:
    bible = bible_of(ctx)
    assert arc_progress(bible, 100, "home") == 1.0
    assert arc_progress(bible, -5) == 0.0
    assert 0.0 <= arc_progress(bible, 8, "home") <= 1.0


def test_story_arc_unlisted_stage_from_model_is_corrected(ctx: Ctx) -> None:
    ctx.llm = ScriptedLLM(
        {"arc_update": [{"threads_opened": ["Where is Pip?"], "threads_closed": [], "stage": "bogus"}]}
    )
    _, diff = approve(ctx, 1, stage="problem")
    assert diff.stage == "problem"


def test_story_arc_final_stage_and_target_flag(ctx: Ctx) -> None:
    bible = bible_of(ctx)
    assert is_final_stage(bible, "home") and not is_final_stage(bible, "setup")
    strips = [add_strip(ctx, i, stage="setup") for i in range(1, 9)]
    assert arc_state(bible, strips).final
    assert not arc_state(bible, strips[:2]).final
    assert next_stage(bible, "home") == "home" and next_stage(bible, None) == "setup"
    assert fit_stage(bible, "zzz", "problem") == "problem" and fit_stage(bible, None) == "setup"


def test_story_arc_requires_bible() -> None:
    with story_ctx() as ctx:
        strip = add_strip(ctx, 1)
        with ctx.project.session() as s, pytest.raises(PrerequisiteError):
            apply_strip_approval(ctx, s, strip)
