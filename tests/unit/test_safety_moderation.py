"""Audience guard, denylist, and LLM moderation (S1-T08)."""

import logging
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
import yaml

from comic_smith.context import Ctx
from comic_smith.errors import (
    AudienceBlockedError,
    ComicSmithError,
    ConfigError,
    OriginalityBlockedError,
    SafetyError,
    UsageError,
)
from comic_smith.models import Audience, ModerationVerdict, llm_schema
from comic_smith.story.arc import apply_strip_approval
from comic_smith.story.audience import audience_rules
from comic_smith.story.beats import normalize_beat
from comic_smith.story.bible import edit_bible, generate_bible
from comic_smith.story.moderation import DENYLIST_FILE, check_texts, find_denied, load_denylist
from comic_smith.story.suggest import suggest_next
from tests.unit.story_core_support import NARRATIVE, ScriptedLLM, add_strip, make_bible, story_ctx


@pytest.fixture
def ctx() -> Iterator[Ctx]:
    with story_ctx() as c:
        yield c


def test_safety_moderation_blocked_bible_raises_safety_blocked(ctx: Ctx) -> None:
    with pytest.raises(AudienceBlockedError) as info:
        generate_bible(ctx, narrative=NARRATIVE + " [[blocked]]", audience="kids-5-8", target_strips=4)
    assert isinstance(info.value, SafetyError)
    assert info.value.code == "audience_blocked" and info.value.exit_code == 4
    make_bible(ctx)
    with pytest.raises(AudienceBlockedError):
        edit_bible(ctx, {"logline": "A [[blocked]] logline."})


def test_safety_moderation_verdict_strict_json_schema() -> None:
    schema = llm_schema(ModerationVerdict)
    assert schema["additionalProperties"] is False and "allowed" in schema["required"]
    with pytest.raises(ValueError):
        ModerationVerdict.model_validate({"allowed": True, "extra": 1})
    assert ModerationVerdict.model_validate({"allowed": True}).allowed


def test_safety_moderation_runs_on_suggestions_beats_scripts() -> None:
    llm = ScriptedLLM({})
    with story_ctx(llm) as c:
        make_bible(c)
        before = len(llm.for_template("moderation"))
        suggest_next(c)
        after_suggest = len(llm.for_template("moderation"))
        normalize_beat(c, "Pip hides.")
        after_beat = len(llm.for_template("moderation"))
        check_texts(c, "script", ["Panel one text."], "kids-5-8")
        after_script = len(llm.for_template("moderation"))
    assert (before, after_suggest, after_beat, after_script) == (1, 2, 3, 4)
    kinds = [u for _, u, _ in llm.for_template("moderation")]
    assert '"kind":"bible"' in kinds[0] and '"kind":"suggestion"' in kinds[1]
    assert '"kind":"beat"' in kinds[2] and '"kind":"script"' in kinds[3]


def test_safety_audience_rules_in_every_system_prompt() -> None:
    llm = ScriptedLLM({})
    with story_ctx(llm) as c:
        make_bible(c)
        strip = add_strip(c, 1, intent="twist")
        suggest_next(c)
        normalize_beat(c, "Pip hides.")
        with c.project.session() as s:
            apply_strip_approval(c, s, strip)
    seen = {s.split("\n", 1)[0] for s in llm.systems()}
    assert len(seen) >= 5  # bible, moderation, suggest, beat_normalize, arc_update
    rules = audience_rules("kids-5-8")
    assert "10 words per balloon" in rules
    for system in llm.systems():
        assert "## Audience rules" in system and rules in system


def test_safety_audience_rules_defined_for_all_five_audiences() -> None:
    texts = {a: audience_rules(a.value) for a in Audience}
    assert len(set(texts.values())) == 5
    assert "2 balloons per panel" in texts[Audience.KIDS_5_8]
    with pytest.raises(UsageError):
        audience_rules("toddler")


def test_safety_denylist_copyrighted_name_blocked_in_beat(ctx: Ctx) -> None:
    make_bible(ctx)
    for text in ("Puddle meets MICKEY   mouse", "a day with spider-man", "pokémon!"):
        with pytest.raises(OriginalityBlockedError) as info:
            normalize_beat(ctx, text)
        assert info.value.code == "originality_blocked"
    with pytest.raises(OriginalityBlockedError) as info:
        check_texts(ctx, "beat", ["draw it like Hayao Miyazaki"], "adult")
    assert "living artists" in info.value.message and "artist.living-manga" in info.value.message
    normalize_beat(ctx, "Puddle meets a mousetrap named Marvin.")  # whole words only


