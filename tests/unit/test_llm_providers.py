"""Provider strings, factories, and doctor checks (S1-T01)."""

import httpx
import pytest
import respx

from comic_smith.backends.llm import get_embeddings, get_llm, parse_provider_string
from comic_smith.backends.llm.anthropic import AnthropicProvider
from comic_smith.backends.llm.checks import embeddings_check, llm_check
from comic_smith.backends.llm.fake import FakeEmbeddings, FakeLLMProvider
from comic_smith.backends.llm.ollama import OllamaEmbeddings, OllamaProvider
from comic_smith.backends.llm.openai_compat import OpenAICompatEmbeddings, OpenAICompatProvider
from comic_smith.config import Settings
from comic_smith.doctor import default_checks
from comic_smith.errors import ProviderStringError


def test_llm_provider_string_parsing_all_three_formats() -> None:
    s = parse_provider_string("ollama:qwen3:14b")
    assert (s.kind, s.model, s.base_url) == ("ollama", "qwen3:14b", None)
    a = parse_provider_string("anthropic:some-model-id")
    assert (a.kind, a.model) == ("anthropic", "some-model-id")
    o = parse_provider_string("openai_compat:http://localhost:1234/v1#my-model")
    assert (o.kind, o.model, o.base_url) == ("openai_compat", "my-model", "http://localhost:1234/v1")
    assert parse_provider_string("fake").kind == "fake"
    bare = parse_provider_string("openai_compat:my-model")
    assert (bare.model, bare.base_url) == ("my-model", None)


@pytest.mark.parametrize(
    "bad",
    [
        "",
        "  ",
        "ollama",
        "ollama:",
        "nope:x",
        "fake:x",
        "anthropic",
        "openai_compat:ftp://x#m",
        "openai_compat:http://x#",
    ],
)
def test_llm_provider_string_invalid_raises(bad: str) -> None:
    with pytest.raises(ProviderStringError) as info:
        parse_provider_string(bad)
    assert info.value.hint


def test_llm_get_llm_builds_each_kind() -> None:
    base = Settings(openai_compat_url="http://x/v1")
    assert isinstance(get_llm(base.model_copy(update={"llm": "ollama:qwen3:14b"})), OllamaProvider)
    assert isinstance(get_llm(base.model_copy(update={"llm": "anthropic:m"})), AnthropicProvider)
    assert isinstance(get_llm(base.model_copy(update={"llm": "openai_compat:m"})), OpenAICompatProvider)
    assert isinstance(get_llm(base.model_copy(update={"llm": "fake"})), FakeLLMProvider)


def test_llm_get_embeddings_builds_each_kind_and_rejects_anthropic() -> None:
    base = Settings(openai_compat_url="http://x/v1")
    assert isinstance(get_embeddings(base), OllamaEmbeddings)
    assert isinstance(get_embeddings(base.model_copy(update={"embeddings": "fake"})), FakeEmbeddings)
    assert isinstance(
        get_embeddings(base.model_copy(update={"embeddings": "openai_compat:http://y/v1#e"})),
        OpenAICompatEmbeddings,
    )
    with pytest.raises(ProviderStringError):
        get_embeddings(base.model_copy(update={"embeddings": "anthropic:m"}))


def test_llm_openai_compat_url_comes_from_settings_or_errors() -> None:
    provider = get_llm(Settings(llm="openai_compat:m", openai_compat_url="http://cfg/v1"))
    assert isinstance(provider, OpenAICompatProvider) and provider.base_url == "http://cfg/v1"
    with pytest.raises(ProviderStringError) as info:
        get_llm(Settings(llm="openai_compat:m"))
    assert "COMIC_SMITH_OPENAI_COMPAT_URL" in info.value.message


def test_llm_doctor_checks_registered_and_fake_is_not_required() -> None:
    assert {"llm", "embeddings"} <= {c.name for c in default_checks()}
    fake = Settings(llm="fake", embeddings="fake")
    for check in (llm_check, embeddings_check):
        r = check(fake)
        assert r.ok and not r.required


@respx.mock
def test_llm_doctor_check_ollama_ok_missing_and_down() -> None:
    settings = Settings(
        llm="ollama:qwen3:14b", embeddings="ollama:nomic-embed-text", ollama_host="http://o.test"
    )
    respx.get("http://o.test/api/tags").mock(
        return_value=httpx.Response(200, json={"models": [{"name": "qwen3:14b"}]})
    )
    assert llm_check(settings).ok and llm_check(settings).required
    missing = embeddings_check(settings)
    assert not missing.ok and missing.required and "ollama pull nomic-embed-text" in (missing.hint or "")


def test_llm_doctor_check_invalid_provider_string_is_reported_not_raised() -> None:
    r = llm_check(Settings(llm="bogus:x"))
    assert not r.ok and r.required and r.hint
