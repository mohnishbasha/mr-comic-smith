"""S1-T11: the story facade in comic_smith.api, offline with the fake providers."""

from pathlib import Path

import pytest

from comic_smith import api
from comic_smith.backends.llm.fake import FakeLLMProvider, clear_fake_responders
from comic_smith.backends.llm.providers import get_llm
from comic_smith.config import Settings
from comic_smith.errors import (
    ImmutableEntityError,
    LLMOutputInvalidError,
    PrerequisiteError,
    ProjectError,
    ProjectNotFoundError,
    UsageError,
)
from comic_smith.story import fake_responses

NARRATIVE = "Puddle is a little rubber duck who is afraid of water. A friend drifts toward the drain."


@pytest.fixture(autouse=True)
def _fake_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COMIC_SMITH_LLM", "fake")
    monkeypatch.setenv("COMIC_SMITH_EMBEDDINGS", "fake")
    fake_responses.ensure_registered()


def _new(name: str = "duck", strips: int = 4) -> str:
    api.create_project(name, narrative=NARRATIVE, audience="kids-5-8", target_strips=strips)
    return name


def test_create_project_generates_and_saves_the_bible() -> None:
    info = api.create_project("duck", narrative=NARRATIVE, audience="kids-5-8")
    bible = api.get_bible("duck")
    assert info.slug == "duck" and bible.arc.target_strips == 8
    assert api.open_project("duck").id == info.id
    assert [p.slug for p in api.list_projects()] == ["duck"]


def test_create_project_needs_a_narrative_and_rejects_images_for_now(tmp_path: Path) -> None:
    with pytest.raises(UsageError, match="narrative is required"):
        api.create_project("duck")
    with pytest.raises(UsageError, match="photos"):
        api.create_project("duck", narrative=NARRATIVE, image_paths=[tmp_path / "x.png"])
    assert api.list_projects() == []


def test_create_project_removes_the_folder_when_the_bible_fails() -> None:
    clear_fake_responders()
    bad = FakeLLMProvider()  # no responders registered: the bible call fails
    with pytest.raises(LLMOutputInvalidError):
        api.create_project("duck", narrative=NARRATIVE, llm=bad)
    assert api.list_projects() == []
    assert not (Settings().projects_dir / "duck").exists()


def test_create_project_duplicate_name_keeps_the_first() -> None:
    _new()
    with pytest.raises(ProjectError):
        api.create_project("duck", narrative=NARRATIVE)
    assert api.get_bible("duck").working_title


def test_get_bible_unknown_project() -> None:
    with pytest.raises(ProjectNotFoundError):
        api.get_bible("ghost")


def test_edit_bible_is_undoable() -> None:
    _new()
    before = api.get_bible("duck").working_title
    assert api.edit_bible("duck", {"working_title": "Splash"}).working_title == "Splash"
    api.undo("duck")
    assert api.get_bible("duck").working_title == before


def test_suggest_then_pick_writes_a_script_only_strip() -> None:
    _new()
    got = api.suggest_next("duck")
    assert len(got.options) == 3
    strip = api.make_strip("duck", pick=2)
    assert strip.status == "scripted" and strip.idx == 1 and len(strip.panels) == 4
    assert strip.beat["beat"] == got.options[1].beat


def test_make_strip_free_text_and_panel_count() -> None:
    _new()
    strip = api.make_strip("duck", beat="Puddle finds a tiny boat", panels=3)
    assert len(strip.panels) == 3 and strip.beat["original_text"] == "Puddle finds a tiny boat"


def test_make_strip_argument_errors() -> None:
    _new()
    with pytest.raises(UsageError, match="exactly one"):
        api.make_strip("duck")
    with pytest.raises(UsageError, match="exactly one"):
        api.make_strip("duck", pick=1, beat="x")
    with pytest.raises(UsageError, match="not a valid pick"):
        api.make_strip("duck", pick="9")
    with pytest.raises(PrerequisiteError, match="no suggestions"):
        api.make_strip("duck", pick=1)
    api.suggest_next("duck")
    with pytest.raises(UsageError, match="not ready to end"):
        api.make_strip("duck", pick="end")


