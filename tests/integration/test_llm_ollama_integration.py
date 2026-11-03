"""Real Ollama with a tiny model; skipped when Ollama is unreachable (S1-T01)."""

import os
from typing import Any

import httpx
import pytest

from comic_smith.backends.llm.ollama import OllamaEmbeddings, OllamaProvider
from comic_smith.config import Settings

pytestmark = pytest.mark.integration
MODEL = os.environ.get("COMIC_SMITH_IT_OLLAMA_MODEL", "qwen3:0.6b")
SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {"greeting": {"type": "string"}, "word_count": {"type": "integer"}},
    "required": ["greeting", "word_count"],
}


@pytest.fixture
def host() -> str:
    url = Settings().ollama_host
    try:
        httpx.get(f"{url}/api/tags", timeout=2).raise_for_status()
    except httpx.HTTPError:
        pytest.skip(f"Ollama is not reachable at {url}")
    return url


def it_ollama_tiny_model_returns_schema_valid_json(host: str) -> None:
    provider = OllamaProvider(MODEL, host, timeout=300)
    if provider.preflight():
        pytest.skip(f"Model {MODEL} is not installed; run `ollama pull {MODEL}`")
    out = provider.complete_json(
        "Reply with JSON only.",
        "Give a short greeting and the number of words in it.",
        SCHEMA,
        temperature=0.0,
        seed=1,
    )
    assert isinstance(out["greeting"], str) and isinstance(out["word_count"], int)
    assert provider.last_usage.prompt_tokens > 0


def it_ollama_embeddings_are_normalized(host: str) -> None:
    model = os.environ.get("COMIC_SMITH_IT_OLLAMA_EMBED_MODEL", "nomic-embed-text")
    emb = OllamaEmbeddings(model, host)
    if emb.preflight():
        pytest.skip(f"Embedding model {model} is not installed")
    vectors = emb.embed(["a red kite", "a blue kite"])
    assert len(vectors) == 2 and emb.dimensions == len(vectors[0])
    assert sum(x * x for x in vectors[0]) == pytest.approx(1.0, abs=1e-3)
