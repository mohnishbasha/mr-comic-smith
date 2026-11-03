"""Provider strings (ADR-017) and the factories that turn Settings into providers."""

from comic_smith.backends.llm.anthropic import AnthropicProvider
from comic_smith.backends.llm.base import EmbeddingsProvider, LLMProvider, ProviderKind, ProviderSpec
from comic_smith.backends.llm.fake import FakeEmbeddings, FakeLLMProvider
from comic_smith.backends.llm.ollama import OllamaEmbeddings, OllamaProvider
from comic_smith.backends.llm.openai_compat import OpenAICompatEmbeddings, OpenAICompatProvider
from comic_smith.config import Settings
from comic_smith.errors import ProviderStringError

LLM_KINDS: tuple[ProviderKind, ...] = ("ollama", "anthropic", "openai_compat", "fake")
EMBEDDING_KINDS: tuple[ProviderKind, ...] = ("ollama", "openai_compat", "fake")
URL_ENV_HINT = "Set COMIC_SMITH_OPENAI_COMPAT_URL, or write openai_compat:<base_url>#<model>."


def _bad(s: str, why: str) -> ProviderStringError:
    return ProviderStringError(
        f"The provider string '{s}' is not valid: {why}.",
        hint="Examples: ollama:qwen3:14b, anthropic:<model-id>, openai_compat:<base_url>#<model>, fake.",
    )


def parse_provider_string(s: str, *, allowed: tuple[ProviderKind, ...] = LLM_KINDS) -> ProviderSpec:
    """Split on the first colon only; the model may itself contain colons."""
    text = s.strip()
    if not text:
        raise _bad(s, "it is empty")
    kind, _, rest = text.partition(":")
    if kind not in allowed:
        raise _bad(s, f"unknown provider '{kind}' (use one of {', '.join(allowed)})")
    if kind == "fake":
        if rest:
            raise _bad(s, "'fake' takes no model")
        return ProviderSpec(kind="fake")
    if not rest:
        raise _bad(s, f"'{kind}' needs a model")
    if kind == "openai_compat" and "#" in rest:
        base_url, _, model = rest.rpartition("#")
        if not base_url.startswith(("http://", "https://")) or not model:
            raise _bad(s, "expected openai_compat:<http(s) base_url>#<model>")
        return ProviderSpec(kind="openai_compat", model=model, base_url=base_url)
    return ProviderSpec(kind=kind, model=rest)


def _compat_url(spec: ProviderSpec, settings: Settings) -> str:
    url = spec.base_url or settings.openai_compat_url
    if not url:
        raise _bad(f"openai_compat:{spec.model}", f"no base URL. {URL_ENV_HINT}")
    return url


def build_llm(spec: ProviderSpec, settings: Settings) -> LLMProvider:
    model = spec.model or ""
    if spec.kind == "ollama":
        return OllamaProvider(model, settings.ollama_host)
    if spec.kind == "anthropic":
        return AnthropicProvider(model)
    if spec.kind == "openai_compat":
        return OpenAICompatProvider(model, _compat_url(spec, settings))
    return _fake_llm()


def _fake_llm() -> FakeLLMProvider:
    """A fake provider with the story answers registered (imported lazily: backends stay a leaf)."""
    from comic_smith.story.fake_responses import ensure_registered  # noqa: PLC0415

    ensure_registered()
    return FakeLLMProvider()


def build_embeddings(spec: ProviderSpec, settings: Settings) -> EmbeddingsProvider:
    model = spec.model or ""
    if spec.kind == "ollama":
        return OllamaEmbeddings(model, settings.ollama_host)
    if spec.kind == "openai_compat":
        return OpenAICompatEmbeddings(model, _compat_url(spec, settings))
    return FakeEmbeddings()


def get_llm(settings: Settings) -> LLMProvider:
    return build_llm(parse_provider_string(settings.llm), settings)


def get_embeddings(settings: Settings) -> EmbeddingsProvider:
    return build_embeddings(parse_provider_string(settings.embeddings, allowed=EMBEDDING_KINDS), settings)
