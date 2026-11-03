"""Anthropic adapter via the official SDK (optional `anthropic` extra, imported lazily).

JSON comes from a single forced tool whose `input_schema` is the requested schema, so the model
must answer with a tool call whose input is the structured result. The model id always comes from
the provider string; this module hardcodes none.
"""

import importlib
import os
import time
from collections.abc import Callable
from typing import Any, Protocol

from comic_smith.backends.llm._common import (
    DEFAULT_TIMEOUT_S,
    JsonProviderBase,
    OutputParseError,
    ProviderTimeoutError,
    Usage,
    as_dict,
    as_int,
)
from comic_smith.backends.llm.base import PreflightIssue
from comic_smith.errors import BackendUnavailableError

API_KEY_ENV = "ANTHROPIC_API_KEY"
KEYRING_SERVICE = "mr-comic-smith"
INSTALL_HINT = 'Install the extra: uv tool install "mr-comic-smith[anthropic]"'
TOOL_NAME = "reply"
MAX_OUTPUT_TOKENS = 4096
ATTEMPTS = 2
BACKOFF_BASE_S = 1.0
SERVER_ERROR_MIN = 500
RATE_LIMITED = 429
TRANSIENT_NAMES = {"APIConnectionError", "APITimeoutError", "InternalServerError", "RateLimitError"}


class _Messages(Protocol):
    def create(self, **kwargs: Any) -> object: ...


class AnthropicClient(Protocol):
    """The slice of `anthropic.Anthropic` this adapter uses (also what tests fake)."""

    messages: _Messages


def sdk_available() -> bool:
    try:
        importlib.import_module("anthropic")
    except ImportError:
        return False
    return True


def find_api_key() -> str | None:
    """ANTHROPIC_API_KEY from the environment, else the OS keyring; never logged."""
    key = os.environ.get(API_KEY_ENV)
    if key:
        return key
    try:
        import keyring  # noqa: PLC0415

        return keyring.get_password(KEYRING_SERVICE, API_KEY_ENV)
    except Exception:
        return None


def _build_client(api_key: str, timeout: float) -> AnthropicClient:
    module = importlib.import_module("anthropic")
    client: AnthropicClient = module.Anthropic(api_key=api_key, timeout=timeout, max_retries=0)
    return client


def _status(error: Exception) -> int | None:
    status = getattr(error, "status_code", None)
    return status if isinstance(status, int) else None


def _is_transient(error: Exception) -> bool:
    status = _status(error)
    if status is not None:
        return status == RATE_LIMITED or status >= SERVER_ERROR_MIN
    return type(error).__name__ in TRANSIENT_NAMES


class AnthropicProvider(JsonProviderBase):
    def __init__(
        self,
        model: str,
        *,
        client: AnthropicClient | None = None,
        timeout: float = DEFAULT_TIMEOUT_S,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        super().__init__()
        self.id = "anthropic"
        self.model = model
        self.timeout = timeout
        self.sleep = sleep
        self._client = client

    def preflight(self) -> list[PreflightIssue]:
        if self._client is not None:
            return []
        if not sdk_available():
            return [
                PreflightIssue(
                    component="llm", message="The anthropic package is not installed.", hint=INSTALL_HINT
                )
            ]
        if find_api_key() is None:
            return [
                PreflightIssue(
                    component="llm",
                    message="No Anthropic API key was found.",
                    hint=f"Set {API_KEY_ENV}, or store it in the OS keyring under service {KEYRING_SERVICE}.",
                )
            ]
        return []

    def _get_client(self) -> AnthropicClient:
        if self._client is not None:
            return self._client
        if not sdk_available():
            raise BackendUnavailableError("The anthropic package is not installed.", hint=INSTALL_HINT)
        key = find_api_key()
        if key is None:
            raise BackendUnavailableError(
                "No Anthropic API key was found.", hint=f"Set {API_KEY_ENV} or store it in the OS keyring."
            )
        self._client = _build_client(key, self.timeout)
        return self._client

    def _generate(
        self, system: str, user: str, schema: dict[str, Any], *, temperature: float, seed: int | None
    ) -> object:
        request: dict[str, Any] = {
            "model": self.model,
            "max_tokens": MAX_OUTPUT_TOKENS,
            "temperature": temperature,
            "system": system,
            "messages": [{"role": "user", "content": user}],
            "tools": [
                {"name": TOOL_NAME, "description": "Return the structured result.", "input_schema": schema}
            ],
            "tool_choice": {"type": "tool", "name": TOOL_NAME},
        }
        response = self._create(request)
        usage = getattr(response, "usage", None)
        self._add_usage(
            Usage(
                prompt_tokens=as_int(getattr(usage, "input_tokens", 0)),
                completion_tokens=as_int(getattr(usage, "output_tokens", 0)),
            )
        )
        for block in getattr(response, "content", None) or []:
            if getattr(block, "type", None) == "tool_use":
                return as_dict(getattr(block, "input", None))
        raise OutputParseError("reply contained no tool call")

    def _create(self, request: dict[str, Any]) -> object:
        client = self._get_client()
        failure: BackendUnavailableError | None = None
        for attempt in range(ATTEMPTS):
            if attempt:
                self.sleep(BACKOFF_BASE_S * 2 ** (attempt - 1))
            try:
                return client.messages.create(**request)
            except Exception as e:
                if _status(e) is None and type(e).__name__ not in TRANSIENT_NAMES:
                    raise
                failure = self._to_error(e)
                if not _is_transient(e):
                    raise failure from e
        assert failure is not None  # noqa: S101 - loop ran at least once
        raise failure

    def _to_error(self, error: Exception) -> BackendUnavailableError:
        if type(error).__name__ == "APITimeoutError":
            return ProviderTimeoutError(
                "Anthropic did not answer in time.", hint="Try again.", retryable=True
            )
        status = _status(error)
        hint = "Check your API key." if status in (401, 403) else "Try again in a moment."
        message = (
            f"Anthropic rejected the request (HTTP {status})."
            if status
            else "Cannot reach the Anthropic API."
        )
        return BackendUnavailableError(
            message, hint=hint, detail=type(error).__name__, retryable=_is_transient(error)
        )