def test_stale_suggestions_are_refused() -> None:
    _new()
    api.suggest_next("duck")
    api.make_strip("duck", pick=1)
    api.approve_strip("duck", 1)
    with pytest.raises(PrerequisiteError, match="out of date"):
        api.make_strip("duck", pick=1)


def test_approve_unapprove_list_and_edit_panel() -> None:
    _new()
    api.suggest_next("duck")
    strip = api.make_strip("duck", pick=1)
    panel = strip.panels[0]
    edited = api.edit_panel("duck", panel.id, {"caption": "Splash!"})
    assert edited.caption == "Splash!"
    assert api.approve_strip("duck", 1).status == "approved"
    with pytest.raises(ImmutableEntityError):
        api.edit_panel("duck", panel.id, {"caption": "again"})
    assert api.unapprove_strip("duck", 1).status == "scripted"
    assert [s.idx for s in api.list_strips("duck")] == [1]


def test_end_pick_closes_the_story_at_target() -> None:
    _new(strips=1)
    api.suggest_next("duck")
    api.make_strip("duck", pick=1)
    api.approve_strip("duck", 1)
    offered = api.suggest_next("duck")
    assert offered.end_here is not None
    assert api.make_strip("duck", pick="end").beat["intent"] == "end"


def test_branches_round_trip() -> None:
    _new()
    api.suggest_next("duck")
    api.make_strip("duck", pick=1)
    api.approve_strip("duck", 1)
    made = api.create_branch("duck", "what-if", switch=True)
    assert made.name == "what-if" and made.active
    assert api.rename_branch("duck", "what-if", "twisty").name == "twisty"
    assert [b.name for b in api.list_branches("duck")] == ["twisty", "main"]
    assert api.switch_branch("duck", "main").active
    api.delete_branch("duck", "twisty")
    assert [b.name for b in api.list_branches("duck")] == ["main"]


def test_branch_none_means_the_active_branch() -> None:
    _new()
    api.suggest_next("duck")
    api.make_strip("duck", pick=1)
    api.approve_strip("duck", 1)
    api.create_branch("duck", "alt", switch=True)
    api.suggest_next("duck")
    strip = api.make_strip("duck", pick=1)
    assert strip.idx == 2 and strip.branch_id != api.list_branches("duck")[1].id


def test_auto_then_finalize_then_reopen() -> None:
    _new(strips=3)
    made = api.run_auto("duck", policy="twist")
    assert len(made) == 3
    story = api.finalize_story("duck", title="Puddle")
    assert story.title == "Puddle" and story.finalized_at is not None
    reopened = api.reopen_story("duck", story.id)
    assert reopened.version == 2 and reopened.finalized_at is None


def test_undo_redo_history() -> None:
    _new()
    assert api.undo("duck") is not None
    redone = api.redo("duck")
    assert redone is not None and redone.type == "bible.updated"
    assert api.redo("duck") is None
    types = [e.type for e in api.history("duck", limit=3)]
    assert types[0] == "event.redone"


def test_undo_with_nothing_to_undo_returns_none() -> None:
    api.create_project("blank", narrative=NARRATIVE)
    assert api.undo("blank") is not None  # the bible
    assert api.undo("blank") is None


def test_rename_archive_delete_project() -> None:
    _new()
    assert api.rename_project("duck", "Duck 2").name == "Duck 2"
    assert api.archive_project("duck").archived
    assert api.list_projects() == []
    assert [p.slug for p in api.list_projects(include_archived=True)] == ["duck"]
    assert api.delete_project("duck").exists()
    assert api.list_projects(include_archived=True) == []


def test_fake_provider_registers_its_answers_after_clear() -> None:
    clear_fake_responders()
    llm = get_llm(Settings(llm="fake"))
    assert isinstance(llm, FakeLLMProvider)
    info = api.create_project("again", narrative=NARRATIVE)
    assert info.slug == "again"


def test_ensure_registered_keeps_a_test_override() -> None:
    from comic_smith.backends.llm.fake import _RESPONDERS, register_fake_responder

    marker = _RESPONDERS["bible"]

    def custom(system: str, user: str, schema: dict[str, object], index: int) -> dict[str, object]:
        return {}

    register_fake_responder("bible", custom)
    fake_responses.ensure_registered()
    assert _RESPONDERS["bible"] is custom
    register_fake_responder("bible", marker)