def test_safety_blocked_error_explains_in_plain_words(ctx: Ctx, caplog: pytest.LogCaptureFixture) -> None:
    secret = "Puddle meets Batman near the bathtub"
    with caplog.at_level(logging.DEBUG), pytest.raises(OriginalityBlockedError) as info:
        check_texts(ctx, "beat", [secret], "kids-5-8")
    err = info.value
    assert "someone else's character" in err.message and "character.superheroes" in err.message
    assert "Batman" not in err.message and "bathtub" not in (err.detail or "")
    assert "Batman" not in caplog.text and "bathtub" not in caplog.text
    with pytest.raises(AudienceBlockedError) as kid:
        check_texts(ctx, "beat", ["a [[blocked]] idea"], "kids-5-8")
    assert "ages 5 to 8" in kid.value.message and "gentler twist" in kid.value.message
    with pytest.raises(AudienceBlockedError) as grown:
        check_texts(ctx, "beat", ["a [[blocked]] idea"], "adult")
    assert "unsafe" in grown.value.message
    assert "\u2014" not in kid.value.message + grown.value.message + err.message
    assert isinstance(err, ComicSmithError) and err.hint


def test_safety_denylist_loaded_from_yaml_data_file(tmp_path: Path) -> None:
    data: dict[str, Any] = yaml.safe_load(DENYLIST_FILE.read_text(encoding="utf-8"))
    assert data["version"] == 1 and {r["kind"] for r in data["rules"]} == {"franchise", "character", "artist"}
    assert all(r["id"] and r["patterns"] for r in data["rules"])
    assert load_denylist() is load_denylist()  # cached
    custom = tmp_path / "deny.yaml"
    custom.write_text(
        "version: 1\nrules:\n  - {id: test.rule, kind: character, patterns: [Zorp the Mighty]}\n",
        encoding="utf-8",
    )
    rules = load_denylist(custom)
    assert [r.id for r in rules] == ["test.rule"]
    assert find_denied("I love zorp   THE mighty!", rules) is not None
    assert find_denied("zorps the mighty", rules) is None
    assert find_denied("Mickey Mouse") is not None and find_denied("a duck in a tub") is None
    bad = tmp_path / "bad.yaml"
    for body in ("version: 2\nrules: []\n", "version: 1\nrules:\n  - {id: x, kind: weird, patterns: [a]}\n"):
        bad.write_text(body, encoding="utf-8")
        with pytest.raises(ConfigError):
            load_denylist(bad)


def test_safety_moderation_unparseable_verdict_fails_closed(ctx: Ctx) -> None:
    for reply in ({"nonsense": 1}, {"allowed": "maybe"}, {}):
        ctx.llm = ScriptedLLM({"moderation": [reply]}, fallback=False)
        with pytest.raises(AudienceBlockedError) as info:
            check_texts(ctx, "beat", ["A calm day."], "kids-5-8")
        assert "could not check" in info.value.message


def test_safety_audience_kids_blocks_violent_beat(ctx: Ctx) -> None:
    make_bible(ctx)
    with pytest.raises(AudienceBlockedError):
        normalize_beat(ctx, "Puddle stabs the villain and there is blood everywhere.")
    check_texts(ctx, "beat", ["Puddle bakes a cake."], "kids-5-8")
    llm = ScriptedLLM(
        {"moderation": [{"allowed": False, "category": "violence", "reason": "r", "rule": "x"}]}
    )
    ctx.llm = llm
    with pytest.raises(AudienceBlockedError):
        check_texts(ctx, "beat", ["innocent words"], "kids-5-8")
    assert '"audience":"kids-5-8"' in llm.for_template("moderation")[0][1]


def test_safety_empty_texts_skip_checks_and_unknown_audience_rejected(ctx: Ctx) -> None:
    ctx.llm = ScriptedLLM({}, fallback=False)
    check_texts(ctx, "beat", ["", "   "], "kids-5-8")
    with pytest.raises(UsageError):
        check_texts(ctx, "beat", ["x"], "toddler")
