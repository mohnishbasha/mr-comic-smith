"""S1-T11: story CLI commands via the typer test runner (fake providers, no network)."""

import json
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from comic_smith.cli import app
from comic_smith.cli_util import parse_assignments
from comic_smith.errors import UsageError
from comic_smith.story import fake_responses

runner = CliRunner()
NARRATIVE = "Puddle is a little rubber duck who is afraid of water. A friend drifts toward the drain."


@pytest.fixture(autouse=True)
def _fake_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COMIC_SMITH_LLM", "fake")
    monkeypatch.setenv("COMIC_SMITH_EMBEDDINGS", "fake")
    fake_responses.ensure_registered()


def run(*args: str, code: int = 0) -> str:
    result = runner.invoke(app, list(args))
    assert result.exit_code == code, result.output
    return result.output


def run_json(*args: str) -> Any:
    return json.loads(run(*args, "--json"))


def new_duck(strips: str = "4") -> None:
    run("new", "duck", "--narrative", NARRATIVE, "--audience", "kids-5-8", "--strips", strips)


def test_cli_new_narrative_creates_project_json_output() -> None:
    info = run_json("new", "duck", "--narrative", NARRATIVE, "--audience", "kids-5-8")
    assert info["id"].startswith("prj_") and info["slug"] == "duck"
    assert Path(info["path"]).is_dir()


def test_cli_new_human_output_shows_the_bible() -> None:
    out = run("new", "duck", "--narrative", NARRATIVE, "--audience", "kids-5-8")
    assert "Created project duck" in out and "Arc:" in out


def test_cli_new_without_narrative_or_with_image_is_a_usage_error() -> None:
    assert "narrative is required" in run("new", "duck", code=2)
    out = run("new", "duck", "--narrative", NARRATIVE, "--image", "x.png", code=2)
    assert "Sprint 2" in out


def test_cli_bible_show_and_edit() -> None:
    new_duck()
    shown = run_json("bible", "duck")
    assert shown["arc"]["target_strips"] == 4
    edited = run_json("bible", "duck", "--set", "working_title=Splash", "--set", 'tone=["warm"]')
    assert edited["working_title"] == "Splash" and edited["tone"] == ["warm"]
    assert "Splash" in run("bible", "duck")
    assert run_json("bible", "duck")["working_title"] == "Splash"
    assert "not KEY=VALUE" in run("bible", "duck", "--set", "oops", code=2)


def test_cli_suggest_json_returns_three_options() -> None:
    new_duck()
    got = run_json("suggest", "duck")
    assert [o["intent"] for o in got["options"]] == ["continue", "twist", "steer"]
    table = run("suggest", "duck")
    assert "continue" in table and "twist" in table


def test_cli_strip_pick_writes_script_only() -> None:
    new_duck()
    run("suggest", "duck")
    strip = run_json("strip", "duck", "--pick", "2")
    assert strip["status"] == "scripted" and len(strip["panels"]) == 4
    assert all("asset" not in p for p in strip["panels"])
    assert "Strip 1" in run("strips", "duck")


def test_cli_strip_beat_free_text() -> None:
    new_duck()
    strip = run_json("strip", "duck", "--beat", "Puddle finds a boat", "--panels", "3")
    assert len(strip["panels"]) == 3 and strip["beat"]["original_text"] == "Puddle finds a boat"
    assert "Strip 2" in run("strip", "duck", "--beat", "A second idea")


def test_cli_strip_needs_exactly_one_of_pick_and_beat() -> None:
    new_duck()
    assert "exactly one" in run("strip", "duck", code=2)
    assert "no suggestions" in run("strip", "duck", "--pick", "1", code=5)


def test_cli_approve_and_history_undo_redo() -> None:
    new_duck()
    run("suggest", "duck")
    run("strip", "duck", "--pick", "1")
    assert run_json("approve", "duck", "--strip", "1")["status"] == "approved"
    assert "Approved strip 1" in run("approve", "duck", "--strip", "1")
    events = run_json("history", "duck")
    assert events[0]["type"] in {"strip.arc_tagged", "strip.approved", "bible.updated"}
    assert "event" in run("history", "duck")
    assert run_json("undo", "duck")["id"]
    assert "Undo:" in run("undo", "duck")
    assert run_json("redo", "duck")["id"]
    assert "Redo:" in run("redo", "duck")


def test_cli_undo_and_redo_with_nothing_to_do() -> None:
    new_duck()
    while run("undo", "duck").startswith("Undo:"):
        pass
    assert "Nothing to undo" in run("undo", "duck")
    assert json.loads(run("undo", "duck", "--json")) is None
    while run("redo", "duck").startswith("Redo:"):
        pass
    assert "Nothing to redo" in run("redo", "duck")


