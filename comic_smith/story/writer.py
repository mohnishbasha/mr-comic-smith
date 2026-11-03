"""Strip writer: turn a beat into Panel Specs the renderer and lettering engine can use (FR-013).

The model drafts, deterministic code decides. Every output is checked for cast integrity, the
audience reading limits, shot variety, panel count, and the balloon-space hint; on any violation the
model gets exactly one corrective retry with the violations listed, then `GenerationInvalidError`
(exit 5) is raised. Story text is untrusted: it is fenced inside one data block (ADR-007).
"""

import json
import logging
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from comic_smith.backends.llm.base import TEMPERATURE_INTERACTIVE
from comic_smith.context import Ctx
from comic_smith.db.models import Character, Panel
from comic_smith.errors import GenerationInvalidError, PrerequisiteError, UsageError
from comic_smith.models import Audience, Beat, Bible, PanelSpec, StripScript, llm_schema
from comic_smith.models._base import BalloonSpace
from comic_smith.story import bible as bible_service
from comic_smith.story import moderation
from comic_smith.story.branches import branch_strips, resolve_branch
from comic_smith.story.prompts import load_prompt, wrap_untrusted

log = logging.getLogger(__name__)

DEFAULT_PANELS = 4
MIN_PANELS, MAX_PANELS = 1, 6
MAX_SAME_SHOT_RUN = 2
CONTEXT_STRIPS = 3
MAX_NOTES = 12
DATA_LABEL = "STORY_DATA"


@dataclass(frozen=True)
class AudienceLimits:
    """Reading limits for one audience (FR-013; recorded in docs/PRD.md FR-013)."""

    words_per_balloon: int
    balloons_per_panel: int
    words_per_strip: int


# Words per strip count dialogue and captions together. A 6-panel strip may hit the strip limit
# before the per-panel limits, which is intended: it keeps dense strips readable.
LIMITS: dict[Audience, AudienceLimits] = {
    Audience.KIDS_5_8: AudienceLimits(10, 2, 60),
    Audience.KIDS_9_12: AudienceLimits(18, 3, 110),
    Audience.ALL_AGES: AudienceLimits(20, 3, 130),
    Audience.TEEN: AudienceLimits(25, 4, 170),
    Audience.ADULT: AudienceLimits(30, 4, 220),
}


def limits_for(audience: Audience | str) -> AudienceLimits:
    """Reading limits for an audience."""
    return LIMITS[Audience(audience)]


def _words(text: str) -> int:
    return len(text.split())


def panel_violations(spec: PanelSpec, cast_ids: set[str], limits: AudienceLimits) -> list[str]:
    """Rule violations inside one panel (cast, balloons, balloon-space hint)."""
    out: list[str] = []
    n = spec.idx
    for char in spec.characters:
        if char.id not in cast_ids:
            out.append(f"panel {n}: character '{char.id}' is not in the cast")
    for sfx in spec.sfx:
        if sfx.near is not None and sfx.near not in cast_ids:
            out.append(f"panel {n}: sfx near '{sfx.near}' is not in the cast")
    for balloon in spec.dialogue:
        if balloon.speaker not in cast_ids:
            out.append(f"panel {n}: speaker '{balloon.speaker}' is not in the cast")
        if _words(balloon.text) > limits.words_per_balloon:
            out.append(f"panel {n}: a balloon has more than {limits.words_per_balloon} words")
    if len(spec.dialogue) > limits.balloons_per_panel:
        out.append(f"panel {n}: more than {limits.balloons_per_panel} balloons")
    if (spec.dialogue or spec.caption) and spec.balloon_space == BalloonSpace.NONE:
        out.append(f"panel {n}: has text, so balloon_space must name where the balloons go")
    return out


def strip_words(panels: Iterable[PanelSpec]) -> int:
    """Total lettered words in a strip: dialogue plus captions."""
    return sum(
        sum(_words(d.text) for d in p.dialogue) + (_words(p.caption) if p.caption else 0) for p in panels
    )


def script_violations(
    script: StripScript, cast_ids: set[str], limits: AudienceLimits, expected_panels: int
) -> list[str]:
    """Every rule violation in a script; empty when it is acceptable."""
    out: list[str] = []
    if len(script.panels) != expected_panels:
        out.append(f"expected {expected_panels} panels, got {len(script.panels)}")
    for panel in script.panels:
        out += panel_violations(panel, cast_ids, limits)
    if strip_words(script.panels) > limits.words_per_strip:
        out.append(f"the strip has more than {limits.words_per_strip} words in total")
    run = 1
    for prev, cur in zip(script.panels, script.panels[1:], strict=False):
        run = run + 1 if cur.shot == prev.shot else 1
        if run > MAX_SAME_SHOT_RUN:
            out.append(
                f"panels {cur.idx - run + 1} to {cur.idx} all use the '{cur.shot}' shot; vary the shots"
            )
            run = 1
    return out


def previous_notes(
    session: Session, project_id: str, branch_ref: str, limit: int = CONTEXT_STRIPS
) -> list[dict[str, Any]]:
    """Beat and continuity notes of the last few strips on a branch (oldest first)."""
    branch = resolve_branch(session, project_id, branch_ref)
    notes: list[dict[str, Any]] = []
    for strip in branch_strips(session, branch)[-limit:]:
        panels = session.scalars(select(Panel).where(Panel.strip_id == strip.id).order_by(Panel.idx))
        specs = [p.spec_json for p in panels]
        found = [str(n) for spec in specs for n in spec.get("continuity", [])]
        last = specs[-1] if specs else {}
        notes.append(
            {
                "strip": strip.idx,
                "beat": strip.beat_json.get("beat", ""),
                "notes": list(dict.fromkeys(found))[:MAX_NOTES],
                "last_setting": last.get("setting", ""),
            }
        )
    return notes


