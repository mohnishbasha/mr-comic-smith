"""Arc stage tracking, progress, and open threads (S1-T04, FR-010).

The current stage is not stored on the bible: it is the `arc_stage` of the latest approved strip
(the bible only holds the template, its stages, and the thread list). Open threads live on the
bible; a closed thread keeps its row with `closed_in_strip` set so continuity review can see it.
"""

import logging
from dataclasses import dataclass

from sqlalchemy.orm import Session

from comic_smith.backends.llm.base import TEMPERATURE_DETERMINISTIC
from comic_smith.context import Ctx
from comic_smith.db.base import JsonObject
from comic_smith.db.models import Branch, Strip
from comic_smith.errors import PrerequisiteError
from comic_smith.events import Inverse, register_handler
from comic_smith.models import ArcDiff, ArcTemplate, Bible, OpenThread
from comic_smith.story._history import approved_strips
from comic_smith.story._llm import call_model
from comic_smith.story._wire import context_block
from comic_smith.story.bible import arc_templates, current_bible, save_bible
from comic_smith.story.prompts import wrap_untrusted

__all__ = [
    "GAG_STAGE",
    "ArcState",
    "apply_strip_approval",
    "arc_progress",
    "arc_state",
    "arc_templates",
    "fit_stage",
    "is_final_stage",
    "open_threads",
]

log = logging.getLogger(__name__)

STRIP_ARC_TAGGED = "strip.arc_tagged"
GAG_STAGE = "standalone"


@dataclass(frozen=True)
class ArcState:
    """Where a branch stands in its arc."""

    stage: str | None
    strips_approved: int
    progress: float
    target_strips: int
    final: bool


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, value))


def arc_progress(bible: Bible, strips_count: int, stage: str | None = None) -> float:
    """Progress from 0.0 to 1.0.

    With a stage, the mean of how far along the stage list it is and how far along the target
    length the story is; without one (or for gag-a-day, which has no stages) strips over target.
    """
    by_count = _clamp(strips_count / bible.arc.target_strips)
    stages = bible.arc.stages
    if bible.arc.template is ArcTemplate.GAG_A_DAY or stage is None or stage not in stages:
        return by_count
    by_stage = (stages.index(stage) + 1) / len(stages)
    return _clamp((by_stage + by_count) / 2)


def is_final_stage(bible: Bible, stage: str | None) -> bool:
    """True when `stage` is the last stage of a template that has stages."""
    stages = bible.arc.stages
    return bool(stages) and stage == stages[-1]


def fit_stage(bible: Bible, stage: str | None, fallback: str | None = None) -> str:
    """A valid stage for the bible's template: `stage` if listed, else `fallback`, else the first."""
    stages = bible.arc.stages
    if not stages:
        return GAG_STAGE
    for candidate in (stage, fallback):
        if candidate in stages:
            return str(candidate)
    return stages[0]


def next_stage(bible: Bible, stage: str | None) -> str:
    """The stage after `stage` (clamped at the last); the first stage when there is none yet."""
    stages = bible.arc.stages
    if not stages:
        return GAG_STAGE
    return stages[min(stages.index(stage) + 1, len(stages) - 1)] if stage in stages else stages[0]


def open_threads(bible: Bible) -> list[OpenThread]:
    """Threads not yet closed."""
    return [t for t in bible.open_threads if t.closed_in_strip is None]


def arc_state(bible: Bible, strips: list[Strip]) -> ArcState:
    """Stage, counts, and progress after the given approved strips (reading order)."""
    stage = strips[-1].arc_stage if strips else None
    return ArcState(
        stage=stage,
        strips_approved=len(strips),
        progress=arc_progress(bible, len(strips), stage),
        target_strips=bible.arc.target_strips,
        final=is_final_stage(bible, stage) or len(strips) >= bible.arc.target_strips,
    )


@register_handler(STRIP_ARC_TAGGED)
def _apply_arc_tagged(txn: Session, payload: JsonObject) -> None:
    """Set the arc stage of one strip."""
    strip = txn.get(Strip, payload["strip_id"])
    if strip is not None:
        strip.arc_stage = payload["arc_stage"]


def _arc_context(bible: Bible, strip: Strip, count: int) -> str:
    facts = {
        "audience": bible.audience.value,
        "arc_template": bible.arc.template.value,
        "stages": bible.arc.stages,
        "target_strips": bible.arc.target_strips,
        "strips_approved": count,
        "strip_idx": strip.idx,
        "strip_stage": strip.arc_stage,
        "strip_intent": strip.beat_json.get("intent"),
        "open_threads": [{"id": t.id, "text": t.text} for t in open_threads(bible)],
    }
    beat = f"{strip.beat_json.get('beat', '')}. {strip.beat_json.get('description', '')}"
    return f"{context_block(facts)}\n\n{wrap_untrusted('approved strip', beat)}"


def _updated_threads(bible: Bible, diff: ArcDiff, strip_idx: int) -> list[OpenThread] | None:
    """Thread list after the diff, or None when nothing changed. Unknown or closed ids are ignored."""
    threads = [t.model_copy() for t in bible.open_threads]
    open_ids = {t.id for t in threads if t.closed_in_strip is None}
    changed = False
    for thread in threads:
        if thread.id in diff.threads_closed and thread.id in open_ids:
            thread.closed_in_strip = strip_idx
            changed = True
    number = 1 + max((int(t.id[1:]) for t in threads if t.id[1:].isdigit()), default=0)
    for text in diff.threads_opened:
        threads.append(OpenThread(id=f"t{number}", text=text, opened_in_strip=strip_idx))
        number += 1
        changed = True
    return threads if changed else None


def apply_strip_approval(ctx: Ctx, session: Session, strip: Strip) -> ArcDiff:
    """After a strip is approved: ask the LLM for the arc diff, update the bible, tag the strip.

    The bible gets a new version only when threads changed. The strip's `arc_stage` is set from the
    diff through a `strip.arc_tagged` event. Close ids that are not open threads are ignored.

    Returns:
        The diff as applied (the stage is corrected to a listed stage).

    Raises:
        PrerequisiteError: The project has no bible.
    """
    bible = current_bible(session, ctx.project_id)
    if bible is None:
        raise PrerequisiteError("There is no story bible yet.", hint="Create the story first.")
    ids = {s.id for s in approved_strips(session, ctx.project_id, _branch_name(session, strip))}
    count = len(ids | {strip.id})
    raw = call_model(
        ctx,
        "arc_update",
        ArcDiff,
        audience=bible.audience.value,
        user=_arc_context(bible, strip, count),
        temperature=TEMPERATURE_DETERMINISTIC,
    )
    diff = raw.model_copy(update={"stage": fit_stage(bible, raw.stage, strip.arc_stage)})
    threads = _updated_threads(bible, diff, strip.idx)
    if threads is not None:
        save_bible(ctx, session, bible.model_copy(update={"open_threads": threads}), actor=ctx.actor)
    inverse = Inverse(STRIP_ARC_TAGGED, {"strip_id": strip.id, "arc_stage": strip.arc_stage})
    ctx.events(session).apply(
        STRIP_ARC_TAGGED, {"strip_id": strip.id, "arc_stage": diff.stage}, inverse, ctx.actor
    )
    log.info("strip %s tagged %s", strip.idx, diff.stage)
    return diff


def _branch_name(session: Session, strip: Strip) -> str:
    branch = session.get(Branch, strip.branch_id)
    return branch.name if branch is not None else "main"
