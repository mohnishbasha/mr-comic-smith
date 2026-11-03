"""Ollama adapters over respx (S1-T01)."""

import json
import math
from typing import Any

import httpx
import pytest
import respx

from comic_smith.backends.llm.ollama import OllamaEmbeddings, OllamaProvider
from comic_smith.errors import BackendUnavailableError, ModelMissingError

HOST = "http://ollama.test"
SCHEMA: dict[str, Any] = {"type": "object", "properties": {"a": {"type": "string"}}, "required": ["a"]}


@respx.mock
def test_llm_ollama_chat_request_sends_schema_in_format() -> None:
    route = respx.post(f"{HOST}/api/chat").mock(
        return_value=httpx.Response(200, json={"message": {"content": '{"a": "hi"}'}})
    )
    p = OllamaProvider("qwen3:14b", HOST + "/")
    assert p.complete_json("sys", "usr", SCHEMA, temperature=0.8, seed=7) == {"a": "hi"}
    body = json.loads(route.calls[0].request.content)
    assert body["format"] == SCHEMA
    assert body["stream"] is False
    assert body["think"] is False
    assert body["model"] == "qwen3:14b"
    assert body["options"] == {"temperature": 0.8, "seed": 7}
    assert body["messages"][0] == {"role": "system", "content": "sys"}


@respx.mock
def test_llm_ollama_omits_seed_when_none_and_strips_think_block() -> None:
    route = respx.post(f"{HOST}/api/chat").mock(
        return_value=httpx.Response(200, json={"message": {"content": '<think>hmm</think>{"a": "x"}'}})
    )
    assert OllamaProvider("m", HOST).complete_json("s", "u", SCHEMA, temperature=0, seed=None) == {"a": "x"}
    assert "seed" not in json.loads(route.calls[0].request.content)["options"]


@respx.mock
def test_llm_ollama_missing_content_counts_as_invalid_reply() -> None:
    from comic_smith.errors import LLMOutputInvalidError

    respx.post(f"{HOST}/api/chat").mock(return_value=httpx.Response(200, json={}))
    with pytest.raises(LLMOutputInvalidError):
        OllamaProvider("m", HOST).complete_json("s", "u", SCHEMA, temperature=0, seed=None)


@respx.mock
def test_llm_ollama_unknown_model_maps_to_model_missing() -> None:
    respx.post(f"{HOST}/api/chat").mock(
        return_value=httpx.Response(404, json={"error": 'model "zz" not found, try pulling it first'})
    )
    with pytest.raises(ModelMissingError) as info:
        OllamaProvider("zz", HOST).complete_json("s", "u", SCHEMA, temperature=0, seed=None)
    assert info.value.hint == "Run `ollama pull zz`."


@respx.mock
def test_llm_ollama_preflight_model_present_missing_and_unreachable() -> None:
    respx.get(f"{HOST}/api/tags").mock(
        return_value=httpx.Response(
            200, json={"models": [{"name": "qwen3:14b"}, {"name": "nomic-embed-text:latest"}]}
        )
    )
    assert OllamaProvider("qwen3:14b", HOST).preflight() == []
    assert OllamaEmbeddings("nomic-embed-text", HOST).preflight() == []
    issues = OllamaProvider("llama9", HOST).preflight()
    assert issues[0].hint == "Run `ollama pull llama9`." and issues[0].required
    respx.get(f"{HOST}/api/tags").mock(side_effect=httpx.ConnectError("no"))
    down = OllamaProvider("qwen3:14b", HOST, sleep=lambda _: None).preflight()
    assert "Cannot reach Ollama" in down[0].message


@respx.mock
def test_llm_ollama_embeddings_posts_input_list_and_normalizes() -> None:
    route = respx.post(f"{HOST}/api/embed").mock(
        return_value=httpx.Response(200, json={"embeddings": [[3.0, 4.0], [0.0, 2.0]]})
    )
    e = OllamaEmbeddings("nomic-embed-text", HOST)
    assert e.dimensions is None
    vectors = e.embed(["a", "b"])
    assert json.loads(route.calls[0].request.content) == {"model": "nomic-embed-text", "input": ["a", "b"]}
    assert vectors[0] == pytest.approx([0.6, 0.8])
    assert all(math.isclose(sum(x * x for x in v), 1.0) for v in vectors)
    assert e.dimensions == 2
    assert e.embed([]) == []


@respx.mock
def test_llm_ollama_embeddings_count_mismatch_raises() -> None:
    respx.post(f"{HOST}/api/embed").mock(return_value=httpx.Response(200, json={"embeddings": [[1.0]]}))
    with pytest.raises(BackendUnavailableError):
        OllamaEmbeddings("m", HOST).embed(["a", "b"])
