"""Shared provider behavior: schema validation with one corrective retry, transport retries, usage.

Every JSON-producing provider subclasses `JsonProviderBase` and implements only `_generate`, the
single raw model call. Validation, the corrective retry (ARCHITECTURE 7.8), and token accounting
live here so all providers behave the same.
"""

import json
import re
import time
from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import Any, ClassVar

import httpx
import jsonschema
from pydantic import BaseModel

from comic_smith.backends.llm.base import PreflightIssue
from comic_smith.errors import BackendUnavailableError, ComicSmithError, LLMOutputInvalidError

DEFAULT_TIMEOUT_S = 120.0
PREFLIGHT_TIMEOUT_S = 5.0
TRANSPORT_ATTEMPTS = 2
BACKOFF_BASE_S = 1.0
MAX_REPORTED_ERRORS = 5
BODY_EXCERPT_CHARS = 300
RETRYABLE_STATUS = 429
SERVER_ERROR_MIN = 500
CLIENT_ERROR_MIN = 400
THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL)


class ProviderTimeoutError(BackendUnavailableError):
    """The backend did not answer within the timeout."""

    code = "provider_timeout"
    title = "The backend took too long to answer"


class Usage(BaseModel):
    """Token counts reported by an API; zero when the API does not report them."""

    prompt_tokens: int = 0
    completion_tokens: int = 0

    def __add__(self, other: "Usage") -> "Usage":
        return Usage(
            prompt_tokens=self.prompt_tokens + other.prompt_tokens,
            completion_tokens=self.completion_tokens + other.completion_tokens,
        )


class OutputParseError(Exception):
    """The model reply could not be parsed as JSON; treated like a schema failure."""


def as_dict(value: object) -> dict[str, Any]:
    """Narrow a decoded JSON value to an object; anything else is an empty dict."""
    return {str(k): v for k, v in value.items()} if isinstance(value, dict) else {}


def as_list(value: object) -> list[object]:
    return list(value) if isinstance(value, list) else []


def as_floats(value: object) -> list[float]:
    return [float(x) for x in as_list(value) if isinstance(x, int | float) and not isinstance(x, bool)]


def as_int(value: object) -> int:
    return value if isinstance(value, int) and not isinstance(value, bool) else 0


def parse_json_text(text: str) -> object:
    """Decode a model reply, ignoring a leading <think> block; raise OutputParseError on failure."""
    cleaned = THINK_RE.sub("", text).strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as e:
        raise OutputParseError(f"reply is not valid JSON ({e.msg} at position {e.pos})") from e


def validation_errors(instance: object, schema: dict[str, Any]) -> list[str]:
    """Human-readable schema violations; empty when the instance is valid."""
    if not isinstance(instance, dict):
        return ["reply must be a JSON object"]
    validator = jsonschema.Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(instance), key=lambda e: list(map(str, e.absolute_path)))
    return [f"{'/'.join(map(str, e.absolute_path)) or '(root)'}: {e.message}" for e in errors]


class JsonProviderBase(ABC):
    """Template for `complete_json`: generate, validate, correct once, then fail typed."""

    id: str
    kind: ClassVar[str] = "llm"

    def __init__(self) -> None:
        self.last_usage = Usage()
        self.usage_total = Usage()
        self._call_usage = Usage()

    @abstractmethod
    def _generate(
        self, system: str, user: str, schema: dict[str, Any], *, temperature: float, seed: int | None
    ) -> object:
        """One raw model call. Return the decoded JSON value; call `_add_usage` when known."""

    def _add_usage(self, usage: Usage) -> None:
        self._call_usage += usage
        self.usage_total += usage

    def complete_json(
        self, system: str, user: str, schema: dict[str, Any], *, temperature: float, seed: int | None
    ) -> dict[str, Any]:
        self._call_usage = Usage()
        try:
            return self._attempt(system, user, schema, temperature, seed)
        finally:
            self.last_usage = self._call_usage

    def _attempt(
        self, system: str, user: str, schema: dict[str, Any], temperature: float, seed: int | None
    ) -> dict[str, Any]:
        errors: list[str] = []
        message = user
        for attempt in range(2):
            try:
                reply = self._generate(system, message, schema, temperature=temperature, seed=seed)
                errors = validation_errors(reply, schema)
            except OutputParseError as e:
                reply, errors = None, [str(e)]
            if not errors:
                return as_dict(reply)
            if attempt == 0:
                message = _corrective_message(user, errors)
        raise LLMOutputInvalidError(
            "The language model did not return a usable answer, even after a second try.",
            hint="Try again, pick a larger model, or lower the temperature.",
            detail="; ".join(errors[:MAX_REPORTED_ERRORS]),
        )


