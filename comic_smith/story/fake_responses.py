"""Deterministic fake LLM answers for the story prompts (offline flow with COMIC_SMITH_LLM=fake).

Each responder reads the same `CONTEXT:` line and fenced text a real model would, and builds a
valid reply from it, so the whole bible, suggest, beat, and arc flow works without a model.
`register_all()` runs at import and can be called again after `clear_fake_responders()`.
"""

import re
from typing import Any

from comic_smith.backends.llm.fake import has_fake_responder, register_fake_responder
from comic_smith.story import fake_responses_writer
from comic_smith.story._wire import parse_context, parse_untrusted

BLOCK_MARKER = "[[blocked]]"
KIDS_BLOCKED_WORDS = re.compile(r"\b(kill|kills|killed|stab|stabs|blood|bloody|gun|guns|murder|gore)\b", re.I)
STOP_WORDS = {"a", "an", "the", "when", "after", "one", "it", "his", "her", "they", "this", "that", "in"}
TONES = {"kids-5-8": ["gentle", "funny", "brave"], "kids-9-12": ["funny", "brave"]}
Reply = dict[str, Any]


def _clip(text: str, size: int) -> str:
    text = " ".join(text.split())
    return text if len(text) <= size else text[: size - 1].rstrip() + "."


def _hero_name(narrative: str) -> str:
    for word in re.findall(r"[A-Za-z][A-Za-z'-]*", narrative):
        if word[0].isupper() and word.lower() not in STOP_WORDS:
            return str(word)
    return "Hero"


def bible_reply(system: str, user: str, schema: dict[str, Any], index: int) -> Reply:
    facts = parse_context(user)
    narrative = parse_untrusted(user, "seed narrative")
    hero = _hero_name(narrative)
    first = re.split(r"(?<=[.!?])\s", narrative.strip())[0]
    friend = "Pip" if hero != "Pip" else "Sunny"
    return {
        "working_title": _clip(f"The Story of {hero}", 120),
        "logline": _clip(first, 300),
        "premise": _clip(narrative, 2000),
        "tone": TONES.get(str(facts.get("audience")), ["warm", "curious"]),
        "setting": {"world": "the world of the story idea", "rules": []},
        "cast": [
            {"name": hero, "role": "protagonist", "want": "to solve the problem", "need": "to trust friends"},
            {"name": friend, "role": "friend", "want": "to help", "need": "to be heard"},
        ],
        "themes": ["friendship", "courage"],
    }


def arc_update_reply(system: str, user: str, schema: dict[str, Any], index: int) -> Reply:
    facts = parse_context(user)
    stages: list[str] = facts.get("stages") or []
    count, target = int(facts.get("strips_approved", 1)), max(int(facts.get("target_strips", 1)), 1)
    if stages:
        position = len(stages) - 1 if count >= target else ((count - 1) * len(stages)) // target
        stage = stages[max(0, min(position, len(stages) - 1))]
    else:
        stage = "standalone"
    beat_text = parse_untrusted(user, "approved strip")
    opened = (
        [_clip("Open question: " + beat_text.split(".")[0], 200)]
        if facts.get("strip_intent") == "twist"
        else []
    )
    open_ids = [t["id"] for t in facts.get("open_threads", [])]
    closing = facts.get("strip_intent") == "steer" or (stages and stage == stages[-1])
    return {"threads_opened": opened, "threads_closed": open_ids[:1] if closing else [], "stage": stage}


def _option(intent: str, beat: str, description: str, stage: str, chars: list[str], sketch: str) -> Reply:
    return {
        "intent": intent,
        "beat": _clip(beat, 100),
        "description": _clip(description, 300),
        "arc_stage": stage,
        "characters": chars,
        "thumbnail_prompt": _clip(sketch, 400),
    }


