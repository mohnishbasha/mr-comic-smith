"""OpenAI-compatible adapters over respx (S1-T01)."""

import json
from typing import Any

import httpx
import pytest
import respx

from comic_smith.backends.llm.openai_compat import OpenAICompatEmbeddings, OpenAICompatProvider
from comic_smith.errors import BackendUnavailableError

BASE = "http://oai.test/v1"
SCHEMA: dict[str, Any] = {"type": "object", "properties": {"a": {"type": "string"}}, "required": ["a"]}


def completion(content: str, **usage: int) -> httpx.Response:
    return httpx.Response(200, json={"choices": [{"message": {"content": content}}], "usage": usage})


@respx.mock
def test_llm_openai_compat_response_format_json_schema(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    route = respx.post(f"{BASE}/chat/completions").mock(
        return_value=completion('{"a": "yo"}', prompt_tokens=4, completion_tokens=2)
    )
    p = OpenAICompatProvider("gpt-x", BASE + "/")
    assert p.complete_json("sys", "usr", SCHEMA, temperature=0.5, seed=3) == {"a": "yo"}
    request = route.calls[0].request
    body = json.loads(request.content)
    assert body["response_format"]["type"] == "json_schema"
    assert body["response_format"]["json_schema"]["schema"] == SCHEMA
    assert body["response_format"]["json_schema"]["strict"] is False
    assert body["seed"] == 3 and body["temperature"] == 0.5
    assert request.headers["Authorization"] == "Bearer sk-test"
    assert (p.last_usage.prompt_tokens, p.last_usage.completion_tokens) == (4, 2)


@respx.mock
def test_llm_openai_compat_no_auth_header_without_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    route = respx.post(f"{BASE}/chat/completions").mock(return_value=completion('{"a": "x"}'))
    OpenAICompatProvider("m", BASE).complete_json("s", "u", SCHEMA, temperature=0, seed=None)
    assert "Authorization" not in route.calls[0].request.headers
    assert "seed" not in json.loads(route.calls[0].request.content)


@respx.mock
def test_llm_openai_compat_empty_choices_is_invalid_reply() -> None:
    from comic_smith.errors import LLMOutputInvalidError

    respx.post(f"{BASE}/chat/completions").mock(return_value=httpx.Response(200, json={"choices": []}))
    with pytest.raises(LLMOutputInvalidError):
        OpenAICompatProvider("m", BASE).complete_json("s", "u", SCHEMA, temperature=0, seed=None)


@respx.mock
def test_llm_openai_compat_preflight() -> None:
    respx.get(f"{BASE}/models").mock(return_value=httpx.Response(200, json={"data": [{"id": "m1"}]}))
    assert OpenAICompatProvider("m1", BASE).preflight() == []
    assert OpenAICompatProvider("zz", BASE).preflight()[0].component == "llm"
    respx.get(f"{BASE}/models").mock(side_effect=httpx.ConnectError("no"))
    assert OpenAICompatEmbeddings("m1", BASE, sleep=lambda _: None).preflight()[0].component == "embeddings"


@respx.mock
def test_llm_openai_compat_embeddings_ordered_by_index_and_normalized() -> None:
    route = respx.post(f"{BASE}/embeddings").mock(
        return_value=httpx.Response(
            200,
            json={"data": [{"index": 1, "embedding": [0.0, 5.0]}, {"index": 0, "embedding": [3.0, 4.0]}]},
        )
    )
    e = OpenAICompatEmbeddings("emb", BASE)
    vectors = e.embed(["a", "b"])
    assert json.loads(route.calls[0].request.content) == {"model": "emb", "input": ["a", "b"]}
    assert vectors == [pytest.approx([0.6, 0.8]), pytest.approx([0.0, 1.0])]
    assert e.dimensions == 2 and e.embed([]) == []


@respx.mock
def test_llm_openai_compat_embeddings_count_mismatch_raises() -> None:
    respx.post(f"{BASE}/embeddings").mock(return_value=httpx.Response(200, json={"data": []}))
    with pytest.raises(BackendUnavailableError):
        OpenAICompatEmbeddings("emb", BASE).embed(["a"])
