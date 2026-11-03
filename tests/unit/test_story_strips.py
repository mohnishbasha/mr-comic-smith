"""Strip service: create, edit specs, approve, list (S1-T07 service side, FR-014, FR-020)."""

from typing import Any

import pytest

from comic_smith.db.models import Panel, Strip, SuggestionSet
from comic_smith.errors import ImmutableEntityError, PrerequisiteError, SchemaValidationError, UsageError
from comic_smith.story.strips import (
    approve_strip,
    create_strip,
    edit_panel_spec,
    list_panels,
    list_strips,
    resolve_strip,
    unapprove_strip,
)
from tests.unit.story_support import Env, make_beat, story_env


def _one(env: Env) -> tuple[str, list[str]]:
    strip_id = create_strip(env.ctx, make_beat())
    with env.ctx.project.session(readonly=True) as view:
        return strip_id, [p.id for p in list_panels(view, strip_id)]


def test_story_strips_create_stores_scripted_strip_and_panels(monkeypatch: pytest.MonkeyPatch) -> None:
    with story_env(monkeypatch) as env:
        first, panels = _one(env)
        second = create_strip(env.ctx, make_beat("Next"), panels=2)
        with env.ctx.project.session(readonly=True) as view:
            rows = list_strips(view, env.ctx.project_id, "main")
            assert [(r.id, r.idx, r.status, r.panel_count) for r in rows] == [
                (first, 1, "scripted", 4),
                (second, 2, "scripted", 2),
            ]
            assert rows[0].beat["beat"] == "The duck finds a kite"
            stored = view.get(Panel, panels[0])
            assert (
                stored is not None
                and stored.stale == 0
                and stored.spec_json["schema"] == "comic-smith/panel@1"
            )


def test_story_strips_create_is_undoable(monkeypatch: pytest.MonkeyPatch) -> None:
    with story_env(monkeypatch) as env:
        create_strip(env.ctx, make_beat())
        with env.ctx.project.session() as work:
            log = env.ctx.events(work)
            assert log.undo() is not None
            assert work.query(Strip).count() == 0 and work.query(Panel).count() == 0
            assert log.redo() is not None
            assert work.query(Strip).count() == 1 and work.query(Panel).count() == 4


def test_story_strips_failed_generation_leaves_no_rows(monkeypatch: pytest.MonkeyPatch) -> None:
    from comic_smith.errors import GenerationInvalidError

    with story_env(monkeypatch) as env:
        env.llm.replies = [{"panels": []}]
        with pytest.raises(GenerationInvalidError):
            create_strip(env.ctx, make_beat())
        with env.ctx.project.session(readonly=True) as view:
            assert view.query(Strip).count() == 0


def test_story_strips_pick_recorded_and_undone(monkeypatch: pytest.MonkeyPatch) -> None:
    with story_env(monkeypatch) as env:
        with env.ctx.project.session() as work:
            main = work.query(Strip).count()
            assert main == 0
            from comic_smith.db.models import Branch

            branch = work.query(Branch).one()
            work.add(
                SuggestionSet(
                    id="ss_1",
                    project_id=env.ctx.project_id,
                    branch_id=branch.id,
                    json={},
                    created_at="2026-01-01",
                )
            )
        create_strip(env.ctx, make_beat(), suggestion_set_id="ss_1", pick=1)
        with env.ctx.project.session() as work:
            assert work.get(SuggestionSet, "ss_1").chosen_idx == 1  # type: ignore[union-attr]
            env.ctx.events(work).undo()
            assert work.get(SuggestionSet, "ss_1").chosen_idx is None  # type: ignore[union-attr]


def test_story_strips_edit_visual_marks_stale_text_does_not(monkeypatch: pytest.MonkeyPatch) -> None:
    with story_env(monkeypatch) as env:
        _, panels = _one(env)
        text_only: dict[str, Any] = {
            "dialogue": [{"speaker": "ch_frog", "type": "shout", "text": "Hey"}],
            "caption": "Later",
        }
        edit_panel_spec(env.ctx, panels[0], text_only)
        edit_panel_spec(env.ctx, panels[0], {"sfx": [{"text": "SPLASH", "near": "ch_duck"}]})
        with env.ctx.project.session(readonly=True) as view:
            assert view.get(Panel, panels[0]).stale == 0  # type: ignore[union-attr]
        spec = edit_panel_spec(env.ctx, panels[0], {"shot": "extreme-wide"})
        assert spec.shot.value == "extreme-wide"
        with env.ctx.project.session(readonly=True) as view:
            assert view.get(Panel, panels[0]).stale == 1  # type: ignore[union-attr]
            assert view.get(Panel, panels[1]).stale == 0  # type: ignore[union-attr]
        assert any(kind == "script" for kind, _, _ in env.checks)


