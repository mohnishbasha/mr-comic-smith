"""Strips and panels: create from a beat, edit specs, approve and unapprove, list (FR-013, 014, 020).

Events (all undoable): `strip.created` (inverse `strip.removed`), `panel.spec_edited` (carries the
new `stale` flag, so one event replaces the doc's `panel.marked_stale`), `strip.approved` and
`strip.unapproved` (each other's inverse). Approval runs the arc update in the same transaction.
"""

import json
from collections.abc import Mapping
from typing import Any

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from comic_smith.backends.llm.base import TEMPERATURE_INTERACTIVE
from comic_smith.context import Ctx
from comic_smith.db.base import JsonObject, utc_now_iso
from comic_smith.db.models import Panel, Strip, SuggestionSet
from comic_smith.errors import ImmutableEntityError, PrerequisiteError, SchemaValidationError, UsageError
from comic_smith.events import Inverse, register_handler
from comic_smith.ids import PREFIXES, new_id
from comic_smith.models import Beat, PanelSpec
from comic_smith.models._base import Strict
from comic_smith.story import arc, moderation, writer
from comic_smith.story import bible as bible_service
from comic_smith.story.branches import (
    assert_branch_open,
    assert_strip_unlocked,
    branch_strips,
    find_strip,
    resolve_branch,
)

CREATED = "strip.created"
REMOVED = "strip.removed"
SPEC_EDITED = "panel.spec_edited"
APPROVED = "strip.approved"
UNAPPROVED = "strip.unapproved"
TEXT_ONLY_FIELDS = frozenset({"dialogue", "caption", "sfx"})
LOCKED_FIELDS = frozenset({"idx", "schema"})


class PanelInfo(Strict):
    """A panel row with its validated spec."""

    id: str
    idx: int
    stale: bool
    spec: PanelSpec


class StripInfo(Strict):
    """A strip as listings show it."""

    id: str
    branch_id: str
    idx: int
    status: str
    arc_stage: str
    beat: dict[str, Any]
    approved_at: str | None
    panel_count: int


class StripDetail(StripInfo):
    """A strip with its panels (what the API returns after writing or approving one)."""

    panels: list[PanelInfo]


@register_handler(CREATED)
def _apply_created(txn: Session, payload: JsonObject) -> None:
    txn.add(Strip(**payload["strip"]))
    txn.flush()
    for panel in payload["panels"]:
        txn.add(
            Panel(strip_id=payload["strip"]["id"], idx=panel["idx"], id=panel["id"], spec_json=panel["spec"])
        )
    link = payload.get("suggestion_set_id")
    chosen = txn.get(SuggestionSet, link) if link else None
    if chosen is not None and payload.get("pick") is not None:
        chosen.chosen_idx = payload["pick"]


@register_handler(REMOVED)
def _apply_removed(txn: Session, payload: JsonObject) -> None:
    for panel in txn.scalars(select(Panel).where(Panel.strip_id == payload["strip_id"])):
        txn.delete(panel)
    txn.flush()
    strip = txn.get(Strip, payload["strip_id"])
    if strip is not None:
        txn.delete(strip)
    link = payload.get("suggestion_set_id")
    chosen = txn.get(SuggestionSet, link) if link else None
    if chosen is not None:
        chosen.chosen_idx = payload.get("previous_pick")


@register_handler(SPEC_EDITED)
def _apply_spec_edited(txn: Session, payload: JsonObject) -> None:
    panel = txn.get(Panel, payload["panel_id"])
    if panel is not None:
        panel.spec_json = payload["spec"]
        panel.stale = 1 if payload["stale"] else 0


@register_handler(APPROVED)
def _apply_approved(txn: Session, payload: JsonObject) -> None:
    strip = txn.get(Strip, payload["strip_id"])
    if strip is not None:
        strip.status = "approved"
        strip.approved_at = payload["approved_at"]


@register_handler(UNAPPROVED)
def _apply_unapproved(txn: Session, payload: JsonObject) -> None:
    strip = txn.get(Strip, payload["strip_id"])
    if strip is not None:
        strip.status = payload["status"]
        strip.approved_at = None


def _dump(spec: PanelSpec) -> JsonObject:
    return json.loads(spec.model_dump_json())  # type: ignore[no-any-return]


