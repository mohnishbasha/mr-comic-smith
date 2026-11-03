"""Finalize: continuity review, titles, lock, reopen (S1-T10, FR-022)."""

from typing import Any

import pytest

from comic_smith.db.models import Story, Strip
from comic_smith.errors import (
    ImmutableEntityError,
    LLMOutputInvalidError,
    PrerequisiteError,
    UsageError,
)
from comic_smith.models import ContinuityReport
from comic_smith.story import fake_responses_writer
from comic_smith.story.branches import create_branch, delete_branch, switch_branch
from comic_smith.story.finalize import finalize, jump_targets, reopen, review
from comic_smith.story.strips import (
    approve_strip,
    create_strip,
    edit_panel_spec,
    list_panels,
    unapprove_strip,
)
from tests.unit.story_support import Env, echo_script, make_beat, story_env

TITLES = {"titles": ["The Kite", "Puddle and the Kite", "A Red Kite Day"], "blurb": "A duck returns a kite."}


def _issue(strip: int = 2, kind: str = "unresolved_thread", **extra: Any) -> dict[str, Any]:
    return {
        "id": "x",
        "kind": kind,
        "severity": "warn",
        "strip": strip,
        "text": "The kite is never returned.",
        **extra,
    }


def _llm(env: Env, issues: list[dict[str, Any]] | None = None, titles: dict[str, Any] | None = None) -> None:
    def reply(user: str) -> dict[str, Any]:
        raise AssertionError("unexpected")

    def respond(user: str) -> dict[str, Any]:
        return echo_script(user)

    env.llm.replies = [respond]
    original = env.llm.complete_json

    def routed(
        system: str, user: str, schema: dict[str, Any], *, temperature: float, seed: int | None
    ) -> dict[str, Any]:
        if "continuity@" in system.splitlines()[0]:
            env.llm.calls.append({"system": system, "user": user, "temperature": temperature})
            return {"issues": issues or []}
        if "titles@" in system.splitlines()[0]:
            env.llm.calls.append({"system": system, "user": user, "temperature": temperature})
            return titles or TITLES
        return original(system, user, schema, temperature=temperature, seed=seed)

    env.ctx.llm = type(
        "Routed", (), {"id": "routed", "preflight": lambda self: [], "complete_json": staticmethod(routed)}
    )()  # type: ignore[assignment]


def _story(env: Env, count: int = 3) -> None:
    for i in range(1, count + 1):
        create_strip(env.ctx, make_beat(f"Beat {i}"))
    approve_strip(env.ctx, 1)


def test_story_finalize_continuity_report_structure(monkeypatch: pytest.MonkeyPatch) -> None:
    with story_env(monkeypatch) as env:
        _story(env)
        _llm(env, [_issue(2, character_id="ch_frog"), _issue(3, "tone_break", panel_idx=2)])
        report = review(env.ctx)
        assert isinstance(report, ContinuityReport)
        assert [(i.id, i.kind.value, i.strip) for i in report.issues] == [
            ("iss_1", "unresolved_thread", 2),
            ("iss_2", "tone_break", 3),
        ]
        assert report.issues[0].character_id == "ch_frog" and report.story_id.startswith("sy_")
        continuity = [c for c in env.llm.calls if "continuity@" in c["system"]]
        assert continuity[0]["temperature"] == 0.0 and "Audience:" in continuity[0]["system"]
        # bad references are dropped, not trusted
        _llm(env, [_issue(9), _issue(1, character_id="ch_ghost"), _issue(1, "inconsistent_prop")])
        assert [i.kind.value for i in review(env.ctx).issues] == ["inconsistent_prop"]


def test_story_finalize_returns_three_titles_and_blurb(monkeypatch: pytest.MonkeyPatch) -> None:
    with story_env(monkeypatch) as env:
        _story(env)
        _llm(env)
        report = review(env.ctx)
        assert report.titles == TITLES["titles"] and report.blurb == TITLES["blurb"]
        info = finalize(env.ctx)
        assert info.title == "The Kite" and info.blurb == TITLES["blurb"]
        assert any(kind == "suggestion" and "The Kite" in texts for kind, texts, _ in env.checks)
        _llm(env, titles={"titles": ["Only one"], "blurb": "x"})
        with pytest.raises(LLMOutputInvalidError):
            review(env.ctx)


def test_story_finalize_locks_story_read_only(monkeypatch: pytest.MonkeyPatch) -> None:
    with story_env(monkeypatch) as env:
        _story(env)
        _llm(env)
        info = finalize(env.ctx, title="  My Title ")
        assert info.title == "My Title" and info.version == 1 and info.finalized_at is not None
        with pytest.raises(ImmutableEntityError):
            finalize(env.ctx)
        with env.ctx.project.session(readonly=True) as view:
            panel = _first_panel(view)
        with pytest.raises(ImmutableEntityError):
            edit_panel_spec(env.ctx, panel, {"action": "x"})
        with pytest.raises(ImmutableEntityError):
            create_strip(env.ctx, make_beat("More"))
        with pytest.raises(ImmutableEntityError):
            unapprove_strip(env.ctx, 1)
        with pytest.raises(ImmutableEntityError):
            approve_strip(env.ctx, 2)


def _first_panel(view: Any, idx: int = 2) -> str:
    """First panel of strip `idx` (strip 1 is approved in these tests, so default to 2)."""
    strip = view.query(Strip).filter(Strip.idx == idx).first()
    return list_panels(view, strip.id)[0].id


