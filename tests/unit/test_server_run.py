"""run() guards and wiring for S0-T08 (uvicorn and the browser are mocked)."""

from collections.abc import Callable
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest
from pydantic import SecretStr
from typer.testing import CliRunner

from comic_smith import api, cli
from comic_smith.config import Settings
from comic_smith.errors import UsageError
from comic_smith.server import run as run_module


class _InlineThread:
    """Runs the target synchronously so the browser-open path is deterministic."""

    def __init__(self, target: Callable[..., None], args: tuple[Any, ...] = (), **_: Any) -> None:
        self._target = target
        self._args = args

    def start(self) -> None:
        self._target(*self._args)


@pytest.fixture
def uvicorn_run(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    mock = MagicMock()
    monkeypatch.setattr(run_module.uvicorn, "run", mock)
    return mock


@pytest.fixture
def open_browser(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    mock = MagicMock()
    monkeypatch.setattr(run_module.webbrowser, "open", mock)
    monkeypatch.setattr(run_module.threading, "Thread", _InlineThread)
    monkeypatch.setattr(run_module, "_wait_for_port", lambda host, port, timeout=15.0: True)
    return mock


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(data_dir=tmp_path / "data")


def test_server_run_binds_given_loopback_host(
    settings: Settings, uvicorn_run: MagicMock, open_browser: MagicMock
) -> None:
    run_module.run(settings, host="127.0.0.1", port=7399, open_browser=False)
    uvicorn_run.assert_called_once()
    assert uvicorn_run.call_args.kwargs["host"] == "127.0.0.1"
    assert uvicorn_run.call_args.kwargs["port"] == 7399
    open_browser.assert_not_called()


def test_server_run_opens_browser_when_requested(
    settings: Settings, uvicorn_run: MagicMock, open_browser: MagicMock
) -> None:
    run_module.run(settings, host="127.0.0.1", port=7399, open_browser=True)
    uvicorn_run.assert_called_once()
    open_browser.assert_called_once_with("http://127.0.0.1:7399/")


@pytest.mark.parametrize("host", ["0.0.0.0", "192.168.1.20", "example.test"])  # noqa: S104
def test_server_run_refuses_non_localhost_without_token(
    settings: Settings, uvicorn_run: MagicMock, host: str
) -> None:
    with pytest.raises(UsageError) as info:
        run_module.run(settings, host=host, port=7399, open_browser=False)
    assert info.value.hint
    assert "COMIC_SMITH_SERVER_TOKEN" in info.value.hint
    uvicorn_run.assert_not_called()


@pytest.mark.parametrize("secret", ["server_token", "access_code"])
def test_server_run_allows_non_localhost_with_credential(
    tmp_path: Path, uvicorn_run: MagicMock, secret: str
) -> None:
    settings = Settings(data_dir=tmp_path / "data", **{secret: SecretStr("correct-horse-battery")})
    run_module.run(settings, host="0.0.0.0", port=7399, open_browser=False)  # noqa: S104
    uvicorn_run.assert_called_once()


def test_server_run_empty_secret_does_not_count(tmp_path: Path, uvicorn_run: MagicMock) -> None:
    settings = Settings(data_dir=tmp_path / "data", server_token=SecretStr(""))
    with pytest.raises(UsageError):
        run_module.run(settings, host="0.0.0.0", port=7399, open_browser=False)  # noqa: S104
    uvicorn_run.assert_not_called()


def test_server_wait_for_port_times_out_on_closed_port() -> None:
    assert run_module._wait_for_port("127.0.0.1", 1, timeout=0.2) is False


def test_cli_studio_binds_loopback_by_default(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    captured = MagicMock()
    monkeypatch.setattr(api, "run_studio", captured)
    monkeypatch.setenv("COMIC_SMITH_DATA_DIR", str(tmp_path / "data"))
    result = CliRunner().invoke(cli.app, ["studio", "--no-browser"])
    assert result.exit_code == 0, result.output
    assert captured.call_args.kwargs["host"] == "127.0.0.1"
    assert captured.call_args.kwargs["open_browser"] is False
