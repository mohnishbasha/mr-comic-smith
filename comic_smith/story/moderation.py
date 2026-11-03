"""Audience guard and text moderation (S1-T08, FR-028, FR-006).

`check_texts` runs the originality denylist first (cheap, deterministic, names the rule), then an
LLM classifier with a strict JSON verdict. Anything unparseable fails closed. There is no bypass
flag: AGENTS.md forbids weakening these guards.
"""

import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import yaml

from comic_smith.context import Ctx
from comic_smith.errors import (
    AudienceBlockedError,
    ConfigError,
    GenerationInvalidError,
    OriginalityBlockedError,
)
from comic_smith.models import ModerationVerdict
from comic_smith.story._llm import call_model
from comic_smith.story._wire import context_block
from comic_smith.story.audience import audience_rules
from comic_smith.story.prompts import wrap_untrusted

__all__ = ["DenyRule", "TextKind", "audience_rules", "check_texts", "find_denied", "load_denylist"]

log = logging.getLogger(__name__)

TextKind = Literal["seed", "bible", "suggestion", "beat", "script", "prompt"]
DENYLIST_FILE = Path(__file__).resolve().parents[1] / "cast" / "denylist.yaml"
DENYLIST_VERSION = 1
RULE_KINDS = ("franchise", "character", "artist")
AUDIENCE_PHRASE = {
    "kids-5-8": "ages 5 to 8",
    "kids-9-12": "ages 9 to 12",
    "teen": "teens",
    "adult": "adults",
    "all-ages": "a family audience",
}
NAME_BLOCK = "That name belongs to someone else's character. Describe your own character and we will draw it."
ARTIST_BLOCK = "We do not copy living artists. Pick one of our looks or describe your own."


@dataclass(frozen=True)
class DenyRule:
    id: str
    kind: str
    pattern: re.Pattern[str]


_CACHE: dict[tuple[Path, int], tuple[DenyRule, ...]] = {}


def _compile(pattern: str) -> str:
    words = r"\s+".join(re.escape(w) for w in pattern.split())
    return rf"(?<!\w){words}(?!\w)"


def _parse(data: object, name: str) -> tuple[DenyRule, ...]:
    if not isinstance(data, dict) or data.get("version") != DENYLIST_VERSION:
        raise ConfigError(f"The denylist {name} must declare version {DENYLIST_VERSION}.")
    rules: list[DenyRule] = []
    for raw in data.get("rules") or []:
        kind = str(raw.get("kind"))
        patterns = [str(p) for p in raw.get("patterns") or [] if str(p).strip()]
        if kind not in RULE_KINDS or not raw.get("id") or not patterns:
            raise ConfigError(f"The denylist {name} has an invalid rule: {raw.get('id')!r}.")
        joined = "|".join(_compile(p) for p in patterns)
        rules.append(DenyRule(str(raw["id"]), kind, re.compile(joined, re.IGNORECASE)))
    return tuple(rules)


def load_denylist(path: Path | None = None) -> tuple[DenyRule, ...]:
    """Parse the denylist data file; cached per path and modification time."""
    target = path or DENYLIST_FILE
    key = (target, target.stat().st_mtime_ns)
    if key not in _CACHE:
        _CACHE[key] = _parse(yaml.safe_load(target.read_text(encoding="utf-8")), target.name)
    return _CACHE[key]


def find_denied(text: str, rules: tuple[DenyRule, ...] | None = None) -> DenyRule | None:
    """First rule whose pattern appears in `text`, or None."""
    return next((r for r in rules or load_denylist() if r.pattern.search(text)), None)


def _originality_error(rule: DenyRule) -> OriginalityBlockedError:
    message = ARTIST_BLOCK if rule.kind == "artist" else NAME_BLOCK
    return OriginalityBlockedError(
        f"{message} (Rule that triggered: {rule.id}.)",
        hint="Change the wording and try again.",
        detail=f"rule={rule.id}",
    )


def _audience_error(audience: str, verdict: ModerationVerdict | None) -> AudienceBlockedError:
    who = AUDIENCE_PHRASE.get(audience, "this audience")
    if verdict is None:
        message = "We could not check that idea for safety, so we skipped it. Try again in a moment."
        detail = "unparseable verdict"
    elif audience.startswith("kids"):
        message = f"That idea is not right for {who}, so we skipped it. Try a gentler twist."
        detail = f"category={verdict.category} rule={verdict.rule}"
    else:
        message = "We could not use that because it asks for something unsafe. Change it and try again."
        detail = f"category={verdict.category} rule={verdict.rule}"
    return AudienceBlockedError(message, hint="Change the idea and try again.", detail=detail)


def _verdict(ctx: Ctx, kind: TextKind, texts: list[str], audience: str) -> ModerationVerdict | None:
    user = "\n\n".join(
        [context_block({"kind": kind, "audience": audience, "count": len(texts)})]
        + [wrap_untrusted(f"text {i}", t) for i, t in enumerate(texts, 1)]
    )
    try:
        return call_model(ctx, "moderation", ModerationVerdict, audience=audience, user=user)
    except GenerationInvalidError:
        return None


def check_texts(ctx: Ctx, kind: TextKind, texts: list[str], audience: str) -> None:
    """Denylist, then LLM moderation, on user or model text.

    Raises:
        OriginalityBlockedError: A denylist rule matched (the message names the rule id).
        AudienceBlockedError: The classifier blocked the text, or its verdict was unusable.
        UsageError: Unknown audience.
    """
    audience_rules(audience)
    cleaned = [t for t in texts if t and t.strip()]
    if not cleaned:
        return
    rules = load_denylist()
    for text in cleaned:
        rule = find_denied(text, rules)
        if rule is not None:
            log.info("denylist rule %s matched in %s text", rule.id, kind)
            raise _originality_error(rule)
    verdict = _verdict(ctx, kind, cleaned, audience)
    if verdict is None or not verdict.allowed:
        log.info("moderation blocked %s text (audience %s)", kind, audience)
        raise _audience_error(audience, verdict)
