"""Offline providers for tests and dev: recorded fixtures, registered responders, hash embeddings.

FakeLLMProvider resolves a call in three layers: (a) a fixture file `{prompt_hash}.json`, (b) a
responder registered for the system prompt's template marker, (c) a typed error naming the
command that records fixtures. Replies still pass through schema validation and the corrective
retry, so responders can exercise that path.
"""

import hashlib
import json
import math
import os
import re
from collections.abc import Callable
from pathlib import Path
from typing import Any

from comic_smith.backends.llm._common import JsonProviderBase, OutputParseError, as_dict
from comic_smith.backends.llm.base import TEMPLATE_MARKER_PREFIX, LLMProvider, PreflightIssue
from comic_smith.errors import LLMOutputInvalidError

FIXTURES_ENV = "COMIC_SMITH_FAKE_LLM_FIXTURES"
DEFAULT_FIXTURES_DIR = Path(__file__).resolve().parents[3] / "tests" / "fixtures" / "llm"
EMBEDDING_DIMENSIONS = 256
TOKEN_RE = re.compile(r"[a-z0-9]+")
MARKER_RE = re.compile(r"<!-- template: ([^@\s]+)@(\d+) -->")

Responder = Callable[[str, str, dict[str, Any], int], dict[str, Any]]
_RESPONDERS: dict[str, Responder] = {}


def register_fake_responder(template: str, fn: Responder) -> None:
    """Register `fn` for a template name (`name`) or an exact version (`name@version`)."""
    _RESPONDERS[template] = fn


def unregister_fake_responder(template: str) -> None:
    _RESPONDERS.pop(template, None)


def has_fake_responder(template: str) -> bool:
    return template in _RESPONDERS


def clear_fake_responders() -> None:
    _RESPONDERS.clear()


def prompt_hash(system: str, user: str, schema: dict[str, Any]) -> str:
    """sha256 over canonical JSON of the three inputs; names recorded fixture files."""
    canonical = json.dumps(
        {"system": system, "user": user, "schema": schema},
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def template_of(system: str) -> tuple[str, str] | None:
    """Return (name, version) from the first-line marker, or None."""
    first = system.split("\n", 1)[0]
    if not first.startswith(TEMPLATE_MARKER_PREFIX):
        return None
    match = MARKER_RE.fullmatch(first.strip())
    return (match.group(1), match.group(2)) if match else None


def resolve_fixtures_dir(explicit: Path | None) -> Path | None:
    if explicit is not None:
        return explicit
    env = os.environ.get(FIXTURES_ENV)
    if env:
        return Path(env)
    return DEFAULT_FIXTURES_DIR if DEFAULT_FIXTURES_DIR.is_dir() else None


class FakeLLMProvider(JsonProviderBase):
    id = "fake"

    def __init__(self, fixtures_dir: Path | None = None) -> None:
        super().__init__()
        self.fixtures_dir = resolve_fixtures_dir(fixtures_dir)
        self.call_counts: dict[str, int] = {}

    def preflight(self) -> list[PreflightIssue]:
        return []

    def _generate(
        self, system: str, user: str, schema: dict[str, Any], *, temperature: float, seed: int | None
    ) -> object:
        digest = prompt_hash(system, user, schema)
        if self.fixtures_dir is not None:
            path = self.fixtures_dir / f"{digest}.json"
            if path.is_file():
                try:
                    return json.loads(path.read_text(encoding="utf-8"))
                except json.JSONDecodeError as e:
                    raise OutputParseError(f"fixture {path.name} is not valid JSON") from e
        found = template_of(system)
        if found is not None:
            name, version = found
            responder = _RESPONDERS.get(f"{name}@{version}") or _RESPONDERS.get(name)
            if responder is not None:
                index = self.call_counts.get(name, 0)
                self.call_counts[name] = index + 1
                return responder(system, user, schema, index)
        raise LLMOutputInvalidError(
            "The fake language model has no recorded answer for this prompt.",
            hint="Record one against a real model with `make record-fixtures` (scripts/record-fixtures.py).",
            detail=f"prompt_hash={digest}",
        )


class RecordingLLMProvider:
    """Wraps a real provider and saves each validated reply as `{prompt_hash}.json`."""

    def __init__(self, inner: LLMProvider, fixtures_dir: Path) -> None:
        self.inner = inner
        self.fixtures_dir = fixtures_dir
        self.id = inner.id

    def preflight(self) -> list[PreflightIssue]:
        return self.inner.preflight()

    def complete_json(
        self, system: str, user: str, schema: dict[str, Any], *, temperature: float, seed: int | None
    ) -> dict[str, Any]:
        result = self.inner.complete_json(system, user, schema, temperature=temperature, seed=seed)
        self.fixtures_dir.mkdir(parents=True, exist_ok=True)
        path = self.fixtures_dir / f"{prompt_hash(system, user, schema)}.json"
        path.write_text(
            json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        return as_dict(result)


class FakeEmbeddings:
    """Deterministic bag-of-words vectors: shared words raise cosine similarity; no randomness."""

    id = "fake"

    def __init__(self, dimensions: int = EMBEDDING_DIMENSIONS) -> None:
        self.dimensions: int | None = dimensions

    def preflight(self) -> list[PreflightIssue]:
        return []

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._vector(t) for t in texts]

    def _vector(self, text: str) -> list[float]:
        size = self.dimensions or EMBEDDING_DIMENSIONS
        vector = [0.0] * size
        for token in TOKEN_RE.findall(text.lower()):
            bucket = (
                int(hashlib.sha1(token.encode("utf-8"), usedforsecurity=False).hexdigest()[:8], 16) % size
            )
            vector[bucket] += 1.0
        norm = math.sqrt(sum(x * x for x in vector))
        return [x / norm for x in vector] if norm else vector
