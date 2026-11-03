"""Shared builders for the writer, strips, branches, and finalize tests (no network, no GPU)."""

import itertools
import json
import re
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any

import pytest

from comic_smith.config import Settings
from comic_smith.context import Ctx, open_ctx
from comic_smith.models import ArcDiff, Beat, Bible
from comic_smith.projects import create_project
from comic_smith.story import arc, moderation
from comic_smith.story import bible as bible_service

_COUNTER = itertools.count(1)
CAST = ["ch_duck", "ch_frog"]
SHOT_CYCLE = ["wide", "medium", "close-up", "medium", "wide", "close-up"]
DATA_RE = re.compile(r"<<<BEGIN STORY_DATA>>>\n(.*?)\n<<<END STORY_DATA>>>", re.DOTALL)


def make_bible(audience: str = "all-ages") -> Bible:
    return Bible.model_validate(
        {
            "working_title": "Puddle the Duck",
            "logline": "A duck finds a lost kite.",
            "premise": "A duck and a frog return a kite to its owner.",
            "audience": audience,
            "tone": ["warm"],
            "setting": {"world": "A rainy pond town", "rules": []},
            "cast": [
                {"character_id": "ch_duck", "role": "hero"},
                {"character_id": "ch_frog", "role": "friend"},
            ],
            "arc": {"template": "three-act", "target_strips": 8},
            "style_id": "st_picture_book_watercolor",
        }
    )


def make_beat(text: str = "The duck finds a kite", stage: str = "setup") -> Beat:
    return Beat.model_validate(
        {
            "source": "suggestion",
            "intent": "continue",
            "beat": text,
            "description": "Puddle spots a red kite stuck in the reeds.",
            "arc_stage": stage,
            "characters": ["ch_duck"],
            "panels": 4,
        }
    )


def panel(
    idx: int, shot: str = "medium", dialogue: list[tuple[str, str]] | None = None, **over: Any
) -> dict[str, Any]:
    lines = dialogue if dialogue is not None else [("ch_duck", "Hello there")]
    spec: dict[str, Any] = {
        "idx": idx,
        "shot": shot,
        "angle": "eye-level",
        "setting": "The pond",
        "characters": [
            {
                "id": "ch_duck",
                "position": "left",
                "pose": "standing",
                "expression": "happy",
                "facing": "right",
            }
        ],
        "action": "Puddle looks around",
        "dialogue": [{"speaker": s, "type": "speech", "text": t} for s, t in lines],
        "caption": None,
        "sfx": [],
        "continuity": [f"red kite in panel {idx}"],
        "mood": "warm",
        "balloon_space": "top" if lines else "none",
    }
    spec.update(over)
    return spec


def script(count: int = 4, shots: list[str] | None = None, **over: Any) -> dict[str, Any]:
    order = shots or SHOT_CYCLE
    return {"panels": [panel(i, order[(i - 1) % len(order)], **over) for i in range(1, count + 1)]}


@dataclass
class ScriptedLLM:
    """LLM stand-in returning queued replies (the last repeats); records every call."""

    replies: list[Any] = field(default_factory=list)
    calls: list[dict[str, Any]] = field(default_factory=list)
    id: str = "scripted"

    def preflight(self) -> list[Any]:
        return []

    def complete_json(
        self, system: str, user: str, schema: dict[str, Any], *, temperature: float, seed: int | None
    ) -> dict[str, Any]:
        self.calls.append({"system": system, "user": user, "temperature": temperature})
        reply = self.replies[min(len(self.calls), len(self.replies)) - 1]
        out = reply(user) if callable(reply) else reply
        assert isinstance(out, dict)
        return out


def data_of(user: str) -> dict[str, Any]:
    match = DATA_RE.search(user)
    assert match is not None
    parsed: dict[str, Any] = json.loads(match.group(1))
    return parsed


def echo_script(user: str) -> dict[str, Any]:
    """A valid script with as many panels as the context asks for."""
    return script(int(data_of(user)["panels"]))


@dataclass
class Env:
    settings: Settings
    ctx: Ctx
    llm: ScriptedLLM
    checks: list[tuple[str, list[str], str]]
    approvals: list[str]


@contextmanager
def story_env(
    monkeypatch: pytest.MonkeyPatch, *, audience: str = "all-ages", name: str = "Story Demo"
) -> Iterator[Env]:
    """An open project, a patched bible/moderation/arc, and a scripted LLM."""
    settings = Settings()
    info = create_project(settings, f"{name} {next(_COUNTER)}", audience=audience)
    bible = make_bible(audience)
    checks: list[tuple[str, list[str], str]] = []
    approvals: list[str] = []
    monkeypatch.setattr(bible_service, "current_bible", lambda session, project_id: bible)
    monkeypatch.setattr(moderation, "audience_rules", lambda aud: f"Audience: {aud}. Keep it gentle.")

    def check(ctx: Ctx, kind: str, texts: list[str], aud: str) -> None:
        checks.append((kind, texts, aud))

    def approve(ctx: Ctx, session: Any, strip: Any) -> ArcDiff:
        approvals.append(strip.id)
        return ArcDiff(stage="setup")

    monkeypatch.setattr(moderation, "check_texts", check)
    monkeypatch.setattr(arc, "apply_strip_approval", approve)
    llm = ScriptedLLM(replies=[echo_script])
    with open_ctx(settings, info.slug, llm=llm) as ctx:  # type: ignore[arg-type]
        yield Env(settings, ctx, llm, checks, approvals)


Reply = Callable[[str], dict[str, Any]]