def create_strip(
    ctx: Ctx,
    beat: Beat,
    *,
    panels: int = writer.DEFAULT_PANELS,
    branch: str = "main",
    suggestion_set_id: str | None = None,
    pick: int | None = None,
    temperature: float = TEMPERATURE_INTERACTIVE,
) -> str:
    """Write a script for the beat and store it as the branch's next strip (status `scripted`).

    The model call happens before the write transaction opens, so a failure leaves no rows.

    Returns:
        The new strip id.
    """
    script = writer.write_strip(ctx, beat, panels=panels, branch=branch, temperature=temperature)
    with ctx.project.session() as work:
        target = resolve_branch(work, ctx.project_id, branch)
        assert_branch_open(work, target)
        row: JsonObject = {
            "id": new_id(PREFIXES["strip"]),
            "project_id": ctx.project_id,
            "branch_id": target.id,
            "idx": len(branch_strips(work, target)) + 1,
            "beat_json": json.loads(beat.model_dump_json()),
            "arc_stage": beat.arc_stage,
            "status": "scripted",
            "created_at": utc_now_iso(),
        }
        specs = [{"id": new_id(PREFIXES["panel"]), "idx": p.idx, "spec": _dump(p)} for p in script.panels]
        link = work.get(SuggestionSet, suggestion_set_id) if suggestion_set_id else None
        payload: JsonObject = {
            "strip": row,
            "panels": specs,
            "suggestion_set_id": suggestion_set_id,
            "pick": pick,
        }
        undo: JsonObject = {
            "strip_id": row["id"],
            "suggestion_set_id": suggestion_set_id,
            "previous_pick": link.chosen_idx if link is not None else None,
        }
        ctx.events(work).apply(CREATED, payload, Inverse(REMOVED, undo), ctx.actor)
        return str(row["id"])


def resolve_strip(session: Session, project_id: str, ref: str | int, branch: str | None = None) -> Strip:
    """Find a strip by 1-based index on a branch (default: active) or by id."""
    target = resolve_branch(session, project_id, branch)
    try:
        return find_strip(session, target, ref)
    except UsageError:
        other = session.get(Strip, str(ref))
        if other is not None and other.project_id == project_id:
            return other
        raise


def _cast_ids(session: Session, project_id: str) -> set[str] | None:
    bible = bible_service.current_bible(session, project_id)
    return None if bible is None else {c.character_id for c in bible.cast}


def _merge_spec(current: JsonObject, changes: Mapping[str, Any]) -> PanelSpec:
    clash = LOCKED_FIELDS & set(changes)
    if clash:
        raise UsageError(f"The field '{sorted(clash)[0]}' cannot be edited.")
    try:
        return PanelSpec.model_validate({**current, **changes})
    except ValidationError as exc:
        first = exc.errors()[0]
        raise SchemaValidationError(
            f"That edit is not a valid panel: {first['loc']}: {first['msg']}.",
            hint="Check the field values against the panel format.",
            detail=str(exc),
        ) from exc


def edit_panel_spec(ctx: Ctx, panel_id: str, changes: Mapping[str, Any]) -> PanelSpec:
    """Apply field changes to a panel spec (FR-014).

    Visual changes mark the panel stale; changes to dialogue, caption, or sfx only do not.

    Raises:
        ImmutableEntityError: The strip is approved or belongs to a finalized story.
        SchemaValidationError: The edited spec is invalid or names a character outside the cast.
    """
    with ctx.project.session() as work:
        panel = work.get(Panel, panel_id)
        strip = work.get(Strip, panel.strip_id) if panel is not None else None
        if panel is None or strip is None:
            raise UsageError(f"Panel '{panel_id}' was not found.")
        _assert_editable(work, ctx.project_id, strip)
        new = _merge_spec(panel.spec_json, changes)
        cast = _cast_ids(work, ctx.project_id)
        if cast is not None:
            found = writer.panel_violations(new, cast, writer.limits_for("all-ages"))
            found = [f for f in found if "not in the cast" in f]
            if found:
                raise SchemaValidationError(
                    f"That edit breaks the cast: {found[0]}.", detail="; ".join(found)
                )
        texts = _changed_texts(changes, new)
        if texts:
            bible = bible_service.current_bible(work, ctx.project_id)
            moderation.check_texts(ctx, "script", texts, bible.audience.value if bible else "all-ages")
        visual = bool(set(changes) - TEXT_ONLY_FIELDS) and _dump(new) != panel.spec_json
        forward: JsonObject = {"panel_id": panel.id, "spec": _dump(new), "stale": bool(panel.stale) or visual}
        back: JsonObject = {"panel_id": panel.id, "spec": panel.spec_json, "stale": bool(panel.stale)}
        ctx.events(work).apply(SPEC_EDITED, forward, Inverse(SPEC_EDITED, back), ctx.actor)
        return new