def test_story_finalize_anyway_with_open_issues_allowed(monkeypatch: pytest.MonkeyPatch) -> None:
    with story_env(monkeypatch) as env:
        _story(env)
        _llm(env, [_issue(2)])
        with pytest.raises(PrerequisiteError) as err:
            finalize(env.ctx)
        report = ContinuityReport.model_validate_json(err.value.detail or "")
        assert report.issues[0].strip == 2 and len(report.titles) == 3
        assert err.value.exit_code == 5 and "force" in (err.value.hint or "")
        with env.ctx.project.session(readonly=True) as view:
            assert view.query(Story).count() == 0  # a refused finalize changes nothing
        info = finalize(env.ctx, force=True)
        assert info.finalized_at is not None
        with env.ctx.project.session(readonly=True) as view:
            stored = view.query(Story).one()
            assert stored.continuity_json is not None and len(stored.continuity_json["issues"]) == 1


def test_story_finalize_reopen_creates_new_version(monkeypatch: pytest.MonkeyPatch) -> None:
    with story_env(monkeypatch) as env:
        _story(env)
        _llm(env)
        first = finalize(env.ctx)
        second = reopen(env.ctx, first.id)
        assert second.version == 2 and second.finalized_at is None and second.id != first.id
        assert (second.title, second.blurb) == (first.title, first.blurb)
        with env.ctx.project.session(readonly=True) as view:
            assert [
                (s.version, s.finalized_at is not None) for s in view.query(Story).order_by(Story.version)
            ] == [
                (1, True),
                (2, False),
            ]
        create_strip(env.ctx, make_beat("Beat 4"))  # unlocked again
        third = finalize(env.ctx, title="Second Cut")
        assert third.id == second.id and third.version == 2 and third.finalized_at is not None
        with pytest.raises(UsageError):
            reopen(env.ctx, first.id)  # not the latest version
        with pytest.raises(UsageError):
            reopen(env.ctx, "sy_missing")
        with env.ctx.project.session() as work:
            log = env.ctx.events(work)
            assert log.undo() is not None  # finalize v2 undone: row back to unfinalized
            assert work.get(Story, second.id).finalized_at is None  # type: ignore[union-attr]
            assert log.undo() is not None  # creating strip 4
            assert log.undo() is not None  # reopen undone: v2 removed
            assert work.query(Story).count() == 1


def test_story_finalize_edit_locked_story_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    with story_env(monkeypatch) as env:
        _story(env)
        _llm(env)
        create_branch(env.ctx, "alt", from_strip=1)
        info = finalize(env.ctx, branch="main")
        with env.ctx.project.session(readonly=True) as view:
            panel = _first_panel(view)
        with pytest.raises(ImmutableEntityError, match="finalized"):
            edit_panel_spec(env.ctx, panel, {"action": "x"})  # alt inherits a strip of a finalized branch
        reopen(env.ctx, info.id)
        edit_panel_spec(env.ctx, panel, {"action": "x"})
        switch_branch(env.ctx, "alt")
        with pytest.raises(UsageError):
            delete_branch(env.ctx, "main")  # main has a child branch; finalize history is kept


def test_story_finalize_report_jump_to_strip_ids(monkeypatch: pytest.MonkeyPatch) -> None:
    with story_env(monkeypatch) as env:
        _story(env)
        _llm(env, [_issue(3), _issue(1, "vanished_character", character_id="ch_frog")])
        report = review(env.ctx)
        with env.ctx.project.session(readonly=True) as view:
            targets = jump_targets(view, env.ctx.project_id, report)
            from comic_smith.story.strips import list_strips

            ids = {s.idx: s.id for s in list_strips(view, env.ctx.project_id)}
        assert targets == {"iss_1": ids[3], "iss_2": ids[1]}


def test_story_finalize_needs_strips_and_bible(monkeypatch: pytest.MonkeyPatch) -> None:
    from comic_smith.story import bible as bible_service

    with story_env(monkeypatch) as env:
        _llm(env)
        with pytest.raises(PrerequisiteError, match="no strips"):
            finalize(env.ctx)
        monkeypatch.setattr(bible_service, "current_bible", lambda session, project_id: None)
        with pytest.raises(PrerequisiteError, match="bible"):
            finalize(env.ctx)


def test_story_finalize_fake_provider_end_to_end(monkeypatch: pytest.MonkeyPatch) -> None:
    from comic_smith.backends.llm.fake import FakeLLMProvider

    fake_responses_writer.register()
    with story_env(monkeypatch) as env:
        env.ctx.llm = FakeLLMProvider()
        _story(env, 2)
        info = finalize(env.ctx)
        assert info.title == "Puddle the Duck" and info.finalized_at is not None
    with story_env(monkeypatch) as env:
        env.ctx.llm = FakeLLMProvider()
        create_strip(env.ctx, make_beat("A [fake:continuity-issue] beat"))
        assert [i.kind.value for i in review(env.ctx).issues] == ["tone_break"]
        with pytest.raises(PrerequisiteError):
            finalize(env.ctx)


def test_story_branch_delete_branch_with_story_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    with story_env(monkeypatch) as env:
        _story(env, 1)
        _llm(env)
        create_branch(env.ctx, "alt", from_strip=1)
        create_strip(env.ctx, make_beat("Alt 2"), branch="alt")
        finalize(env.ctx, branch="alt")
        with pytest.raises(ImmutableEntityError):
            delete_branch(env.ctx, "alt")
