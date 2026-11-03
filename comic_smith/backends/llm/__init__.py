"""LLM and embeddings providers (ARCHITECTURE 7.8). Import from here, not from adapter modules."""

from comic_smith.backends.llm.base import (
    EmbeddingsProvider,
    LLMProvider,
    PreflightIssue,
    ProviderSpec,
)
from comic_smith.backends.llm.providers import get_embeddings, get_llm, parse_provider_string

__all__ = [
    "EmbeddingsProvider",
    "LLMProvider",
    "PreflightIssue",
    "ProviderSpec",
    "get_embeddings",
    "get_llm",
    "parse_provider_string",
]
