"""Fake providers: fixtures, responders, recording, embeddings (S1-T01)."""

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from comic_smith.backends.llm.fake import (
    FakeEmbeddings,
    FakeLLMProvider,
    RecordingLLMProvider,
    clear_fake_responders,
    prompt_hash,
    register_fake_responder,
    resolve_fixtures_dir,
    template_of,
)
from comic_smith.errors import LLMOutputInvalidError

SCHEMA: dict[str, Any] = {"type": "object", "properties": {"a": {"type": "string"}}, "required": ["a"]}
MARK = "<!-- template: demo@3 -->\nYou are a demo."


@pytest.fixture(autouse=True)
def _clean_registry() -> Iterator[None]:
    clear_fake_responders()
    yield
    clear_fake_responders()


def cosine(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b, strict=True))


def test_llm_fake_provider_replays_by_prompt_hash(tmp_path: Path) -> None:
    (tmp_path / f"{prompt_hash('s', 'u', SCHEMA)}.json").write_text('{"a": "recorded"}')
    p = FakeLLMProvider(tmp_path)
    assert p.complete_json("s", "u", SCHEMA, temperature=0, seed=None) == {"a": "recorded"}
    assert p.id == "fake" and p.preflight() == []


def test_llm_prompt_hash_is_canonical_and_input_sensitive() -> None:
    assert prompt_hash("s", "u", {"b": 1, "a": 2}) == prompt_hash("s", "u", {"a": 2, "b": 1})
    assert len(prompt_hash("s", "u", SCHEMA)) == 64
    assert prompt_hash("s", "u", SCHEMA) != prompt_hash("s", "u2", SCHEMA)


def test_llm_fake_provider_unknown_hash_names_record_command(tmp_path: Path) -> None:
    with pytest.raises(LLMOutputInvalidError) as info:
        FakeLLMProvider(tmp_path).complete_json("s", "u", SCHEMA, temperature=0, seed=None)
    assert "make record-fixtures" in (info.value.hint or "")
    assert "scripts/record-fixtures.py" in (info.value.hint or "")
    assert prompt_hash("s", "u", SCHEMA) in (info.value.detail or "")


def test_llm_fake_responder_selected_by_template_marker_and_call_index() -> None:
    seen: list[int] = []

    def responder(system: str, user: str, schema: dict[str, Any], index: int) -> dict[str, Any]:
        seen.append(index)
        return {"a": f"{user}-{index}"}

    register_fake_responder("demo", responder)
    p = FakeLLMProvider()
    assert p.complete_json(MARK, "x", SCHEMA, temperature=0, seed=None) == {"a": "x-0"}
    assert p.complete_json(MARK, "x", SCHEMA, temperature=0, seed=None) == {"a": "x-1"}
    assert seen == [0, 1]


def test_llm_fake_responder_exact_version_wins_over_name() -> None:
    register_fake_responder("demo", lambda s, u, sc, i: {"a": "name"})
    register_fake_responder("demo@3", lambda s, u, sc, i: {"a": "versioned"})
    assert FakeLLMProvider().complete_json(MARK, "x", SCHEMA, temperature=0, seed=None) == {"a": "versioned"}


def test_llm_fake_responder_invalid_first_reply_gets_corrective_retry() -> None:
    users: list[str] = []

    def responder(system: str, user: str, schema: dict[str, Any], index: int) -> dict[str, Any]:
        users.append(user)
        return {"wrong": 1} if index == 0 else {"a": "fixed"}

    register_fake_responder("demo", responder)
    assert FakeLLMProvider().complete_json(MARK, "x", SCHEMA, temperature=0, seed=None) == {"a": "fixed"}
    assert "did not match the schema" in users[1]


def test_llm_fake_no_responder_for_marker_or_without_marker_raises(tmp_path: Path) -> None:
    p = FakeLLMProvider(tmp_path)
    for system in (MARK, "no marker here", "<!-- template: broken -->"):
        with pytest.raises(LLMOutputInvalidError):
            p.complete_json(system, "x", SCHEMA, temperature=0, seed=None)


def test_llm_fake_corrupt_fixture_is_an_invalid_reply(tmp_path: Path) -> None:
    (tmp_path / f"{prompt_hash('s', 'u', SCHEMA)}.json").write_text("{nope")
    with pytest.raises(LLMOutputInvalidError):
        FakeLLMProvider(tmp_path).complete_json("s", "u", SCHEMA, temperature=0, seed=None)


def test_llm_template_of_parses_marker() -> None:
    assert template_of(MARK) == ("demo", "3")
    assert template_of("plain") is None


def test_llm_fixtures_dir_resolution_order(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COMIC_SMITH_FAKE_LLM_FIXTURES", str(tmp_path / "env"))
    assert resolve_fixtures_dir(tmp_path / "arg") == tmp_path / "arg"
    assert resolve_fixtures_dir(None) == tmp_path / "env"
    monkeypatch.delenv("COMIC_SMITH_FAKE_LLM_FIXTURES")
    default = resolve_fixtures_dir(None)
    assert default is None or default.name == "llm"


def test_llm_recording_wrapper_writes_replayable_fixture(tmp_path: Path) -> None:
    register_fake_responder("demo", lambda s, u, sc, i: {"a": "live"})
    rec = RecordingLLMProvider(FakeLLMProvider(), tmp_path / "fx")
    assert rec.complete_json(MARK, "x", SCHEMA, temperature=0, seed=None) == {"a": "live"}
    files = list((tmp_path / "fx").glob("*.json"))
    assert [f.stem for f in files] == [prompt_hash(MARK, "x", SCHEMA)]
    assert json.loads(files[0].read_text()) == {"a": "live"}
    clear_fake_responders()
    replay = FakeLLMProvider(tmp_path / "fx")
    assert replay.complete_json(MARK, "x", SCHEMA, temperature=0, seed=None) == {"a": "live"}
    assert rec.id == "fake" and rec.preflight() == []


def test_llm_fake_embeddings_are_deterministic_unit_vectors() -> None:
    e = FakeEmbeddings()
    v1 = e.embed(["The brave fox runs"])[0]
    assert v1 == FakeEmbeddings().embed(["The brave fox runs"])[0]
    assert len(v1) == 256 == e.dimensions
    assert cosine(v1, v1) == pytest.approx(1.0)
    assert e.embed([""]) == [[0.0] * 256]
    assert e.preflight() == [] and e.id == "fake"


def test_llm_fake_embeddings_shared_words_score_higher() -> None:
    e = FakeEmbeddings()
    a, b, c = e.embed(
        ["a fox chases the red kite", "the red kite and a fox", "quarterly tax filing deadline"]
    )
    assert cosine(a, b) > 0.6
    assert cosine(a, b) > cosine(a, c) + 0.5
