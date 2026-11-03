"""Shared provider behavior: corrective retry, usage, transport retries (S1-T01)."""

from typing import Any

import httpx
import pytest
import respx

from comic_smith.backends.llm._common import ProviderTimeoutError, Usage, validation_errors
from comic_smith.backends.llm.ollama import OllamaProvider
from comic_smith.errors import BackendUnavailableError, LLMOutputInvalidError

SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {"title": {"type": "string"}, "n": {"type": "integer"}},
    "required": ["title"],
    "additionalProperties": False,
}
HOST = "http://ollama.test"


def chat_reply(content: str, **extra: Any) -> httpx.Response:
    return httpx.Response(200, json={"message": {"role": "assistant", "content": content}, **extra})


def make(sleeps: list[float] | None = None, **kw: Any) -> OllamaProvider:
    rec = sleeps if sleeps is not None else []
    return OllamaProvider("m", HOST, sleep=rec.append, **kw)


def call(p: OllamaProvider) -> dict[str, Any]:
    return p.complete_json("sys", "user text", SCHEMA, temperature=0.0, seed=1)


@respx.mock
def test_llm_complete_json_invalid_output_one_corrective_retry() -> None:
    route = respx.post(f"{HOST}/api/chat").mock(
        side_effect=[chat_reply('{"n": "x"}'), chat_reply('{"title": "ok"}')]
    )
    assert call(make()) == {"title": "ok"}
    assert route.call_count == 2
    import json

    second = json.loads(route.calls[1].request.content)["messages"][1]["content"]
    assert "Your previous reply did not match the schema" in second
    assert "title" in second and "user text" in second


@respx.mock
def test_llm_complete_json_second_failure_raises() -> None:
    route = respx.post(f"{HOST}/api/chat").mock(side_effect=[chat_reply("not json"), chat_reply("{}")])
    with pytest.raises(LLMOutputInvalidError) as info:
        call(make())
    assert route.call_count == 2
    assert info.value.detail and "title" in info.value.detail
    assert info.value.retryable


@respx.mock
def test_llm_retry_backoff_on_5xx() -> None:
    sleeps: list[float] = []
    route = respx.post(f"{HOST}/api/chat").mock(
        side_effect=[httpx.Response(503, text="busy"), chat_reply('{"title": "a"}')]
    )
    assert call(make(sleeps)) == {"title": "a"}
    assert route.call_count == 2
    assert sleeps == [1.0]


@respx.mock
def test_llm_retry_gives_up_after_two_attempts_on_429_and_transport_errors() -> None:
    respx.post(f"{HOST}/api/chat").mock(return_value=httpx.Response(429, text="slow down"))
    with pytest.raises(BackendUnavailableError):
        call(make())
    respx.post(f"{HOST}/api/chat").mock(side_effect=httpx.ConnectError("refused"))
    with pytest.raises(BackendUnavailableError) as info:
        call(make())
    assert "Cannot reach" in info.value.message


@respx.mock
def test_llm_non_retryable_4xx_surfaces_without_retry() -> None:
    route = respx.post(f"{HOST}/api/chat").mock(return_value=httpx.Response(400, text="bad"))
    with pytest.raises(BackendUnavailableError) as info:
        call(make())
    assert route.call_count == 1
    assert not info.value.retryable


@respx.mock
def test_llm_timeout_raises_provider_timeout() -> None:
    route = respx.post(f"{HOST}/api/chat").mock(side_effect=httpx.ReadTimeout("slow"))
    with pytest.raises(ProviderTimeoutError) as info:
        call(make(timeout=3))
    assert route.call_count == 2
    assert "3 seconds" in info.value.message


@respx.mock
def test_llm_token_usage_recorded_per_call() -> None:
    respx.post(f"{HOST}/api/chat").mock(
        side_effect=[
            chat_reply('{"title": "a"}', prompt_eval_count=10, eval_count=5),
            chat_reply('{"title": "b"}', prompt_eval_count=7, eval_count=3),
        ]
    )
    p = make()
    call(p)
    assert p.last_usage == Usage(prompt_tokens=10, completion_tokens=5)
    call(p)
    assert p.last_usage == Usage(prompt_tokens=7, completion_tokens=3)
    assert p.usage_total == Usage(prompt_tokens=17, completion_tokens=8)


@respx.mock
def test_llm_usage_counts_corrective_retry_in_one_call() -> None:
    respx.post(f"{HOST}/api/chat").mock(
        side_effect=[
            chat_reply("{}", prompt_eval_count=10, eval_count=2),
            chat_reply('{"title": "a"}', prompt_eval_count=12, eval_count=4),
        ]
    )
    p = make()
    call(p)
    assert p.last_usage == Usage(prompt_tokens=22, completion_tokens=6)


def test_llm_validation_errors_reports_paths_and_non_objects() -> None:
    assert validation_errors({"title": "x"}, SCHEMA) == []
    assert validation_errors([1], SCHEMA) == ["reply must be a JSON object"]
    errs = validation_errors({"title": 1, "n": "x"}, SCHEMA)
    assert len(errs) == 2 and errs[0].startswith("n:")