def cast_context(session: Session, bible: Bible) -> list[dict[str, str]]:
    """Cast list for prompts: id, name, role, and visual description when known."""
    ids = [c.character_id for c in bible.cast]
    rows = {r.id: r for r in session.scalars(select(Character).where(Character.id.in_(ids)))}
    return [
        {
            "id": c.character_id,
            "name": rows[c.character_id].name if c.character_id in rows else c.character_id,
            "role": c.role,
            "want": c.want or "",
        }
        for c in bible.cast
    ]


def build_context(
    bible: Bible, cast: list[dict[str, str]], beat: Beat, panels: int, notes: list[dict[str, Any]]
) -> dict[str, Any]:
    """The JSON data block placed in the user message."""
    lim = limits_for(bible.audience)
    return {
        "panels": panels,
        "beat": beat.model_dump(mode="json", exclude={"original_text"}),
        "story": {
            "title": bible.working_title,
            "premise": bible.premise,
            "tone": bible.tone,
            "world": bible.setting.world,
            "audience": bible.audience.value,
        },
        "cast": cast,
        "continuity_notes": notes,
        "limits": {
            "words_per_balloon": lim.words_per_balloon,
            "balloons_per_panel": lim.balloons_per_panel,
            "words_per_strip": lim.words_per_strip,
            "max_same_shot_in_a_row": MAX_SAME_SHOT_RUN,
        },
    }


def _attempt(ctx: Ctx, system: str, user: str, temperature: float) -> tuple[StripScript | None, list[str]]:
    """One model call; returns the parsed script or the schema problems found."""
    raw = ctx.require_llm().complete_json(
        system, user, llm_schema(StripScript), temperature=temperature, seed=None
    )
    try:
        return StripScript.model_validate(raw), []
    except ValidationError as exc:
        return None, [f"schema: {e['loc']}: {e['msg']}" for e in exc.errors()[:5]]


def _script_texts(script: StripScript) -> list[str]:
    texts: list[str] = []
    for p in script.panels:
        texts += [p.setting, p.action, *(d.text for d in p.dialogue), *(s.text for s in p.sfx)]
        texts += [p.caption] if p.caption else []
    return texts


def write_strip(
    ctx: Ctx,
    beat: Beat,
    *,
    panels: int = DEFAULT_PANELS,
    branch: str = "main",
    temperature: float = TEMPERATURE_INTERACTIVE,
) -> StripScript:
    """Write 1 to 6 Panel Specs for a beat.

    Args:
        ctx: Open project context; its LLM writes the script.
        beat: The accepted beat.
        panels: Panel count, 1 to 6 (default 4).
        branch: Branch name or id whose earlier strips supply continuity notes.
        temperature: 0.8 for interactive use; auto mode passes 0.

    Raises:
        UsageError: Panel count outside 1 to 6.
        PrerequisiteError: The project has no bible yet.
        GenerationInvalidError: Still invalid after the single corrective retry (exit 5).
        SafetyError: Moderation blocked the script.
    """
    if not MIN_PANELS <= panels <= MAX_PANELS:
        raise UsageError(f"A strip has {MIN_PANELS} to {MAX_PANELS} panels, not {panels}.")
    with ctx.project.session(readonly=True) as view:
        bible = bible_service.current_bible(view, ctx.project_id)
        if bible is None:
            raise PrerequisiteError("There is no story bible yet.", hint="Create the bible first.")
        cast = cast_context(view, bible)
        notes = previous_notes(view, ctx.project_id, branch)
    audience = bible.audience
    data = build_context(bible, cast, beat, panels, notes)
    system = load_prompt("strip_writer").system(moderation.audience_rules(audience.value), panels=panels)
    user = wrap_untrusted(DATA_LABEL, json.dumps(data, ensure_ascii=False))
    script = _validated(ctx, system, user, temperature, {c["id"] for c in cast}, data, audience)
    moderation.check_texts(ctx, "script", _script_texts(script), audience.value)
    return script


def _validated(
    ctx: Ctx,
    system: str,
    user: str,
    temperature: float,
    cast_ids: set[str],
    data: dict[str, Any],
    audience: Audience,
) -> StripScript:
    """Call the model, validate, and retry once with the violations listed."""
    limits, expected = limits_for(audience), int(data["panels"])
    problems: list[str] = []
    for attempt in range(2):
        prompt = (
            user
            if not problems
            else f"{user}\n\nYour previous reply broke these rules. Fix them all:\n"
            + "\n".join(f"- {p}" for p in problems)
        )
        script, problems = _attempt(ctx, system, prompt, temperature)
        if script is not None:
            problems = script_violations(script, cast_ids, limits, expected)
            if not problems:
                return script
        log.info("strip script rejected (attempt %s): %s", attempt + 1, problems)
    raise GenerationInvalidError(
        "The model could not write a usable script for this beat.",
        hint="Try again, or pick a different beat.",
        detail="; ".join(problems),
        stage="story.writer",
    )
