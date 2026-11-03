"""Plot suggestions: continue, twist, steer, and end-here (S1-T05, FR-011).

Flow: read the bible and the last approved strips, ask the LLM at temperature 0.8, check the three
options are pairwise distinct with embeddings (regenerate once), moderate the text, then store the
set through a `suggestions.created` event. Thumbnails are deferred (S3-T09); the field stays.
"""

import logging
import math
from dataclasses import dataclass

from pydantic import Field
from sqlalchemy.orm import Session

from comic_smith.backends.llm.base import TEMPERATURE_INTERACTIVE
from comic_smith.context import Ctx
from comic_smith.db.base import JsonObject, utc_now_iso
from comic_smith.db.models import Strip
from comic_smith.db.models import SuggestionSet as SuggestionRow
from comic_smith.errors import PrerequisiteError, SchemaValidationError
from comic_smith.events import Inverse, register_handler
from comic_smith.ids import PREFIXES, new_id
from comic_smith.models import Bible, Intent, SuggestionOption, SuggestionSet
from comic_smith.models._base import Strict
from comic_smith.models.story import SUGGESTION_ORDER
from comic_smith.story._history import approved_strips, branch_by_name
from comic_smith.story._llm import call_model
from comic_smith.story._wire import context_block
from comic_smith.story.arc import ArcState, arc_state, fit_stage, next_stage, open_threads
from comic_smith.story.bible import current_bible, fit_characters
from comic_smith.story.moderation import check_texts

log = logging.getLogger(__name__)

SUGGESTIONS_CREATED = "suggestions.created"
SUGGESTIONS_DISCARDED = "suggestions.discarded"
SUGGESTION_MAX_SIMILARITY = 0.85
RECENT_STRIPS = 3
RETRY_HINT = "The previous options were too similar. Make the three options clearly different."


class SuggestionDraft(Strict):
    """What the LLM returns: three options, plus an end option when asked."""

    options: list[SuggestionOption] = Field(min_length=3, max_length=3)
    end_here: SuggestionOption | None = None


@dataclass(frozen=True)
class _Situation:
    bible: Bible
    state: ArcState
    recent: list[dict[str, object]]
    after_id: str | None
    after_idx: int
    branch_id: str


def cosine(a: list[float], b: list[float]) -> float:
    """Cosine similarity of two vectors; 0.0 when either is all zeros."""
    norm = math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b))
    return sum(x * y for x, y in zip(a, b, strict=True)) / norm if norm else 0.0


def max_pairwise_similarity(vectors: list[list[float]]) -> float:
    return max(
        (cosine(vectors[i], vectors[j]) for i in range(len(vectors)) for j in range(i + 1, len(vectors))),
        default=0.0,
    )


def option_text(option: SuggestionOption) -> str:
    """The text compared for distinctness: beat plus description."""
    return f"{option.beat} {option.description}"


def _summary(strip: Strip) -> dict[str, object]:
    return {
        "idx": strip.idx,
        "stage": strip.arc_stage,
        "summary": str(strip.beat_json.get("beat", "")),
    }


def _situation(ctx: Ctx, branch: str) -> _Situation:
    with ctx.project.session(readonly=True) as s:
        bible = current_bible(s, ctx.project_id)
        if bible is None:
            raise PrerequisiteError("There is no story bible yet.", hint="Create the story first.")
        strips = approved_strips(s, ctx.project_id, branch)
        branch_id = branch_by_name(s, ctx.project_id, branch).id
    last = strips[-1] if strips else None
    return _Situation(
        bible=bible,
        state=arc_state(bible, strips),
        recent=[_summary(x) for x in strips[-RECENT_STRIPS:]],
        after_id=last.id if last else None,
        after_idx=last.idx if last else 0,
        branch_id=branch_id,
    )


def _facts(sit: _Situation, retry: bool) -> JsonObject:
    bible = sit.bible
    facts: JsonObject = {
        "audience": bible.audience.value,
        "bible": bible.model_dump(mode="json"),
        "recent_strips": sit.recent,
        "open_threads": [{"id": t.id, "text": t.text} for t in open_threads(bible)],
        "arc_stage": sit.state.stage,
        "next_stage": next_stage(bible, sit.state.stage),
        "arc_progress": sit.state.progress,
        "strips_approved": sit.state.strips_approved,
        "include_end_here": sit.state.final,
    }
    if retry:
        facts["retry_hint"] = RETRY_HINT
    return facts


def _fit_option(sit: _Situation, option: SuggestionOption) -> SuggestionOption:
    return option.model_copy(
        update={
            "characters": fit_characters(sit.bible, option.characters),
            "arc_stage": fit_stage(sit.bible, option.arc_stage, sit.state.stage),
        }
    )


