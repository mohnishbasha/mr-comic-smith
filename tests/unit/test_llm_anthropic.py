"""Anthropic adapter with a fake SDK client (S1-T01); no network."""

from types import SimpleNamespace
from typing import Any

import pytest

from comic_smith.backends.llm import anthropic as mod
from comic_smith.backends.llm._common import ProviderTimeoutError
from comic_smith.backends.llm.anthropic import AnthropicProvider
from comic_smith.errors import BackendUnavailableError, LLMOutputInvalidError

SCHEMA: dict[str, Any] = {"type": "object", "properties": {"a": {"type": "string"}}, "required": ["a"]}


class APIConnectionError(Exception):
    """Same class name the SDK uses; the adapter classifies by name."""


class APITimeoutError(Exception):
    pass


class StatusError(Exception):
    def __init__(self, status: int) -> None:
        super().__init__(f"status {status}")
        self.status_code = status


def tool_reply(payload: dict[str, Any], tin: int = 11, tout: int = 5) -> SimpleNamespace:
    block = SimpleNamespace(type="tool_use", name="reply", input=payload)
    return SimpleNamespace(
        content=[SimpleNamespace(type="text", text="..."), block],
        usage=SimpleNamespace(input_tokens=tin, output_tokens=tout),
    )


class FakeClient:
    def __init__(self, *replies: object) -> None:
        self.replies = list(replies)
        self.calls: list[dict[str, Any]] = []
        self.messages = SimpleNamespace(create=self._create)

    def _create(self, **kwargs: Any) -> object:
        self.calls.append(kwargs)
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply


def make(client: FakeClient) -> AnthropicProvider:
    return AnthropicProvider("some-model-id", client=client, sleep=lambda _: None)


def test_llm_anthropic_provider_uses_tool_use_for_json() -> None:
    client = FakeClient(tool_reply({"a": "hi"}))
    p = make(client)
    assert p.complete_json("sys", "usr", SCHEMA, temperature=0.3, seed=1) == {"a": "hi"}
    call = client.calls[0]
    assert call["model"] == "some-model-id"
    assert call["tools"][0]["input_schema"] == SCHEMA
    assert call["tool_choice"] == {"type": "tool", "name": call["tools"][0]["name"]}
    assert call["system"] == "sys" and call["temperature"] == 0.3
    assert (p.last_usage.prompt_tokens, p.last_usage.completion_tokens) == (11, 5)


def test_llm_anthropic_corrective_retry_then_failure() -> None:
    client = FakeClient(tool_reply({"b": 1}), tool_reply({"a": "ok"}))
    assert make(client).complete_json("s", "u", SCHEMA, temperature=0, seed=None) == {"a": "ok"}
    assert "did not match the schema" in client.calls[1]["messages"][0]["content"]
    bad = FakeClient(tool_reply({}), tool_reply({}))
    with pytest.raises(LLMOutputInvalidError):
        make(bad).complete_json("s", "u", SCHEMA, temperature=0, seed=None)


def test_llm_anthropic_no_tool_call_is_invalid_reply() -> None:
    empty = SimpleNamespace(content=[SimpleNamespace(type="text", text="x")], usage=None)
    with pytest.raises(LLMOutputInvalidError):
        make(FakeClient(empty, empty)).complete_json("s", "u", SCHEMA, temperature=0, seed=None)


def test_llm_anthropic_transient_errors_retry_once() -> None:
    client = FakeClient(StatusError(503), tool_reply({"a": "x"}))
    assert make(client).complete_json("s", "u", SCHEMA, temperature=0, seed=None) == {"a": "x"}
    assert len(client.calls) == 2
    conn = FakeClient(APIConnectionError(), APIConnectionError())
    with pytest.raises(BackendUnavailableError) as info:
        make(conn).complete_json("s", "u", SCHEMA, temperature=0, seed=None)
    assert "Cannot reach" in info.value.message


def test_llm_anthropic_timeout_and_client_errors() -> None:
    with pytest.raises(ProviderTimeoutError):
        make(FakeClient(APITimeoutError(), APITimeoutError())).complete_json(
            "s", "u", SCHEMA, temperature=0, seed=None
        )
    client = FakeClient(StatusError(401))
    with pytest.raises(BackendUnavailableError) as info:
        make(client).complete_json("s", "u", SCHEMA, temperature=0, seed=None)
    assert len(client.calls) == 1 and not info.value.retryable and "API key" in (info.value.hint or "")


def test_llm_anthropic_unknown_exceptions_propagate() -> None:
    with pytest.raises(ZeroDivisionError):
        make(FakeClient(ZeroDivisionError())).complete_json("s", "u", SCHEMA, temperature=0, seed=None)


def test_llm_anthropic_preflight_reports_missing_sdk_and_key(monkeypatch: pytest.MonkeyPatch) -> None:
    p = AnthropicProvider("m")
    monkeypatch.setattr(mod, "sdk_available", lambda: False)
    assert "anthropic" in (p.preflight()[0].hint or "")
    with pytest.raises(BackendUnavailableError):
        p.complete_json("s", "u", SCHEMA, temperature=0, seed=None)
    monkeypatch.setattr(mod, "sdk_available", lambda: True)
    monkeypatch.setattr(mod, "find_api_key", lambda: None)
    assert "API key" in p.preflight()[0].message
    with pytest.raises(BackendUnavailableError):
        p.complete_json("s", "u", SCHEMA, temperature=0, seed=None)
    monkeypatch.setattr(mod, "find_api_key", lambda: "k")
    assert p.preflight() == []
    assert make(FakeClient()).preflight() == []


def test_llm_anthropic_builds_client_with_key_and_no_sdk_retries(monkeypatch: pytest.MonkeyPatch) -> None:
    made: dict[str, Any] = {}
    client = FakeClient(tool_reply({"a": "z"}))

    def fake_build(key: str, timeout: float) -> FakeClient:
        made.update(key=key, timeout=timeout)
        return client

    monkeypatch.setattr(mod, "sdk_available", lambda: True)
    monkeypatch.setattr(mod, "find_api_key", lambda: "secret")
    monkeypatch.setattr(mod, "_build_client", fake_build)
    assert AnthropicProvider("m", timeout=9).complete_json("s", "u", SCHEMA, temperature=0, seed=None) == {
        "a": "z"
    }
    assert made == {"key": "secret", "timeout": 9}


def test_llm_anthropic_find_api_key_env_then_keyring(monkeypatch: pytest.MonkeyPatch) -> None:
    import keyring

    monkeypatch.setenv("ANTHROPIC_API_KEY", "from-env")
    assert mod.find_api_key() == "from-env"
    monkeypatch.delenv("ANTHROPIC_API_KEY")
    seen: list[tuple[str, str]] = []
    monkeypatch.setattr(keyring, "get_password", lambda s, u: seen.append((s, u)) or "from-ring")
    assert mod.find_api_key() == "from-ring" and seen[0][0] == "mr-comic-smith"

    def boom(s: str, u: str) -> str:
        raise RuntimeError("no backend")

    monkeypatch.setattr(keyring, "get_password", boom)
    assert mod.find_api_key() is None
