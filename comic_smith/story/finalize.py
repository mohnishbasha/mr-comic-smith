"""Finalize a story: continuity review, three titles and a blurb, then lock (FR-022, ARCHITECTURE 6.2).

`review` is read-only and returns a `ContinuityReport`. `finalize` runs it and locks the branch's
story unless issues are open and `force` is false, in which case `PrerequisiteError` carries the
report as JSON in `detail`. A finalized story is read-only (editing raises `ImmutableEntityError`);
`reopen` adds a new story version and unlocks, keeping the old row.

Events (undoable): `story.finalized` is an upsert of the story row's state (its inverse restores the
earlier state or removes the row), `story.reopened` inserts the next version, `story.removed`
deletes a row.
"""

import json
import logging
from datetime import UTC, datetime
from typing import Any

from pydantic import Field, ValidationError
from sqlalchemy.orm import Session

from comic_smith.backends.llm.base import TEMPERATURE_DETERMINISTIC, TEMPERATURE_INTERACTIVE
from comic_smith.context import Ctx
from comic_smith.db.base import JsonObject, utc_now_iso
from comic_smith.db.models import Branch, Story
from comic_smith.errors import (
    ImmutableEntityError,
    LLMOutputInvalidError,
    PrerequisiteError,
    UsageError,
)
from comic_smith.events import Inverse, register_handler
from comic_smith.ids import PREFIXES, new_id
from comic_smith.models import Bible, ContinuityIssue, ContinuityReport, StoryInfo, llm_schema
from comic_smith.models._base import Str80, Str160, Strict
from comic_smith.story import bible as bible_service
from comic_smith.story import moderation
from comic_smith.story.branches import branch_strips, latest_story, resolve_branch
from comic_smith.story.prompts import load_prompt, wrap_untrusted
from comic_smith.story.strips import list_panels

log = logging.getLogger(__name__)

FINALIZED = "story.finalized"
REOPENED = "story.reopened"
REMOVED = "story.removed"
DATA_LABEL = "STORY_DATA"
STORY_COLS = ("id", "project_id", "branch_id", "title", "blurb", "finalized_at", "continuity_json", "version")


class ContinuityReview(Strict):
    """What the continuity model returns: issues only; titles come from a second call."""

    issues: list[ContinuityIssue]


class TitleSuggestions(Strict):
    """What the titles model returns."""

    titles: list[Str80] = Field(min_length=3, max_length=3)
    blurb: Str160


@register_handler(FINALIZED)
def _apply_finalized(txn: Session, payload: JsonObject) -> None:
    row = txn.get(Story, payload["id"])
    if row is None:
        txn.add(Story(**{c: payload[c] for c in STORY_COLS}))
        return
    for col in ("title", "blurb", "finalized_at", "continuity_json"):
        setattr(row, col, payload[col])


@register_handler(REOPENED)
def _apply_reopened(txn: Session, payload: JsonObject) -> None:
    txn.add(Story(**{c: payload[c] for c in STORY_COLS}))


@register_handler(REMOVED)
def _apply_removed(txn: Session, payload: JsonObject) -> None:
    row = txn.get(Story, payload["story_id"])
    if row is not None:
        txn.delete(row)


def story_info(row: Story) -> StoryInfo:
    """API record for a story row."""
    return StoryInfo(
        id=row.id,
        project_id=row.project_id,
        branch_id=row.branch_id,
        title=row.title,
        blurb=row.blurb,
        version=row.version,
        finalized_at=datetime.fromisoformat(row.finalized_at) if row.finalized_at else None,
    )


def _strip_summaries(session: Session, branch: Branch) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for strip in branch_strips(session, branch):
        panels = [p.spec for p in list_panels(session, strip.id)]
        out.append(
            {
                "strip": strip.idx,
                "beat": strip.beat_json.get("beat", ""),
                "description": strip.beat_json.get("description", ""),
                "arc_stage": strip.arc_stage,
                "characters": sorted({c.id for p in panels for c in p.characters}),
                "continuity": [n for p in panels for n in p.continuity],
                "text": [d.text for p in panels for d in p.dialogue],
            }
        )
    return out


def _context(bible: Bible, strips: list[dict[str, Any]]) -> str:
    data = {
        "story": {"title": bible.working_title, "premise": bible.premise, "tone": bible.tone},
        "cast": [c.character_id for c in bible.cast],
        "open_threads": [t.model_dump(mode="json") for t in bible.open_threads],
        "strips": strips,
    }
    return wrap_untrusted(DATA_LABEL, json.dumps(data, ensure_ascii=False))


def _ask(ctx: Ctx, template: str, audience: str, user: str, model: type[Strict], temperature: float) -> Any:
    system = load_prompt(template).system(moderation.audience_rules(audience))
    raw = ctx.require_llm().complete_json(system, user, llm_schema(model), temperature=temperature, seed=None)
    try:
        return model.model_validate(raw)
    except ValidationError as exc:
        raise LLMOutputInvalidError(
            "The model's finalize answer was not usable.", hint="Try finalizing again.", detail=str(exc)
        ) from exc


