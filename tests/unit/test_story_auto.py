"""S1-T11: auto mode policy and loop (FR-026), offline with the fake providers."""

import pytest

from comic_smith.errors import PrerequisiteError, UsageError
from comic_smith.events import EventLog
from comic_smith.models import Intent, SuggestionOption, SuggestionSet
from comic_smith.story import auto, fake_responses, strips
from comic_smith.story.make import make_strip
from comic_smith.story.suggest import suggest_next
from tests.unit.story_core_support import make_bible, story_ctx


@pytest.fixture(autouse=True)
def _responders() -> None:
    fake_responses.ensure_registered()  # test_llm_fake clears the registry


def _option(intent: Intent) -> SuggestionOption:
    return SuggestionOption(
        intent=intent,
        beat=f"{intent.value} beat",
        description="Something happens.",
        arc_stage="setup",
        characters=["ch_a"],
        thumbnail_prompt="a scene",
    )


def _set(*, end: bool = False) -> SuggestionSet:
    return SuggestionSet(
        after_strip=0,
        arc_progress=0.0,
        options=[_option(Intent.CONTINUE), _option(Intent.TWIST), _option(Intent.STEER)],
        end_here=_option(Intent.END) if end else None,
    )


def test_balanced_policy_rotates_continue_steer_twist() -> None:
    picks = [auto.choose_pick("balanced", _set(), n, 40) for n in range(6)]
    assert picks == [1, 3, 2, 1, 3, 2]


def test_steer_policy_prefers_steer() -> None:
    picks = [auto.choose_pick("steer", _set(), n, 40) for n in range(6)]
    assert picks.count(3) == 4 and picks.count(2) == 0


def test_twist_policy_prefers_twist() -> None:
    picks = [auto.choose_pick("twist", _set(), n, 40) for n in range(6)]
    assert picks.count(2) == 4 and picks.count(3) == 0


def test_end_is_picked_when_offered_and_this_strip_reaches_target() -> None:
    assert auto.choose_pick("balanced", _set(end=True), 7, 8) == "end"
    assert auto.choose_pick("balanced", _set(end=True), 3, 8) != "end"
    assert auto.choose_pick("balanced", _set(end=False), 7, 8) in {1, 2, 3}


def test_unknown_policy_is_a_usage_error() -> None:
    with pytest.raises(UsageError, match="not an auto policy"):
        auto.check_policy("wild")


def test_run_auto_stops_at_target_and_records_actor_auto() -> None:
    with story_ctx() as ctx:
        make_bible(ctx, target=3)
        made = auto.run_auto(ctx, policy="balanced")
        assert [m.idx for m in made] == [1, 2, 3]
        assert all(m.status == "approved" and m.panels for m in made)
        assert ctx.actor == "user"
        with ctx.project.session(readonly=True) as s:
            events = EventLog(s, ctx.project_id).history(200)
        autos = [e for e in events if e.actor.value == "auto"]
        types = {e.type for e in autos}
        assert {"auto.started", "auto.pick", "auto.stopped", "strip.created", "strip.approved"} <= types
        assert not any(e.type == "story.finalized" for e in events)
        started = next(e for e in events if e.type == "auto.started")
        assert started.payload["policy"] == "balanced"


def test_run_auto_is_undoable() -> None:
    with story_ctx() as ctx:
        make_bible(ctx, target=2)
        auto.run_auto(ctx, policy="steer")
        with ctx.project.session() as s:
            log = EventLog(s, ctx.project_id)
            while log.can_undo():
                log.undo()
        with ctx.project.session(readonly=True) as s:
            assert strips.list_strips(s, ctx.project_id) == []


def test_run_auto_one_step_and_resume() -> None:
    with story_ctx() as ctx:
        make_bible(ctx, target=3)
        assert len(auto.run_auto(ctx, until_target=False)) == 1
        seen: list[int] = []
        rest = auto.run_auto(ctx, on_strip=lambda s: seen.append(s.idx))
        assert [m.idx for m in rest] == seen == [2, 3]
        assert auto.run_auto(ctx) == []


def test_run_auto_refuses_unapproved_strips_and_missing_bible() -> None:
    with story_ctx() as ctx:
        with pytest.raises(PrerequisiteError, match="no story bible"):
            auto.run_auto(ctx)
        make_bible(ctx, target=3)
        suggest_next(ctx)
        make_strip(ctx, pick=1)
        with pytest.raises(PrerequisiteError, match="waiting for approval"):
            auto.run_auto(ctx)
