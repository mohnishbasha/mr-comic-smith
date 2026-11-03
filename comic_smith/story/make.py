"""Turn a pick from the latest suggestions, or the author's own words, into a scripted strip."""

from typing import Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from comic_smith.backends.llm.base import TEMPERATURE_INTERACTIVE
from comic_smith.context import Ctx
from comic_smith.db.models import SuggestionSet as SuggestionRow
from comic_smith.errors import PrerequisiteError, UsageError
from comic_smith.models import Beat, SuggestionOption, SuggestionSet
from comic_smith.story import beats, strips, writer
from comic_smith.story._history import approved_strips, branch_by_name
from comic_smith.story.strips import StripDetail

Pick = int | Literal["end"]
END_INDEX = 3
PICK_TEXT = "Pick 1, 2, 3, or end."


def parse_pick(value: int | str) -> Pick:
    """Accept 1, 2, 3, 'end', or their string forms; anything else is a usage error."""
    text = str(value).strip().lower()
    if text == "end":
        return "end"
    if text in {"1", "2", "3"}:
        return int(text)
    raise UsageError(f"'{value}' is not a valid pick.", hint=PICK_TEXT)


def stored_set(
    session: Session, project_id: str, branch: str, set_id: str | None
) -> tuple[str, SuggestionSet]:
    """The named suggestion set, or the newest one on the branch; it must follow the last approved strip."""
    target = branch_by_name(session, project_id, branch)
    stmt = select(SuggestionRow).where(SuggestionRow.project_id == project_id)
    if set_id:
        stmt = stmt.where(SuggestionRow.id == set_id)
    else:
        stmt = stmt.where(SuggestionRow.branch_id == target.id)
    row = session.scalars(stmt.order_by(SuggestionRow.created_at.desc(), SuggestionRow.id.desc())).first()
    if row is None:
        raise PrerequisiteError("There are no suggestions to pick from yet.", hint="Run suggest first.")
    sset = SuggestionSet.model_validate(row.json)
    last = approved_strips(session, project_id, branch)
    if sset.after_strip != (last[-1].idx if last else 0):
        raise PrerequisiteError(
            "Those suggestions are out of date because a strip was approved since.",
            hint="Run suggest again.",
        )
    return row.id, sset


def option_for(sset: SuggestionSet, pick: Pick) -> tuple[SuggestionOption, int]:
    """The picked option and its stored index (0 to 2 for options, 3 for the end option)."""
    if pick == "end":
        if sset.end_here is None:
            raise UsageError(
                "The story is not ready to end yet.", hint="The end option appears near the end of the arc."
            )
        return sset.end_here, END_INDEX
    return sset.options[pick - 1], pick - 1


def make_strip(
    ctx: Ctx,
    *,
    pick: int | str | None = None,
    beat: str | None = None,
    set_id: str | None = None,
    panels: int = writer.DEFAULT_PANELS,
    branch: str = "main",
    temperature: float = TEMPERATURE_INTERACTIVE,
) -> StripDetail:
    """Write the next strip from exactly one of `pick` or `beat` (free text, normalized first)."""
    if (pick is None) == (beat is None):
        raise UsageError("Give exactly one of a pick or a beat.", hint=f"{PICK_TEXT} Or describe the beat.")
    link: str | None = None
    chosen: int | None = None
    if pick is not None:
        parsed = parse_pick(pick)
        with ctx.project.session(readonly=True) as view:
            link, sset = stored_set(view, ctx.project_id, branch, set_id)
        option, chosen = option_for(sset, parsed)
        the_beat: Beat = beats.beat_from_option(option)
    else:
        assert beat is not None  # noqa: S101
        the_beat = beats.normalize_beat(ctx, beat, branch=branch)
    strip_id = strips.create_strip(
        ctx,
        the_beat,
        panels=panels,
        branch=branch,
        suggestion_set_id=link,
        pick=chosen,
        temperature=temperature,
    )
    with ctx.project.session(readonly=True) as view:
        return strips.strip_detail(view, strip_id)