def _end_option(sit: _Situation, draft: SuggestionDraft) -> SuggestionOption:
    bible = sit.bible
    final_stage = fit_stage(bible, bible.arc.stages[-1] if bible.arc.stages else None)
    base = draft.end_here or SuggestionOption(
        intent=Intent.END,
        beat="Wrap up the story here",
        description=f"The story comes to a satisfying close. {bible.logline}"[:300],
        arc_stage=final_stage,
        characters=[bible.cast[0].character_id],
        thumbnail_prompt="The whole cast together, relieved and smiling, a calm final scene",
    )
    fitted = _fit_option(sit, base)
    return fitted.model_copy(update={"intent": Intent.END, "arc_stage": final_stage})


def _ask(ctx: Ctx, sit: _Situation, retry: bool, temperature: float) -> SuggestionDraft:
    draft = call_model(
        ctx,
        "suggest",
        SuggestionDraft,
        audience=sit.bible.audience.value,
        user=context_block(_facts(sit, retry)),
        temperature=temperature,
    )
    by_intent = {o.intent: o for o in draft.options}
    if set(by_intent) != set(SUGGESTION_ORDER) or len(draft.options) != len(by_intent):
        raise SchemaValidationError(
            "The ideas did not cover continue, twist, and steer.", hint="Try again.", retryable=True
        )
    ordered = [_fit_option(sit, by_intent[i]) for i in SUGGESTION_ORDER]
    return SuggestionDraft(options=ordered, end_here=draft.end_here)


def _too_similar(ctx: Ctx, draft: SuggestionDraft) -> bool:
    vectors = ctx.require_embeddings().embed([option_text(o) for o in draft.options])
    return max_pairwise_similarity(vectors) > SUGGESTION_MAX_SIMILARITY


def _distinct_draft(ctx: Ctx, sit: _Situation, temperature: float) -> SuggestionDraft:
    draft = _ask(ctx, sit, retry=False, temperature=temperature)
    if _too_similar(ctx, draft):
        draft = _ask(ctx, sit, retry=True, temperature=temperature)
        if _too_similar(ctx, draft):
            log.warning(
                "distinctness_warning: options still above %s after one retry", SUGGESTION_MAX_SIMILARITY
            )
    return draft


@register_handler(SUGGESTIONS_CREATED)
def _apply_created(txn: Session, payload: JsonObject) -> None:
    """Insert one stored suggestion set."""
    txn.add(
        SuggestionRow(
            id=payload["id"],
            project_id=payload["project_id"],
            branch_id=payload["branch_id"],
            after_strip_id=payload["after_strip_id"],
            json=payload["json"],
            created_at=payload["created_at"],
        )
    )


@register_handler(SUGGESTIONS_DISCARDED)
def _apply_discarded(txn: Session, payload: JsonObject) -> None:
    """Remove a stored suggestion set (the inverse of creating it)."""
    row = txn.get(SuggestionRow, payload["id"])
    if row is not None:
        txn.delete(row)


def suggest_next(
    ctx: Ctx, *, branch: str = "main", temperature: float = TEMPERATURE_INTERACTIVE
) -> SuggestionSet:
    """Offer continue, twist, and steer options (plus end-here at the end) for the next strip.

    Raises:
        PrerequisiteError: No bible yet.
        UsageError: Unknown branch.
        OriginalityBlockedError, AudienceBlockedError: An option failed a guard.
    """
    sit = _situation(ctx, branch)
    draft = _distinct_draft(ctx, sit, temperature)
    end = _end_option(sit, draft) if sit.state.final else None
    result = SuggestionSet(
        after_strip=sit.after_idx,
        arc_progress=sit.state.progress,
        options=draft.options,
        end_here=end,
    )
    shown = [*result.options, *([end] if end else [])]
    check_texts(
        ctx,
        "suggestion",
        [t for o in shown for t in (o.beat, o.description, o.thumbnail_prompt)],
        sit.bible.audience.value,
    )
    payload: JsonObject = {
        "id": new_id(PREFIXES["suggestion_set"]),
        "project_id": ctx.project_id,
        "branch_id": sit.branch_id,
        "after_strip_id": sit.after_id,
        "json": result.model_dump(mode="json"),
        "created_at": utc_now_iso(),
    }
    with ctx.project.session() as session:
        inverse = Inverse(SUGGESTIONS_DISCARDED, {"id": payload["id"]})
        ctx.events(session).apply(SUGGESTIONS_CREATED, payload, inverse, ctx.actor)
    return result
