"""Helpers for the bible, arc, suggest, beat, and moderation tests (fake providers, no network)."""

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from itertools import count
from typing import Any

from comic_smith.backends.llm.fake import FakeEmbeddings, FakeLLMProvider
from comic_smith.config import Settings
from comic_smith.context import Ctx, open_ctx
from comic_smith.db.base import utc_now_iso
from comic_smith.db.models import Branch, Strip
from comic_smith.ids import PREFIXES, new_id
from comic_smith.projects import create_project
from comic_smith.story import fake_responses
from comic_smith.story.bible import generate_bible, save_bible

_COUNTER = count(1)
NARRATIVE = "Puddle is a little rubber duck who is afraid of water. A friend drifts toward the drain."


@contextmanager
def story_ctx(
    llm: Any = None, embeddings: Any = None, *, name: str | None = None, audience: str = "kids-5-8"
) -> Iterator[Ctx]:
    """An open project with fake providers; the responders are re-registered first."""
    name = name or f"Puddle Story {next(_COUNTER)}"
    fake_responses.register_all()
    settings = Settings()
    create_project(settings, name, narrative=NARRATIVE, audience=audience)
    with open_ctx(
        settings, name, llm=llm or FakeLLMProvider(), embeddings=embeddings or FakeEmbeddings()
    ) as ctx:
        yield ctx


def make_bible(ctx: Ctx, *, audience: str = "kids-5-8", target: int = 8, arc: str | None = None) -> int:
    """Generate and save a bible; return its version."""
    bible = generate_bible(ctx, narrative=NARRATIVE, audience=audience, target_strips=target, arc=arc)
    with ctx.project.session() as s:
        return save_bible(ctx, s, bible, actor="user")


def main_branch_id(ctx: Ctx) -> str:
    with ctx.project.session(readonly=True) as s:
        return s.query(Branch).filter_by(project_id=ctx.project_id, name="main").one().id


def add_strip(
    ctx: Ctx,
    idx: int,
    *,
    stage: str = "setup",
    status: str = "approved",
    branch_id: str | None = None,
    intent: str = "continue",
    beat: str | None = None,
) -> Strip:
    """Insert a strip row directly (tests only; services use events)."""
    bid = branch_id or main_branch_id(ctx)
    with ctx.project.session() as s:
        strip = Strip(
            id=new_id(PREFIXES["strip"]),
            project_id=ctx.project_id,
            branch_id=bid,
            idx=idx,
            beat_json={
                "beat": beat or f"Beat number {idx}",
                "description": f"Description {idx}.",
                "intent": intent,
            },
            arc_stage=stage,
            status=status,
            created_at=utc_now_iso(),
            approved_at=utc_now_iso() if status == "approved" else None,
        )
        s.add(strip)
    return strip


class ScriptedLLM:
    """Returns queued replies per template name; records every call."""

    id = "scripted"

    def __init__(self, replies: dict[str, list[dict[str, Any]]], fallback: bool = True) -> None:
        self.replies = {k: list(v) for k, v in replies.items()}
        self.calls: list[tuple[str, str, float]] = []
        self.fallback = FakeLLMProvider() if fallback else None

    def preflight(self) -> list[Any]:
        return []

    def complete_json(
        self, system: str, user: str, schema: dict[str, Any], *, temperature: float, seed: int | None
    ) -> dict[str, Any]:
        name = system.split("\n", 1)[0].split("template: ")[1].split("@", maxsplit=1)[0]
        self.calls.append((system, user, temperature))
        queue = self.replies.get(name)
        if queue:
            return queue.pop(0) if len(queue) > 1 else queue[0]
        assert self.fallback is not None, f"no scripted reply for {name}"
        return self.fallback.complete_json(system, user, schema, temperature=temperature, seed=seed)

    def systems(self) -> list[str]:
        return [c[0] for c in self.calls]

    def for_template(self, name: str) -> list[tuple[str, str, float]]:
        return [c for c in self.calls if f"template: {name}@" in c[0]]


def option(
    intent: str, beat: str, desc: str, stage: str = "setup", chars: list[str] | None = None
) -> dict[str, Any]:
    return {
        "intent": intent,
        "beat": beat,
        "description": desc,
        "arc_stage": stage,
        "characters": chars or ["ch_puddle"],
        "thumbnail_prompt": "a quiet scene",
    }


class VectorEmbeddings:
    """Embeddings that return queued vectors per call (for threshold tests)."""

    id = "vec"
    dimensions: int | None = 2

    def __init__(self, calls: list[list[list[float]]]) -> None:
        self.calls = calls
        self.n = 0

    def preflight(self) -> list[Any]:
        return []

    def embed(self, texts: list[str]) -> list[list[float]]:
        out = self.calls[min(self.n, len(self.calls) - 1)]
        self.n += 1
        return out


Responder = Callable[..., dict[str, Any]]
