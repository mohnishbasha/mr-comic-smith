"""Branching: parent chain listing, switch, rename, delete (S1-T09, FR-021)."""

import pytest

from comic_smith.db.models import Panel, Strip
from comic_smith.errors import PrerequisiteError, UsageError
from comic_smith.story.branches import (
    branch_strips,
    create_branch,
    delete_branch,
    list_branches,
    rename_branch,
    resolve_branch,
    switch_branch,
)
from comic_smith.story.strips import approve_strip, create_strip, list_strips
from tests.unit.story_support import Env, make_beat, story_env


def _strips(env: Env, count: int, approve: int, branch: str = "main") -> list[str]:
    ids = [create_strip(env.ctx, make_beat(f"Beat {i}"), branch=branch) for i in range(1, count + 1)]
    for i in range(approve):
        approve_strip(env.ctx, ids[i], branch=branch)
    return ids


def _listing(env: Env, branch: str | None) -> list[tuple[int, str]]:
    with env.ctx.project.session(readonly=True) as view:
        return [(s.idx, s.beat["beat"]) for s in list_strips(view, env.ctx.project_id, branch)]


def test_story_branch_create_from_approved_strip(monkeypatch: pytest.MonkeyPatch) -> None:
    with story_env(monkeypatch) as env:
        ids = _strips(env, 3, 2)
        info = create_branch(env.ctx, "what-if", from_strip=2)
        assert info.name == "what-if" and not info.active and info.fork_strip_id == ids[1]
        assert info.strip_count == 2
        default = create_branch(env.ctx, "latest")  # defaults to the latest approved strip
        assert default.fork_strip_id == ids[1]
        by_id = create_branch(env.ctx, "by-id", from_strip=ids[0])
        assert by_id.fork_strip_id == ids[0]
        with env.ctx.project.session() as work:
            env.ctx.events(work).undo()
            assert [b.name for b in list_branches(work, env.ctx.project_id)] == ["main", "latest", "what-if"]


def test_story_branch_create_from_unapproved_strip_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    with story_env(monkeypatch) as env:
        _strips(env, 2, 1)
        with pytest.raises(PrerequisiteError, match="not approved"):
            create_branch(env.ctx, "nope", from_strip=2)
    with story_env(monkeypatch) as env:
        _strips(env, 1, 0)
        with pytest.raises(PrerequisiteError):
            create_branch(env.ctx, "nope")
        assert [b.name for b in _branches(env)] == ["main"]


def _branches(env: Env):  # type: ignore[no-untyped-def]
    with env.ctx.project.session(readonly=True) as view:
        return list_branches(view, env.ctx.project_id)


def test_story_branch_strip_listing_follows_parent_chain_to_fork(monkeypatch: pytest.MonkeyPatch) -> None:
    with story_env(monkeypatch) as env:
        _strips(env, 3, 2)
        create_branch(env.ctx, "alt", from_strip=2, switch=True)
        create_strip(env.ctx, make_beat("Alt 3"), branch="alt")
        create_strip(env.ctx, make_beat("Alt 4"), branch="alt")
        assert _listing(env, "alt") == [(1, "Beat 1"), (2, "Beat 2"), (3, "Alt 3"), (4, "Alt 4")]
        assert _listing(env, "main") == [(1, "Beat 1"), (2, "Beat 2"), (3, "Beat 3")]
        approve_strip(env.ctx, 3)  # the active branch is alt, so index 3 is Alt 3
        create_branch(env.ctx, "alt-deep", from_strip=2)  # fork from inherited strip 2
        create_strip(env.ctx, make_beat("Deep 3"), branch="alt-deep")
        assert _listing(env, "alt-deep") == [(1, "Beat 1"), (2, "Beat 2"), (3, "Deep 3")]
        with env.ctx.project.session(readonly=True) as view:
            assert len(branch_strips(view, resolve_branch(view, env.ctx.project_id, "alt"))) == 4


def test_story_branch_switch_changes_active_branch(monkeypatch: pytest.MonkeyPatch) -> None:
    with story_env(monkeypatch) as env:
        _strips(env, 1, 1)
        create_branch(env.ctx, "alt")
        assert [(b.name, b.active) for b in _branches(env)] == [("main", True), ("alt", False)]
        assert switch_branch(env.ctx, "alt").active
        assert [(b.name, b.active) for b in _branches(env)] == [("alt", True), ("main", False)]
        assert switch_branch(env.ctx, "alt").active  # no-op
        with env.ctx.project.session() as work:
            env.ctx.events(work).undo()
            assert resolve_branch(work, env.ctx.project_id, None).name == "main"
        with pytest.raises(UsageError):
            switch_branch(env.ctx, "ghost")


def test_story_branch_rename(monkeypatch: pytest.MonkeyPatch) -> None:
    with story_env(monkeypatch) as env:
        _strips(env, 1, 1)
        create_branch(env.ctx, "alt")
        assert rename_branch(env.ctx, "alt", "  better  ").name == "better"
        with pytest.raises(UsageError, match="already exists"):
            rename_branch(env.ctx, "better", "main")
        with pytest.raises(UsageError):
            rename_branch(env.ctx, "better", " ")
        assert rename_branch(env.ctx, "better", "better").name == "better"
        with env.ctx.project.session() as work:
            env.ctx.events(work).undo()
            assert {b.name for b in list_branches(work, env.ctx.project_id)} == {"main", "alt"}


def test_story_branch_delete_keeps_shared_strips(monkeypatch: pytest.MonkeyPatch) -> None:
    with story_env(monkeypatch) as env:
        _strips(env, 3, 2)
        create_branch(env.ctx, "alt", from_strip=2)
        create_strip(env.ctx, make_beat("Alt 3"), branch="alt")
        delete_branch(env.ctx, "alt")
        assert [b.name for b in _branches(env)] == ["main"]
        assert _listing(env, "main") == [(1, "Beat 1"), (2, "Beat 2"), (3, "Beat 3")]
        with env.ctx.project.session() as work:
            assert work.query(Strip).count() == 3 and work.query(Panel).count() == 12
            env.ctx.events(work).undo()  # restores the branch and its own strip with panels
            assert work.query(Strip).count() == 4 and work.query(Panel).count() == 16
        assert _listing(env, "alt") == [(1, "Beat 1"), (2, "Beat 2"), (3, "Alt 3")]


def test_story_branch_delete_active_branch_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    with story_env(monkeypatch) as env:
        _strips(env, 1, 1)
        with pytest.raises(UsageError, match="active"):
            delete_branch(env.ctx, "main")
        create_branch(env.ctx, "alt", switch=True)
        with pytest.raises(UsageError, match="active"):
            delete_branch(env.ctx, "alt")


def test_story_branch_delete_with_children_or_story_rejected(monkeypatch: pytest.MonkeyPatch) -> None:

    with story_env(monkeypatch) as env:
        _strips(env, 2, 2)
        create_branch(env.ctx, "mid", from_strip=2)
        switch_branch(env.ctx, "mid")
        create_strip(env.ctx, make_beat("Mid 3"), branch="mid")
        approve_strip(env.ctx, 3)
        create_branch(env.ctx, "leaf", from_strip=3)
        switch_branch(env.ctx, "main")
        with pytest.raises(UsageError, match="leaf"):
            delete_branch(env.ctx, "mid")