def suggest_reply(system: str, user: str, schema: dict[str, Any], index: int) -> Reply:
    facts = parse_context(user)
    bible = facts["bible"]
    cast = [c["character_id"] for c in bible["cast"]]
    stages: list[str] = bible["arc"]["stages"]
    now = facts.get("arc_stage") or (stages[0] if stages else "standalone")
    nxt = facts.get("next_stage") or now
    after = stages[min(stages.index(nxt) + 1, len(stages) - 1)] if nxt in stages else nxt
    title = bible["working_title"]
    n = int(facts.get("strips_approved", 0)) + 1
    options = [
        _option(
            "continue",
            f"Strip {n}: the friends take the obvious next step",
            f"Everyone follows the plan and makes steady progress in {title}. A small success builds hope.",
            nxt,
            cast[:1],
            "calm wide scene, hero walking forward, warm light",
        ),
        _option(
            "twist",
            f"Strip {n}: a surprise tangles everything",
            "A sudden mishap upsets the plan and nobody expected it. The hero scrambles to react.",
            now,
            cast[:2],
            "close-up of a startled face, tilted camera, scattered objects",
        ),
        _option(
            "steer",
            f"Strip {n}: an unexpected helper points the way home",
            "A newcomer offers wisdom and a shortcut toward the goal. The hero chooses to trust it.",
            after,
            cast[-1:],
            "medium shot of two characters sharing a map under a tree",
        ),
    ]
    end = None
    if facts.get("include_end_here"):
        end = _option(
            "end",
            "Everyone celebrates a happy ending",
            "The problem is solved and the friends gather together. The story closes warmly.",
            stages[-1] if stages else "standalone",
            cast[:2],
            "group hug at sunset, wide shot",
        )
    if facts.get("retry_hint"):
        options[1]["beat"] = _clip(options[1]["beat"] + " with thunder", 100)
    return {"options": options, "end_here": end}


def beat_normalize_reply(system: str, user: str, schema: dict[str, Any], index: int) -> Reply:
    facts = parse_context(user)
    text = parse_untrusted(user, "author idea")
    stages: list[str] = facts.get("stages") or []
    current = facts.get("arc_stage")
    stage = (
        stages[min(stages.index(current) + 1, len(stages) - 1)]
        if current in stages
        else (stages[0] if stages else "standalone")
    )
    lowered = text.lower()
    chars = [c for c in facts.get("cast", []) if c.removeprefix("ch_").replace("_", " ") in lowered]
    sentences = re.split(r"(?<=[.!?])\s+", text)
    return {
        "beat": _clip(sentences[0], 100),
        "description": _clip(" ".join(sentences[:2]), 300),
        "arc_stage": stage,
        "characters": chars or facts.get("cast", [])[:1],
        "panels": 4,
    }


def moderation_reply(system: str, user: str, schema: dict[str, Any], index: int) -> Reply:
    facts = parse_context(user)
    texts = " ".join(parse_untrusted(user, f"text {i}") for i in range(1, int(facts.get("count", 1)) + 1))
    kids = str(facts.get("audience", "")).startswith("kids")
    if BLOCK_MARKER in texts:
        return {
            "allowed": False,
            "category": "test",
            "reason": "Marked as blocked for a test.",
            "rule": "marker",
        }
    if kids and KIDS_BLOCKED_WORDS.search(texts):
        return {
            "allowed": False,
            "category": "violence",
            "reason": "Too violent for children.",
            "rule": "kids-violence",
        }
    return {"allowed": True, "category": None, "reason": None, "rule": None}


RESPONDERS = {
    "bible": bible_reply,
    "arc_update": arc_update_reply,
    "suggest": suggest_reply,
    "beat_normalize": beat_normalize_reply,
    "moderation": moderation_reply,
}


def register_all() -> None:
    """Register every story responder with the fake LLM provider."""
    for name, fn in RESPONDERS.items():
        register_fake_responder(name, fn)


def ensure_registered() -> None:
    """Register any story responder that is missing; never replaces one a test installed.

    Why: after `clear_fake_responders()` the fake provider could not answer, and production use
    (`get_llm` for `fake`) must not depend on which module happened to be imported first.
    """
    for name, fn in {**RESPONDERS, **fake_responses_writer.RESPONDERS}.items():
        if not has_fake_responder(name):
            register_fake_responder(name, fn)


register_all()