def test_cli_branch_create_switch_list() -> None:
    new_duck()
    run("suggest", "duck")
    run("strip", "duck", "--pick", "1")
    run("approve", "duck", "--strip", "1")
    made = run_json("branch", "duck", "create", "what-if", "--from-strip", "1")
    assert made["name"] == "what-if" and not made["active"]
    assert run_json("branch", "duck", "switch", "what-if")["active"]
    listing = run_json("branch", "duck", "list")
    assert [b["name"] for b in listing] == ["what-if", "main"]
    assert "* what-if" in run("branch", "duck", "list")
    assert "Branch twisty" in run("branch", "duck", "rename", "what-if", "twisty")
    run("branch", "duck", "switch", "main")
    assert "twisty" in run("branch", "duck", "list")
    assert run_json("branch", "duck", "delete", "twisty", "--yes") == {"deleted": "twisty"}
    assert "twisty" not in run("branch", "duck", "list")


def test_cli_branch_argument_and_confirmation_rules() -> None:
    new_duck()
    assert "takes 1 name" in run("branch", "duck", "create", code=2)
    assert "takes 0 name" in run("branch", "duck", "list", "extra", code=2)
    assert "needs --yes" in run("branch", "duck", "delete", "x", "--json", code=2)
    result = runner.invoke(app, ["branch", "duck", "delete", "x"], input="n\n")
    assert result.exit_code == 2


def test_cli_branch_delete_asks_and_deletes_on_yes() -> None:
    new_duck()
    run("suggest", "duck")
    run("strip", "duck", "--pick", "1")
    run("approve", "duck", "--strip", "1")
    run("branch", "duck", "create", "alt")
    result = runner.invoke(app, ["branch", "duck", "delete", "alt"], input="y\n")
    assert result.exit_code == 0 and "Deleted branch alt" in result.output


def test_cli_auto_until_target_policy_balanced() -> None:
    new_duck("3")
    made = run_json("auto", "duck", "--policy", "balanced", "--until-target")
    assert len(made) == 3 and {m["status"] for m in made} == {"approved"}
    assert len(run_json("strips", "duck")) == 3
    assert "Wrote and approved 0" in run("auto", "duck")


def test_cli_auto_one_step_and_bad_policy() -> None:
    new_duck("3")
    assert len(run_json("auto", "duck", "--one-step")) == 1
    assert "Wrote and approved 2" in run("auto", "duck", "--policy", "twist")
    assert runner.invoke(app, ["auto", "duck", "--policy", "wild"]).exit_code == 2


def test_cli_finalize_json_and_human() -> None:
    new_duck("2")
    run("auto", "duck")
    story = run_json("finalize", "duck", "--title", "Puddle")
    assert story["title"] == "Puddle" and story["finalized_at"]
    assert "already finalized" in run("finalize", "duck", code=8)


def test_cli_finalize_human_output() -> None:
    new_duck("2")
    run("auto", "duck")
    assert "Finalized 'Puddle'" in run("finalize", "duck", "--title", "Puddle")


def test_cli_errors_json_problem_object_and_exit_codes() -> None:
    result = runner.invoke(app, ["bible", "ghost", "--json"])
    assert result.exit_code == 8
    assert '"code": "project_not_found"' in result.output


def test_cli_all_story_commands_support_json_flag() -> None:
    new_duck("2")
    commands = [
        ["bible", "duck"],
        ["suggest", "duck"],
        ["strip", "duck", "--pick", "1"],
        ["strips", "duck"],
        ["approve", "duck", "--strip", "1"],
        ["branch", "duck", "list"],
        ["auto", "duck"],
        ["finalize", "duck", "--title", "T"],
        ["history", "duck"],
        ["undo", "duck"],
        ["redo", "duck"],
    ]
    for cmd in commands:
        json.loads(run(*cmd, "--json"))
    json.loads(run("new", "other", "--narrative", NARRATIVE, "--json"))
    for name in (
        "new",
        "bible",
        "suggest",
        "strip",
        "strips",
        "approve",
        "branch",
        "finalize",
        "auto",
        "history",
    ):
        assert "--json" in run(name, "--help")


def test_parse_assignments_nests_dotted_keys_and_parses_json() -> None:
    got = parse_assignments(["a=1", "arc.target_strips=6", 'tone=["x"]', "title=Hello = World"])
    assert got == {"a": 1, "arc": {"target_strips": 6}, "tone": ["x"], "title": "Hello = World"}
    with pytest.raises(UsageError):
        parse_assignments(["=x"])
