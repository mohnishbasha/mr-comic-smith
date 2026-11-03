"""Bible, suggestions, and strip writer against a real local Ollama; skipped when it is not available.

These run every story call through the fail-closed moderation classifier, which needs a capable model:
qwen3:0.6b blocks harmless text, so the default is qwen3:14b (override with COMIC_SMITH_IT_STORY_MODEL).
"""

import os
import time

import httpx
import pytest

from comic_smith.backends.llm.ollama import OllamaEmbeddings, OllamaProvider
from comic_smith.config import Settings
from comic_smith.models import Bible, PanelSpec
from comic_smith.story.bible import generate_bible
from comic_smith.story.suggest import suggest_next
from comic_smith.story.writer import write_strip
from tests.unit.story_core_support import NARRATIVE, make_bible, story_ctx
from tests.unit.story_support import make_beat

# A cold load of a 14B model plus several calls can take minutes on a laptop.
pytestmark = [pytest.mark.integration, pytest.mark.timeout(900)]
MODEL = os.environ.get("COMIC_SMITH_IT_STORY_MODEL", "qwen3:14b")
EMBED = os.environ.get("COMIC_SMITH_IT_OLLAMA_EMBED_MODEL", "nomic-embed-text")


def providers(model: str) -> tuple[OllamaProvider, OllamaEmbeddings]:
    host = Settings().ollama_host
    try:
        httpx.get(f"{host}/api/tags", timeout=2).raise_for_status()
    except httpx.HTTPError:
        pytest.skip(f"Ollama is not reachable at {host}")
    llm, emb = OllamaProvider(model, host, timeout=300), OllamaEmbeddings(EMBED, host)
    if llm.preflight() or emb.preflight():
        pytest.skip(f"{model} or {EMBED} is not installed")
    return llm, emb


def it_story_bible_ollama_generates_valid_bible() -> None:
    llm, emb = providers(MODEL)
    with story_ctx(llm, emb) as ctx:
        bible = generate_bible(ctx, narrative=NARRATIVE, audience="kids-5-8", target_strips=6)
    assert Bible.model_validate(bible.model_dump(mode="json")).arc.target_strips == 6


def it_story_suggest_ollama_distinct_options() -> None:
    llm, emb = providers(MODEL)
    with story_ctx(llm, emb) as ctx:
        make_bible(ctx)
        result = suggest_next(ctx)
    assert len(result.options) == 3


def it_story_suggest_local_model_within_10s() -> None:
    llm, emb = providers(os.environ.get("COMIC_SMITH_IT_SUGGEST_MODEL", MODEL))
    with story_ctx(llm, emb) as ctx:
        make_bible(ctx)
        start = time.perf_counter()
        suggest_next(ctx)
    assert time.perf_counter() - start < 10


def it_story_writer_ollama_valid_panel_specs() -> None:
    llm, emb = providers(MODEL)
    with story_ctx(llm, emb) as ctx:
        make_bible(ctx)
        script = write_strip(ctx, make_beat(), temperature=0.0)
    assert len(script.panels) == 4
    for spec in script.panels:
        PanelSpec.model_validate(spec.model_dump(mode="json"))
