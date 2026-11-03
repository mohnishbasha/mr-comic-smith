"""Offline responders for the strip writer, continuity, and titles templates.

They read the JSON data block the services put in the user message and answer from it, so
`COMIC_SMITH_LLM=fake` runs the whole script-and-finalize flow with valid output: only cast ids from
the context, varied shots, and dialogue inside the audience limits. A beat or story text containing
`[fake:continuity-issue]` makes the continuity responder report one issue (for tests and demos).
"""

import json
import re
from typing import Any

from comic_smith.backends.llm.fake import register_fake_responder

DATA_RE = re.compile(r"<<<BEGIN STORY_DATA>>>\n(.*?)\n<<<END STORY_DATA>>>", re.DOTALL)
ISSUE_MARKER = "[fake:continuity-issue]"
SHOTS = ("wide", "medium", "close-up", "medium", "wide", "extreme-close-up")
ANGLES = ("eye-level", "high", "eye-level", "low", "eye-level", "birds-eye")
POSITIONS = ("left", "right", "center")
LINES = (
    "Here we go!",
    "I see something.",
    "Wait for me!",
    "That was close.",
    "Look over there.",
    "We did it!",
)
FAKE_MAX_BALLOON_WORDS = 6


def _data(user: str) -> dict[str, Any]:
    match = DATA_RE.search(user)
    parsed = json.loads(match.group(1)) if match else {}
    return parsed if isinstance(parsed, dict) else {}


def _cut(text: str, size: int) -> str:
    return (text.strip() or "x")[:size]


def _panel(idx: int, data: dict[str, Any], budget: int) -> dict[str, Any]:
    cast = [c["id"] for c in data["cast"]]
    wanted = [c for c in data["beat"].get("characters", []) if c in cast] or cast
    first = wanted[(idx - 1) % len(wanted)]
    words = LINES[(idx - 1) % len(LINES)].split()[:budget]
    return {
        "idx": idx,
        "shot": SHOTS[(idx - 1) % len(SHOTS)],
        "angle": ANGLES[(idx - 1) % len(ANGLES)],
        "setting": _cut(data["story"]["world"], 300),
        "characters": [
            {
                "id": first,
                "position": POSITIONS[idx % len(POSITIONS)],
                "pose": "standing",
                "expression": "happy",
                "facing": "camera",
            }
        ],
        "action": _cut(data["beat"].get("description", data["beat"].get("beat", "")), 300),
        "dialogue": [{"speaker": first, "type": "speech", "text": " ".join(words)}] if words else [],
        "caption": None,
        "sfx": [],
        "continuity": [_cut(f"{first} looks the same in every panel", 160)],
        "mood": _cut(str(data["story"]["tone"][0]), 60),
        "balloon_space": "top" if words else "none",
    }


def strip_writer(system: str, user: str, schema: dict[str, Any], index: int) -> dict[str, Any]:
    """Write `panels` valid Panel Specs from the context block."""
    data = _data(user)
    count = int(data["panels"])
    limits = data["limits"]
    budget = max(
        0, min(FAKE_MAX_BALLOON_WORDS, limits["words_per_balloon"], limits["words_per_strip"] // count)
    )
    return {"panels": [_panel(i, data, budget) for i in range(1, count + 1)]}


def continuity(system: str, user: str, schema: dict[str, Any], index: int) -> dict[str, Any]:
    """No issues, unless the data carries the test marker."""
    if ISSUE_MARKER not in user:
        return {"issues": []}
    issue = {
        "id": "i1",
        "kind": "tone_break",
        "severity": "warn",
        "strip": 1,
        "text": "The tone of this strip does not match the rest of the story.",
    }
    return {"issues": [issue]}


def titles(system: str, user: str, schema: dict[str, Any], index: int) -> dict[str, Any]:
    """Three titles and a blurb derived from the story title and premise."""
    story = _data(user).get("story", {})
    name = _cut(str(story.get("title", "Our Story")), 50)
    premise = _cut(str(story.get("premise", name)), 160)
    return {"titles": [name, f"{name}: The Adventure", f"The Tale of {name}"], "blurb": premise}


RESPONDERS = {"strip_writer": strip_writer, "continuity": continuity, "titles": titles}


def register() -> None:
    """Register the three responders (safe to call again after `clear_fake_responders`)."""
    for name, fn in RESPONDERS.items():
        register_fake_responder(name, fn)


register()
