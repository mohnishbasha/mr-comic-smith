"""OpenAI-compatible adapters (LM Studio, vLLM, llama.cpp server, OpenAI): chat and embeddings."""

import os
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
from comic_smith.backends.llm.ollama import l2_normalize
from comic_smith.errors import BackendUnavailableError

API_KEY_ENV = "OPENAI_API_KEY"
SCHEMA_NAME = "reply"


def _auth_headers() -> dict[str, str]:
    key = os.environ.get(API_KEY_ENV)
    return {"Authorization": f"Bearer {key}"} if key else {}


def _models_issues(http: HttpJson, base_url: str, model: str, component: str) -> list[PreflightIssue]:
    try:
        data = http.get(f"{base_url}/models", headers=_auth_headers(), timeout=PREFLIGHT_TIMEOUT_S)
    except BackendUnavailableError as e:
        return [unreachable_issue(component, "the OpenAI-compatible server", e)]
    names = {str(as_dict(m).get("id", "")) for m in as_list(data.get("data"))}
    if not names or model_present(model, names):
        return []
    return [
        PreflightIssue(
            component=component,
            message=f"The server does not list the model {model}.",
            hint="Load that model in the server, or fix the model name in the provider string.",
        )
    ]


class OpenAICompatProvider(JsonProviderBase):
    """Chat completions with a `json_schema` response format (non-strict for broad server support)."""

    def __init__(
        self,
        model: str,
        base_url: str,
        *,
        client: httpx.Client | None = None,
        timeout: float = DEFAULT_TIMEOUT_S,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        super().__init__()
        self.id = "openai_compat"
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.http = HttpJson("the OpenAI-compatible server", client=client, timeout=timeout, sleep=sleep)

    def preflight(self) -> list[PreflightIssue]:
        return _models_issues(self.http, self.base_url, self.model, "llm")

    def _generate(
        self, system: str, user: str, schema: dict[str, Any], *, temperature: float, seed: int | None
    ) -> object:
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "temperature": temperature,
            "response_format": {
                "type": "json_schema",
                "json_schema": {"name": SCHEMA_NAME, "schema": schema, "strict": False},
            },
        }
        if seed is not None:
            payload["seed"] = seed
        data = self.http.post(f"{self.base_url}/chat/completions", payload, headers=_auth_headers())
        usage = as_dict(data.get("usage"))
        self._add_usage(
            Usage(
                prompt_tokens=as_int(usage.get("prompt_tokens")),
                completion_tokens=as_int(usage.get("completion_tokens")),
            )
        )
        choices = as_list(data.get("choices"))
        content = as_dict(as_dict(choices[0]).get("message")).get("content") if choices else None
        if not isinstance(content, str):
            raise OutputParseError("reply had no message content")
        return parse_json_text(content)


class OpenAICompatEmbeddings:
    """Embeddings from {base_url}/embeddings, L2-normalized."""

    def __init__(
        self,
        model: str,
        base_url: str,
        *,
        client: httpx.Client | None = None,
        timeout: float = DEFAULT_TIMEOUT_S,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.id = "openai_compat"
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.dimensions: int | None = None
        self.http = HttpJson("the OpenAI-compatible server", client=client, timeout=timeout, sleep=sleep)

    def preflight(self) -> list[PreflightIssue]:
        return _models_issues(self.http, self.base_url, self.model, "embeddings")

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        data = self.http.post(
            f"{self.base_url}/embeddings", {"model": self.model, "input": texts}, headers=_auth_headers()
        )
        rows = sorted((as_dict(r) for r in as_list(data.get("data"))), key=lambda r: as_int(r.get("index")))
        vectors = [as_floats(r.get("embedding")) for r in rows]
        if len(vectors) != len(texts):
            raise BackendUnavailableError(
                "The server returned the wrong number of embeddings.",
                detail=f"{len(vectors)} for {len(texts)}",
            )
        result = [l2_normalize(v) for v in vectors]
        self.dimensions = len(result[0])
        return result
