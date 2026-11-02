"""Settings with documented precedence (ARCHITECTURE 12.2): flags > env > comic-smith.toml > defaults.

The project file is searched at --config PATH, then ./comic-smith.toml, then the user config
directory. Unknown keys in the file produce warnings so a newer config still loads; a key that
looks like a secret is a ConfigError because secrets only come from the environment or keyring.
"""

import re
import tomllib
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Literal

from pydantic import AliasChoices, Field, SecretStr, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict

from comic_smith.errors import ConfigError

PROJECT_FILE = "comic-smith.toml"
USER_CONFIG_FILE = Path("~/.config/comic-smith") / PROJECT_FILE
SECRET_KEY_RE = re.compile(r"(key|token|secret)", re.IGNORECASE)
REDACTED = "***"
DEFAULT_STUDIO_PORT = 7351
DEFAULT_SERVER_PORT = 7350
DEFAULT_QA_MIN_SCORE = 4
DEFAULT_QA_MAX_RETAKES = 2

Audience = Literal["all-ages", "kids-5-8", "kids-9-12", "teen", "adult"]


class Settings(BaseSettings):
    """All runtime configuration. Defaults equal the prod column of the environment model."""

    model_config = SettingsConfigDict(env_prefix="COMIC_SMITH_", extra="ignore", populate_by_name=True)

    env: Literal["dev", "stage", "prod"] = "prod"
    data_dir: Path = Path("~/ComicSmith")
    log_level: Literal["debug", "info", "warning", "error"] = "info"
    log_format: Literal["pretty", "json"] = "pretty"
    image_backend: str = "comfyui"
    comfyui_url: str = "http://127.0.0.1:8188"
    comfyui_workflow: str = "qwen-image-edit"
    allow_noncommercial: bool = False
    llm: str = "ollama:qwen3:14b"
    vision: str = "ollama:qwen2.5vl:7b"
    embeddings: str = "ollama:nomic-embed-text"
    openai_compat_url: str | None = None
    ollama_host: str = Field(
        default="http://127.0.0.1:11434",
        validation_alias=AliasChoices("COMIC_SMITH_OLLAMA_HOST", "OLLAMA_HOST", "ollama_host"),
    )
    qa_min_score: int = Field(default=DEFAULT_QA_MIN_SCORE, ge=1, le=5)
    qa_max_retakes: int = Field(default=DEFAULT_QA_MAX_RETAKES, ge=0, le=10)
    studio_port: int = Field(default=DEFAULT_STUDIO_PORT, ge=1, le=65535)
    server_host: str = "127.0.0.1"
    server_port: int = Field(default=DEFAULT_SERVER_PORT, ge=1, le=65535)
    server_token: SecretStr | None = None
    access_code: SecretStr | None = None
    default_audience: Audience = "all-ages"
    config_file: Path | None = Field(default=None, exclude=True)
    config_warnings: list[str] = Field(default_factory=list, exclude=True)

    def resolved(self, path: Path) -> Path:
        """Expand ~ so every consumer sees an absolute path."""
        return path.expanduser()

    @property
    def projects_dir(self) -> Path:
        return self.resolved(self.data_dir) / "projects"

    @property
    def library_dir(self) -> Path:
        return self.resolved(self.data_dir) / "library"

    @property
    def exports_dir(self) -> Path:
        return self.resolved(self.data_dir) / "exports"

    def redacted(self) -> dict[str, Any]:
        """Dump for display or logs with every secret-looking value masked."""
        data = self.model_dump(mode="json")
        return {k: (REDACTED if SECRET_KEY_RE.search(k) and v is not None else v) for k, v in data.items()}


def find_config_file(explicit: Path | None = None, cwd: Path | None = None) -> Path | None:
    """Return the first config file in the documented search order, or None."""
    if explicit is not None:
        if not explicit.is_file():
            raise ConfigError(f"Config file not found: {explicit}", hint="Check the --config path.")
        return explicit
    for candidate in ((cwd or Path.cwd()) / PROJECT_FILE, USER_CONFIG_FILE.expanduser()):
        if candidate.is_file():
            return candidate
    return None


def _read_file(path: Path) -> tuple[dict[str, Any], list[str]]:
    try:
        raw = tomllib.loads(path.read_text(encoding="utf-8"))
    except (tomllib.TOMLDecodeError, OSError) as e:
        raise ConfigError(f"Cannot read {path}: {e}", hint="Fix the TOML syntax in the config file.") from e
    known = set(Settings.model_fields) - {"config_warnings", "config_file"}
    data: dict[str, Any] = {}
    warnings: list[str] = []
    for key, value in raw.items():
        if SECRET_KEY_RE.search(key):
            raise ConfigError(
                f"{path}: '{key}' looks like a secret and cannot live in a config file",
                hint="Set it as an environment variable or in the OS keyring instead.",
            )
        if key not in known:
            warnings.append(f"{path}: unknown key '{key}' ignored")
        else:
            data[key] = value
    return data, warnings


def load_settings(
    overrides: Mapping[str, Any] | None = None,
    config_path: Path | None = None,
    cwd: Path | None = None,
) -> Settings:
    """Build Settings honoring the precedence order. None-valued overrides are ignored."""
    path = find_config_file(config_path, cwd)
    file_data, warnings = _read_file(path) if path else ({}, [])
    try:
        from_env = Settings()
        env_data = {k: getattr(from_env, k) for k in from_env.model_fields_set}
        cli_data = {k: v for k, v in (overrides or {}).items() if v is not None}
        merged = {**file_data, **env_data, **cli_data, "config_warnings": warnings, "config_file": path}
        return Settings(**merged)
    except ValidationError as e:
        first = e.errors()[0]
        key = ".".join(str(p) for p in first["loc"])
        raise ConfigError(
            f"Invalid configuration value for '{key}': {first['msg']}",
            hint="Check the flag, the COMIC_SMITH_ environment variable, or comic-smith.toml.",
        ) from e
