"""Ollama adapters (ADR-012): structured chat via /api/chat and embeddings via /api/embed.

Verified against Ollama 0.18 (ARCHITECTURE 13.2): `format` accepts a JSON schema, `think: false`
turns off qwen3 reasoning, and `/api/embed` takes a list of inputs.
"""

import math
import time
from collections.abc import Callable
from typing import Any

import httpx

from comic_smith.backends.llm._common import (
    DEFAULT_TIMEOUT_S,
    PREFLIGHT_TIMEOUT_S,
    HttpJson,
    JsonProviderBase,
    OutputParseError,
    Usage,
    as_dict,
    as_floats,
    as_int,
    as_list,
    model_present,
    parse_json_text,
    unreachable_issue,
)
from comic_smith.backends.llm.base import PreflightIssue
from comic_smith.errors import BackendUnavailableError, ComicSmithError, ModelMissingError


def _tags_issues(http: HttpJson, host: str, model: str, component: str) -> list[PreflightIssue]:
    try:
        tags = http.get(f"{host}/api/tags", timeout=PREFLIGHT_TIMEOUT_S)
    except BackendUnavailableError as e:
        return [unreachable_issue(component, "Ollama", e)]
    names = {str(as_dict(m).get("name", "")) for m in as_list(tags.get("models"))}
    if model_present(model, names):
        return []
    return [
        PreflightIssue(
            component=component,
            message=f"The model {model} is not installed in Ollama.",
            hint=f"Run `ollama pull {model}`.",
        )
    ]


def _missing_model_mapper(model: str) -> Callable[[int, str], ComicSmithError | None]:
    def mapper(status: int, body: str) -> ComicSmithError | None:
        if status == 404 and "not found" in body.lower():
            return ModelMissingError(
                f"The model {model} is not installed in Ollama.",
                hint=f"Run `ollama pull {model}`.",
                detail=body[:200],
            )
        return None

    return mapper


class OllamaProvider(JsonProviderBase):
    """Constrained JSON decoding by passing the schema as `format`."""

    def __init__(
        self,
        model: str,
        host: str,
        *,
        client: httpx.Client | None = None,
        timeout: float = DEFAULT_TIMEOUT_S,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        super().__init__()
        self.id = "ollama"
        self.model = model
        self.host = host.rstrip("/")
        self.http = HttpJson("Ollama", client=client, timeout=timeout, sleep=sleep)

    def preflight(self) -> list[PreflightIssue]:
        return _tags_issues(self.http, self.host, self.model, "llm")

    def _generate(
        self, system: str, user: str, schema: dict[str, Any], *, temperature: float, seed: int | None
    ) -> object:
        options: dict[str, Any] = {"temperature": temperature}
        if seed is not None:
            options["seed"] = seed
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "format": schema,
            "stream": False,
            "think": False,
            "options": options,
        }
        mapper = _missing_model_mapper(self.model)
        data = self.http.post(f"{self.host}/api/chat", payload, error_mapper=mapper)
        self._add_usage(
            Usage(
                prompt_tokens=as_int(data.get("prompt_eval_count")),
                completion_tokens=as_int(data.get("eval_count")),
            )
        )
        content = as_dict(data.get("message")).get("content")
        if not isinstance(content, str):
            raise OutputParseError("reply had no message content")
        return parse_json_text(content)


def l2_normalize(vector: list[float]) -> list[float]:
    norm = math.sqrt(sum(x * x for x in vector))
    return [x / norm for x in vector] if norm else list(vector)


class OllamaEmbeddings:
    """Sentence embeddings from /api/embed, L2-normalized so cosine equals the dot product."""

    def __init__(
        self,
        model: str,
        host: str,
        *,
        client: httpx.Client | None = None,
        timeout: float = DEFAULT_TIMEOUT_S,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.id = "ollama"
        self.model = model
        self.host = host.rstrip("/")
        self.dimensions: int | None = None
        self.http = HttpJson("Ollama", client=client, timeout=timeout, sleep=sleep)

    def preflight(self) -> list[PreflightIssue]:
        return _tags_issues(self.http, self.host, self.model, "embeddings")

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        data = self.http.post(
            f"{self.host}/api/embed",
            {"model": self.model, "input": texts},
            error_mapper=_missing_model_mapper(self.model),
        )
        vectors = [as_floats(v) for v in as_list(data.get("embeddings"))]
        if len(vectors) != len(texts):
            raise BackendUnavailableError(
                "Ollama returned the wrong number of embeddings.", detail=f"{len(vectors)} for {len(texts)}"
            )
        result = [l2_normalize(v) for v in vectors]
        self.dimensions = len(result[0])
        return result
