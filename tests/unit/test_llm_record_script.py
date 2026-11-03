"""scripts/record-fixtures.py end to end with the fake provider (S1-T01)."""

import importlib.util
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

from comic_smith.backends.llm.fake import clear_fake_responders, register_fake_responder


def load_script(repo_root: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "record_fixtures", repo_root / "scripts" / "record-fixtures.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_llm_record_script_records_selftest_scenario(
    repo_root: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    script = load_script(repo_root)
    register_fake_responder("_selftest", lambda s, u, sc, i: {"echo": "Ada"})
    try:
        out = tmp_path / "fx"
        assert script.main(["--provider", "fake", "--scenario", "selftest", "--out", str(out)]) == 0
    finally:
        clear_fake_responders()
    assert len(list(out.glob("*.json"))) == 1
    assert "recorded scenario selftest" in capsys.readouterr().out


def test_llm_record_script_list_and_argument_errors(
    repo_root: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    script = load_script(repo_root)
    assert script.main(["--list"]) == 0
    assert "selftest" in capsys.readouterr().out
    for argv in ([], ["--provider", "fake", "--scenario", "nope"]):
        with pytest.raises(SystemExit):
            script.main(argv)
    args: dict[str, Any] = {}
    assert not args
