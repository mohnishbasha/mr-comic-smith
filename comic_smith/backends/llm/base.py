"""LLM and embeddings provider contracts (ARCHITECTURE 7.8, ADR-007, ADR-017).

Story services depend only on these protocols; adapters live next to this module and are
selected by provider strings such as `ollama:qwen3:14b`, `anthropic:<model-id>`,
`openai_compat:<base_url>#<model>`, or `fake`.
"""

from typing import Any, Literal, Protocol

from pydantic import BaseModel

ProviderKind = Literal["ollama", "anthropic", "openai_compat", "fake"]
TEMPERATURE_INTERACTIVE = 0.8
TEMPERATURE_DETERMINISTIC = 0.0
TEMPLATE_MARKER_PREFIX = "<!-- template: "


class PreflightIssue(BaseModel):
    """One problem found before a provider is used, with a plain-words fix."""

    component: str
    message: str
    hint: str | None = None
    required: bool = True


class ProviderSpec(BaseModel):
    """A parsed provider string."""

    kind: ProviderKind
    model: str | None = None
    base_url: str | None = None


class LLMProvider(Protocol):
    """Structured-output text generation. Implementations validate against `schema`."""

    id: str

    def preflight(self) -> list[PreflightIssue]: ...

    def complete_json(
        self,
        system: str,
        user: str,
        schema: dict[str, Any],
        *,
        temperature: float,
        seed: int | None,
    ) -> dict[str, Any]: ...


class EmbeddingsProvider(Protocol):
    """Sentence embeddings used by the suggestion distinctness check (FR-011)."""

    id: str
    dimensions: int | None

    def preflight(self) -> list[PreflightIssue]: ...

    def embed(self, texts: list[str]) -> list[list[float]]: ...
