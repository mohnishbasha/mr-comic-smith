"""Auto mode (FR-026): suggest, pick by policy, write, and approve strips until the target length.

Script-only in Sprint 1. Picks are deterministic (no randomness) so a run is reproducible: the
policy chooses an intent from the number of strips already approved. Everything runs with actor
`auto` at temperature 0, so each suggestion, strip, and approval is its own undoable event, and
`auto.started`, `auto.pick`, and `auto.stopped` notes record the policy. Never finalizes.
"""

from collections.abc import Callable
from typing import Literal, get_args

from sqlalchemy.orm import Session

from comic_smith.backends.llm.base import TEMPERATURE_DETERMINISTIC
from comic_smith.context import Ctx
from comic_smith.db.base import JsonObject
from comic_smith.errors import PrerequisiteError, UsageError
from comic_smith.events import register_handler
from comic_smith.models import Intent, SuggestionSet
from comic_smith.models.story import SUGGESTION_ORDER
from comic_smith.story import make, strips
from comic_smith.story._history import approved_strips
from comic_smith.story.bible import current_bible
from comic_smith.story.branches import branch_strips, resolve_branch
from comic_smith.story.strips import StripDetail
from comic_smith.story.suggest import suggest_next

STARTED = "auto.started"
PICKED = "auto.pick"
STOPPED = "auto.stopped"
Policy = Literal["balanced", "steer", "twist"]
POLICIES: tuple[str, ...] = get_args(Policy)
CYCLES: dict[str, tuple[Intent, ...]] = {
    "balanced": (Intent.CONTINUE, Intent.STEER, Intent.TWIST),
    "steer": (Intent.STEER, Intent.STEER, Intent.CONTINUE),
    "twist": (Intent.TWIST, Intent.TWIST, Intent.CONTINUE),
}


@register_handler(STARTED)
@register_handler(PICKED)
@register_handler(STOPPED)
def _apply_note(txn: Session, payload: JsonObject) -> None:
    """Auto notes only live in the event log (history); they change no table."""


def check_policy(policy: str) -> Policy:
    """The policy, or a usage error that names the choices."""
    if policy not in POLICIES:
        raise UsageError(f"'{policy}' is not an auto policy.", hint=f"Use one of: {', '.join(POLICIES)}.")
    return policy  # type: ignore[return-value]


def choose_pick(policy: str, options: SuggestionSet, approved: int, target: int) -> make.Pick:
    """Pick 1, 2, 3, or 'end' for the next strip.

    The end option wins when offered and this strip reaches the target; otherwise the policy cycle
    (indexed by strips approved so far) names the intent.
    """
    if options.end_here is not None and approved + 1 >= target:
        return "end"
    intent = CYCLES[check_policy(policy)][approved % len(CYCLES[policy])]
    return SUGGESTION_ORDER.index(intent) + 1


def _note(ctx: Ctx, event_type: str, payload: JsonObject) -> None:
    with ctx.project.session() as session:
        ctx.events(session).apply(event_type, payload, None, ctx.actor)


def _state(ctx: Ctx, branch: str | None) -> tuple[str, int, int, int]:
    """Branch name, approved count, unapproved count, and the bible's target length."""
    with ctx.project.session(readonly=True) as view:
        bible = current_bible(view, ctx.project_id)
        if bible is None:
            raise PrerequisiteError("There is no story bible yet.", hint="Create the story first.")
        target = resolve_branch(view, ctx.project_id, branch)
        approved = len(approved_strips(view, ctx.project_id, target.name))
        pending = len(branch_strips(view, target)) - approved
        return target.name, approved, pending, bible.arc.target_strips


def run_auto(
    ctx: Ctx,
    *,
    policy: str = "balanced",
    until_target: bool = True,
    branch: str | None = None,
    on_strip: Callable[[StripDetail], None] | None = None,
) -> list[StripDetail]:
    """Write and approve strips until the bible's target length (or one strip when not `until_target`).

    Raises:
        UsageError: Unknown policy.
        PrerequisiteError: No bible, or the branch has strips waiting for approval.
        ImmutableEntityError: The branch is finalized.
    """
    chosen = check_policy(policy)
    name, approved, pending, target = _state(ctx, branch)
    if pending:
        raise PrerequisiteError(
            f"{pending} strip(s) on '{name}' are waiting for approval.",
            hint="Approve them (or undo them) before running auto.",
        )
    saved_actor, ctx.actor = ctx.actor, "auto"
    made: list[StripDetail] = []
    try:
        _note(ctx, STARTED, {"policy": chosen, "branch": name, "approved": approved, "target": target})
        while approved < target:
            options = suggest_next(ctx, branch=name, temperature=TEMPERATURE_DETERMINISTIC)
            pick = choose_pick(chosen, options, approved, target)
            _note(ctx, PICKED, {"policy": chosen, "pick": pick, "strip": approved + 1})
            written = make.make_strip(ctx, pick=pick, branch=name, temperature=TEMPERATURE_DETERMINISTIC)
            info = strips.approve_strip(ctx, written.id, branch=name)
            written = written.model_copy(update={"status": info.status, "approved_at": info.approved_at})
            made.append(written)
            approved += 1
            if on_strip is not None:
                on_strip(written)
            if not until_target:
                break
        reason = "target" if approved >= target else "one-step"
        _note(ctx, STOPPED, {"policy": chosen, "reason": reason, "strips": len(made)})
    finally:
        ctx.actor = saved_actor
    return made