def test_story_strips_edit_is_undoable_and_restores_stale(monkeypatch: pytest.MonkeyPatch) -> None:
    with story_env(monkeypatch) as env:
        _, panels = _one(env)
        edit_panel_spec(env.ctx, panels[0], {"action": "Puddle jumps"})
        with env.ctx.project.session() as work:
            row = work.get(Panel, panels[0])
            assert row is not None and row.stale == 1 and row.spec_json["action"] == "Puddle jumps"
            env.ctx.events(work).undo()
            work.refresh(row)
            assert row.stale == 0 and row.spec_json["action"] == "Puddle looks around"


def test_story_strips_edit_rejects_invalid_and_foreign_cast(monkeypatch: pytest.MonkeyPatch) -> None:
    with story_env(monkeypatch) as env:
        _, panels = _one(env)
        with pytest.raises(SchemaValidationError):
            edit_panel_spec(env.ctx, panels[0], {"shot": "giant"})
        with pytest.raises(SchemaValidationError, match="cast"):
            edit_panel_spec(
                env.ctx, panels[0], {"dialogue": [{"speaker": "ch_x", "type": "speech", "text": "Hi"}]}
            )
        with pytest.raises(UsageError):
            edit_panel_spec(env.ctx, panels[0], {"idx": 3})
        with pytest.raises(UsageError):
            edit_panel_spec(env.ctx, "pn_missing", {"action": "x"})


def test_story_strips_approve_runs_arc_and_locks_edits_until_unapprove(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with story_env(monkeypatch) as env:
        strip_id, panels = _one(env)
        info = approve_strip(env.ctx, 1)
        assert info.status == "approved" and info.approved_at is not None
        assert env.approvals == [strip_id]
        approve_strip(env.ctx, strip_id)  # idempotent, no second arc update
        assert env.approvals == [strip_id]
        with pytest.raises(ImmutableEntityError):
            edit_panel_spec(env.ctx, panels[0], {"action": "No"})
        assert unapprove_strip(env.ctx, "1").status == "scripted"
        edit_panel_spec(env.ctx, panels[0], {"action": "Yes"})
        with pytest.raises(UsageError):
            unapprove_strip(env.ctx, 1)


def test_story_strips_approve_undo_returns_to_scripted(monkeypatch: pytest.MonkeyPatch) -> None:
    with story_env(monkeypatch) as env:
        strip_id, _ = _one(env)
        approve_strip(env.ctx, 1)
        with env.ctx.project.session() as work:
            env.ctx.events(work).undo()
            assert work.get(Strip, strip_id).status == "scripted"  # type: ignore[union-attr]
        approve_strip(env.ctx, 1)
        unapprove_strip(env.ctx, 1)
        with env.ctx.project.session() as work:
            env.ctx.events(work).undo()
            assert work.get(Strip, strip_id).status == "approved"  # type: ignore[union-attr]


def test_story_strips_approve_requires_lettered_when_asked(monkeypatch: pytest.MonkeyPatch) -> None:
    with story_env(monkeypatch) as env:
        _one(env)
        with pytest.raises(PrerequisiteError, match="not lettered"):
            approve_strip(env.ctx, 1, require_lettered=True)
        assert env.approvals == []


def test_story_strips_resolve_by_index_or_id_and_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    with story_env(monkeypatch) as env:
        first, _ = _one(env)
        with env.ctx.project.session(readonly=True) as view:
            assert resolve_strip(view, env.ctx.project_id, 1).id == first
            assert resolve_strip(view, env.ctx.project_id, first).id == first
            assert resolve_strip(view, env.ctx.project_id, "1", "main").id == first
            with pytest.raises(UsageError):
                resolve_strip(view, env.ctx.project_id, 9)
            with pytest.raises(UsageError):
                resolve_strip(view, env.ctx.project_id, 1, "nope")