def _corrective_message(user: str, errors: list[str]) -> str:
    listed = "\n".join(f"- {e}" for e in errors[:MAX_REPORTED_ERRORS])
    return (
        f"{user}\n\nYour previous reply did not match the schema:\n{listed}\n"
        "Reply again with JSON that matches the schema."
    )


ErrorMapper = Callable[[int, str], ComicSmithError | None]


class HttpJson:
    """httpx wrapper: timeout, two attempts with backoff on transient failures, typed errors."""

    def __init__(
        self,
        service: str,
        *,
        client: httpx.Client | None = None,
        timeout: float = DEFAULT_TIMEOUT_S,
        sleep: Callable[[float], None] = time.sleep,
        backoff_s: float = BACKOFF_BASE_S,
    ) -> None:
        self.service = service
        self.client = client or httpx.Client(timeout=timeout)
        self.timeout = timeout
        self.sleep = sleep
        self.backoff_s = backoff_s

    def post(
        self,
        url: str,
        payload: dict[str, Any],
        headers: dict[str, str] | None = None,
        error_mapper: ErrorMapper | None = None,
    ) -> dict[str, Any]:
        return self._request("POST", url, payload, headers, error_mapper, self.timeout)

    def get(
        self, url: str, headers: dict[str, str] | None = None, timeout: float | None = None
    ) -> dict[str, Any]:
        return self._request("GET", url, None, headers, None, timeout or self.timeout)

    def _request(
        self,
        method: str,
        url: str,
        payload: dict[str, Any] | None,
        headers: dict[str, str] | None,
        error_mapper: ErrorMapper | None,
        timeout: float,
    ) -> dict[str, Any]:
        failure: ComicSmithError | None = None
        for attempt in range(TRANSPORT_ATTEMPTS):
            if attempt:
                self.sleep(self.backoff_s * 2 ** (attempt - 1))
            try:
                response = self.client.request(method, url, json=payload, headers=headers, timeout=timeout)
            except httpx.TimeoutException as e:
                failure = ProviderTimeoutError(
                    f"{self.service} did not answer within {timeout:.0f} seconds.",
                    hint="Try again, or use a smaller model.",
                    detail=type(e).__name__,
                    retryable=True,
                )
                continue
            except httpx.TransportError as e:
                failure = BackendUnavailableError(
                    f"Cannot reach {self.service}.",
                    hint=f"Check that {self.service} is running and the address is right.",
                    detail=f"{type(e).__name__}: {e}",
                )
                continue
            status = response.status_code
            if status == RETRYABLE_STATUS or status >= SERVER_ERROR_MIN:
                failure = BackendUnavailableError(
                    f"{self.service} is busy or failing (HTTP {status}).",
                    hint="Wait a moment and try again.",
                    detail=response.text[:BODY_EXCERPT_CHARS],
                )
                continue
            if status >= CLIENT_ERROR_MIN:
                raise self._client_error(status, response.text, error_mapper)
            return as_dict(response.json())
        assert failure is not None  # noqa: S101 - loop ran at least once
        raise failure

    def _client_error(self, status: int, body: str, mapper: ErrorMapper | None) -> ComicSmithError:
        mapped = mapper(status, body) if mapper else None
        if mapped is not None:
            return mapped
        return BackendUnavailableError(
            f"{self.service} rejected the request (HTTP {status}).",
            hint="Check the model name and your credentials.",
            detail=body[:BODY_EXCERPT_CHARS],
            retryable=False,
        )


def model_present(model: str, names: set[str]) -> bool:
    """True when `model` is among `names`, treating a bare name as `name:latest`."""
    return model in names or (":" not in model and f"{model}:latest" in names)


def unreachable_issue(component: str, service: str, error: ComicSmithError) -> PreflightIssue:
    return PreflightIssue(
        component=component,
        message=f"Cannot reach {service}: {error.message}",
        hint=error.hint,
    )
