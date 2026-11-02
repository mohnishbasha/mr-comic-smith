"""S0-T12: settings precedence flags > env > comic-smith.toml > defaults (ARCHITECTURE 12.2)."""

from pathlib import Path

import pytest

from comic_smith.config import DEFAULT_STUDIO_PORT, Settings, find_config_file, load_settings
from comic_smith.errors import ConfigError


def _write_toml(tmp_path: Path, body: str) -> Path:
    path = tmp_path / "comic-smith.toml"
    path.write_text(body, encoding="utf-8")
    return path


def test_config_precedence_flags_over_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COMIC_SMITH_STUDIO_PORT", "8000")
    assert load_settings({"studio_port": 9000}).studio_port == 9000


def test_config_precedence_env_over_file(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _write_toml(tmp_path, "studio_port = 8100\n")
    monkeypatch.setenv("COMIC_SMITH_STUDIO_PORT", "8200")
    assert load_settings().studio_port == 8200


def test_config_precedence_file_over_defaults(tmp_path: Path) -> None:
    _write_toml(tmp_path, 'studio_port = 8100\nimage_backend = "mock"\n')
    s = load_settings()
    assert s.studio_port == 8100
    assert s.image_backend == "mock"
    assert load_settings(cwd=tmp_path / "elsewhere").studio_port == DEFAULT_STUDIO_PORT


def test_config_env_prefix_comic_smith(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("STUDIO_PORT", "1234")
    monkeypatch.setenv("AUDIO_SMITH_STUDIO_PORT", "1234")
    assert load_settings().studio_port == DEFAULT_STUDIO_PORT
    monkeypatch.setenv("COMIC_SMITH_STUDIO_PORT", "1234")
    assert load_settings().studio_port == 1234


def test_config_ollama_host_conventional_name(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OLLAMA_HOST", "http://ollama:11434")
    assert load_settings().ollama_host == "http://ollama:11434"


def test_config_unknown_key_warns(tmp_path: Path) -> None:
    _write_toml(tmp_path, "colour = 1\n")
    assert any("colour" in w for w in load_settings().config_warnings)


def test_config_secret_key_in_file_rejected(tmp_path: Path) -> None:
    _write_toml(tmp_path, 'server_token = "abc"\n')
    with pytest.raises(ConfigError, match="secret"):
        load_settings()


def test_config_invalid_value_raises_config_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COMIC_SMITH_DEFAULT_AUDIENCE", "toddlers")
    with pytest.raises(ConfigError, match="default_audience"):
        load_settings()


def test_config_bad_toml_raises(tmp_path: Path) -> None:
    _write_toml(tmp_path, "studio_port = [\n")
    with pytest.raises(ConfigError, match="Cannot read"):
        load_settings()


def test_config_explicit_missing_path_raises(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="not found"):
        find_config_file(tmp_path / "nope.toml")


def test_config_user_config_dir_is_searched(tmp_path: Path) -> None:
    user = Path.home() / ".config" / "comic-smith"
    user.mkdir(parents=True)
    (user / "comic-smith.toml").write_text("studio_port = 8300\n", encoding="utf-8")
    assert load_settings(cwd=tmp_path / "empty").studio_port == 8300


def test_config_redacted_masks_secrets(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COMIC_SMITH_SERVER_TOKEN", "hunter2")
    data = load_settings().redacted()
    assert data["server_token"] == "***"
    assert "hunter2" not in str(data)


def test_config_derived_dirs_under_data_dir(tmp_path: Path) -> None:
    s = Settings(data_dir=tmp_path / "d")
    assert s.projects_dir == tmp_path / "d" / "projects"
    assert s.library_dir.name == "library"
    assert s.exports_dir.name == "exports"