def _clean_issues(issues: list[ContinuityIssue], strip_count: int, cast: set[str]) -> list[ContinuityIssue]:
    """Keep issues that point at a real strip and a real cast member; renumber their ids."""
    kept: list[ContinuityIssue] = []
    for issue in issues:
        if issue.strip is None or not 1 <= issue.strip <= strip_count:
            log.warning("dropping continuity issue with bad strip %s", issue.strip)
        elif issue.character_id is not None and issue.character_id not in cast:
            log.warning("dropping continuity issue with unknown character %s", issue.character_id)
        else:
            kept.append(issue.model_copy(update={"id": f"iss_{len(kept) + 1}"}))
    return kept


def review(ctx: Ctx, *, branch: str | None = None, story_id: str | None = None) -> ContinuityReport:
    """Continuity review plus titles and blurb for a branch; changes nothing."""
    with ctx.project.session(readonly=True) as view:
        target = resolve_branch(view, ctx.project_id, branch)
        bible = bible_service.current_bible(view, ctx.project_id)
        if bible is None:
            raise PrerequisiteError("There is no story bible yet.", hint="Create the bible first.")
        strips = _strip_summaries(view, target)
        existing = latest_story(view, target.id)
        sid = story_id or (existing.id if existing is not None else new_id(PREFIXES["story"]))
    if not strips:
        raise PrerequisiteError("This branch has no strips to finalize.", hint="Write at least one strip.")
    audience, user = bible.audience.value, _context(bible, strips)
    found: ContinuityReview = _ask(
        ctx, "continuity", audience, user, ContinuityReview, TEMPERATURE_DETERMINISTIC
    )
    names: TitleSuggestions = _ask(ctx, "titles", audience, user, TitleSuggestions, TEMPERATURE_INTERACTIVE)
    moderation.check_texts(ctx, "suggestion", [*names.titles, names.blurb], audience)
    cast = {c.character_id for c in bible.cast}
    return ContinuityReport(
        story_id=sid,
        checked_at=datetime.now(UTC),
        issues=_clean_issues(found.issues, len(strips), cast),
        titles=names.titles,
        blurb=names.blurb,
    )


def jump_targets(
    session: Session, project_id: str, report: ContinuityReport, branch: str | None = None
) -> dict[str, str]:
    """Map each issue id to the id of the strip to jump to on the branch."""
    target = resolve_branch(session, project_id, branch)
    by_idx = {s.idx: s.id for s in branch_strips(session, target)}
    return {i.id: by_idx[i.strip] for i in report.issues if i.strip in by_idx}


def finalize(
    ctx: Ctx, *, branch: str | None = None, title: str | None = None, force: bool = False
) -> StoryInfo:
    """Review and lock one branch's story.

    Raises:
        PrerequisiteError: Issues are open and `force` is false; `detail` holds the report JSON.
        ImmutableEntityError: The story is already finalized.
    """
    with ctx.project.session(readonly=True) as view:
        target = resolve_branch(view, ctx.project_id, branch)
        current = latest_story(view, target.id)
        if current is not None and current.finalized_at is not None:
            raise ImmutableEntityError("This story is already finalized.", hint="Reopen it to change it.")
        branch_id = target.id
    report = review(ctx, branch=branch)
    if report.issues and not force:
        raise PrerequisiteError(
            f"The continuity check found {len(report.issues)} open issue(s).",
            hint="Fix them, or finalize anyway with force.",
            detail=report.model_dump_json(),
        )
    chosen = (title or report.titles[0]).strip()
    if not chosen:
        raise UsageError("A story title cannot be empty.")
    with ctx.project.session() as work:
        return _lock(ctx, work, branch_id, report, chosen)


def _lock(ctx: Ctx, work: Session, branch_id: str, report: ContinuityReport, title: str) -> StoryInfo:
    current = latest_story(work, branch_id)
    forward: JsonObject = {
        "id": report.story_id,
        "project_id": ctx.project_id,
        "branch_id": branch_id,
        "title": title,
        "blurb": report.blurb,
        "finalized_at": utc_now_iso(),
        "continuity_json": json.loads(report.model_dump_json()),
        "version": current.version if current is not None else 1,
    }
    if current is None:
        undo = Inverse(REMOVED, {"story_id": report.story_id})
    else:
        before = {c: getattr(current, c) for c in STORY_COLS}
        undo = Inverse(FINALIZED, before)
    ctx.events(work).apply(FINALIZED, forward, undo, ctx.actor)
    work.flush()
    row = work.get(Story, report.story_id)
    assert row is not None  # noqa: S101
    return story_info(row)


def reopen(ctx: Ctx, story_id: str) -> StoryInfo:
    """Unlock a finalized story by adding a new version; the finalized row stays as history."""
    with ctx.project.session() as work:
        old = work.get(Story, story_id)
        if old is None or old.project_id != ctx.project_id:
            raise UsageError(f"Story '{story_id}' was not found.")
        latest = latest_story(work, old.branch_id)
        if latest is None or latest.id != old.id or old.finalized_at is None:
            raise UsageError("Only the latest finalized version of a story can be reopened.")
        payload: JsonObject = {
            "id": new_id(PREFIXES["story"]),
            "project_id": old.project_id,
            "branch_id": old.branch_id,
            "title": old.title,
            "blurb": old.blurb,
            "finalized_at": None,
            "continuity_json": None,
            "version": old.version + 1,
        }
        ctx.events(work).apply(REOPENED, payload, Inverse(REMOVED, {"story_id": payload["id"]}), ctx.actor)
        work.flush()
        row = work.get(Story, str(payload["id"]))
        assert row is not None  # noqa: S101
        return story_info(row)