def _changed_texts(changes: Mapping[str, Any], spec: PanelSpec) -> list[str]:
    out: list[str] = []
    if "dialogue" in changes:
        out += [d.text for d in spec.dialogue]
    if "caption" in changes and spec.caption:
        out.append(spec.caption)
    if "sfx" in changes:
        out += [s.text for s in spec.sfx]
    return out


def _assert_editable(session: Session, project_id: str, strip: Strip) -> None:
    if strip.status == "approved":
        raise ImmutableEntityError(
            f"Strip {strip.idx} is approved and cannot be edited.", hint="Unapprove the strip first."
        )
    assert_strip_unlocked(session, project_id, strip)


def approve_strip(
    ctx: Ctx, strip_ref: str | int, *, branch: str | None = None, require_lettered: bool = False
) -> StripInfo:
    """Approve a strip; it is immutable until `unapprove_strip`.

    In Sprint 1 a scripted strip can be approved. With `require_lettered` (the default from Sprint 3)
    the strip must be rendered and lettered first. The arc/bible update runs in this transaction.
    """
    with ctx.project.session() as work:
        strip = resolve_strip(work, ctx.project_id, strip_ref, branch)
        assert_strip_unlocked(work, ctx.project_id, strip)
        if strip.status == "approved":
            return _strip_info(work, strip)
        if require_lettered and strip.status != "lettered":
            raise PrerequisiteError(
                f"Strip {strip.idx} is not lettered yet (status: {strip.status}).",
                hint="Render and letter every panel, then approve.",
            )
        stamp = utc_now_iso()
        forward: JsonObject = {"strip_id": strip.id, "approved_at": stamp}
        back: JsonObject = {"strip_id": strip.id, "status": strip.status}
        ctx.events(work).apply(APPROVED, forward, Inverse(UNAPPROVED, back), ctx.actor)
        work.refresh(strip)
        arc.apply_strip_approval(ctx, work, strip)
        return _strip_info(work, strip)


def unapprove_strip(ctx: Ctx, strip_ref: str | int, *, branch: str | None = None) -> StripInfo:
    """Make an approved strip editable again (status returns to `scripted`)."""
    with ctx.project.session() as work:
        strip = resolve_strip(work, ctx.project_id, strip_ref, branch)
        assert_strip_unlocked(work, ctx.project_id, strip)
        if strip.status != "approved":
            raise UsageError(f"Strip {strip.idx} is not approved.")
        forward: JsonObject = {"strip_id": strip.id, "status": "scripted"}
        back: JsonObject = {"strip_id": strip.id, "approved_at": strip.approved_at}
        ctx.events(work).apply(UNAPPROVED, forward, Inverse(APPROVED, back), ctx.actor)
        work.refresh(strip)
        return _strip_info(work, strip)


def _strip_info(session: Session, strip: Strip) -> StripInfo:
    count = len(list(session.scalars(select(Panel.id).where(Panel.strip_id == strip.id))))
    return StripInfo(
        id=strip.id,
        branch_id=strip.branch_id,
        idx=strip.idx,
        status=strip.status,
        arc_stage=strip.arc_stage,
        beat=strip.beat_json,
        approved_at=strip.approved_at,
        panel_count=count,
    )


def list_strips(session: Session, project_id: str, branch: str | None = None) -> list[StripInfo]:
    """Strips of a branch in order, including those inherited from parents up to the fork (FR-021)."""
    target = resolve_branch(session, project_id, branch)
    return [_strip_info(session, s) for s in branch_strips(session, target)]


def list_panels(session: Session, strip_id: str) -> list[PanelInfo]:
    """Panels of a strip in order, with validated specs."""
    rows = session.scalars(select(Panel).where(Panel.strip_id == strip_id).order_by(Panel.idx))
    return [
        PanelInfo(id=p.id, idx=p.idx, stale=bool(p.stale), spec=PanelSpec.model_validate(p.spec_json))
        for p in rows
    ]


def strip_detail(session: Session, strip_id: str) -> StripDetail:
    """One strip by id with its panels."""
    strip = session.get(Strip, strip_id)
    if strip is None:
        raise UsageError(f"Strip '{strip_id}' was not found.")
    info = _strip_info(session, strip)
    return StripDetail(**info.model_dump(), panels=list_panels(session, strip.id))
