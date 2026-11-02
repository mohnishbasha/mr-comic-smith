"""Shared fixtures: every test runs with an isolated environment, home, and working directory."""

import os
from collections.abc import Iterator
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(autouse=True)
def _isolated_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Iterator[None]:
    for key in list(os.environ):
        if key.startswith("COMIC_SMITH_"):
            monkeypatch.delenv(key, raising=False)
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    monkeypatch.setenv("COMIC_SMITH_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.chdir(tmp_path)
    yield


@pytest.fixture
def repo_root() -> Path:
    return ROOT


@pytest.fixture
def fixtures_dir() -> Path:
    return FIXTURES
