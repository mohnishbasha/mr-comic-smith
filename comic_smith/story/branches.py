"""Branches: create, switch, rename, delete, list, and the parent-chain strip listing (FR-021).

A branch shares earlier strips with its parent without copying them: it stores `parent_branch_id`
and `fork_strip_id`, and its listing is the parent's listing up to the fork strip plus its own
strips. A strip's `idx` is therefore its 1-based position in any listing that contains it, which
is also how users refer to strips ("strip 3").

Events (all undoable): `branch.created` / `branch.deleted` (each other's inverse family, with
`branch.restored` rebuilding a deleted branch and its own strips), `branch.switched`,
`branch.renamed`. Handlers name their session `txn`; they are the only code here that writes rows.
"""

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from comic_smith.context import Ctx
from comic_smith.db.base import JsonObject
from comic_smith.db.models import Branch, Panel, Story, Strip
from comic_smith.errors import ImmutableEntityError, PrerequisiteError, UsageError
from comic_smith.events import Inverse, register_handler
from comic_smith.ids import PREFIXES, new_id
from comic_smith.models._base import Strict

CREATED = "branch.created"
SWITCHED = "branch.switched"
RENAMED = "branch.renamed"
DELETED = "branch.deleted"
RESTORED = "branch.restored"
MAX_NAME = 40
STRIP_COLS = ("id", "project_id", "branch_id", "idx", "beat_json", "arc_stage", "status", "created_at")


class BranchInfo(Strict):
    """A branch as the API sees it."""

    id: str
    name: str
    parent_branch_id: str | None
    fork_strip_id: str | None
    active: bool
    strip_count: int


def resolve_branch(session: Session, project_id: str, ref: str | None) -> Branch:
    """Find a branch by id or name; `None` means the active branch."""
    stmt = select(Branch).where(Branch.project_id == project_id)
    rows = list(session.scalars(stmt))
    for row in rows:
        if (ref is None and row.active) or ref in {row.id, row.name}:
            return row
    raise UsageError(
        f"There is no branch called '{ref or 'active'}'.",
        hint="List branches with 'branch list' to see the names.",
    )


def branch_strips(session: Session, branch: Branch) -> list[Strip]:
    """Strips visible on a branch in order: the parent's up to the fork point, then its own."""
    own = list(session.scalars(select(Strip).where(Strip.branch_id == branch.id).order_by(Strip.idx)))
    if branch.parent_branch_id is None or branch.fork_strip_id is None:
        return own
    parent = session.get(Branch, branch.parent_branch_id)
    fork = session.get(Strip, branch.fork_strip_id)
    if parent is None or fork is None:
        return own
    return [s for s in branch_strips(session, parent) if s.idx <= fork.idx] + own


def latest_story(session: Session, branch_id: str) -> Story | None:
    """The highest-version story row of a branch."""
    stmt = select(Story).where(Story.branch_id == branch_id).order_by(Story.version.desc()).limit(1)
    return session.scalars(stmt).first()


def is_finalized(session: Session, branch_id: str) -> bool:
    """True when the branch's current story version is locked."""
    story = latest_story(session, branch_id)
    return story is not None and story.finalized_at is not None


def assert_branch_open(session: Session, branch: Branch) -> None:
    """Raise `ImmutableEntityError` when the branch's story is finalized."""
    if is_finalized(session, branch.id):
        raise ImmutableEntityError(
            f"The story on branch '{branch.name}' is finalized and read-only.",
            hint="Reopen the story to edit it.",
        )


def assert_strip_unlocked(session: Session, project_id: str, strip: Strip) -> None:
    """Raise when any finalized branch (the strip's own or one that inherits it) contains the strip."""
    for branch in session.scalars(select(Branch).where(Branch.project_id == project_id)):
        if is_finalized(session, branch.id) and strip.id in {s.id for s in branch_strips(session, branch)}:
            raise ImmutableEntityError(
                f"This strip belongs to the finalized story on branch '{branch.name}'.",
                hint="Reopen the story to edit it.",
            )


def find_strip(session: Session, branch: Branch, ref: str | int) -> Strip:
    """Resolve a 1-based index on `branch` or a strip id."""
    strips = branch_strips(session, branch)
    text = str(ref)
    for strip in strips:
        if (text.isdigit() and strip.idx == int(text)) or strip.id == text:
            return strip
    raise UsageError(f"Strip '{ref}' is not on branch '{branch.name}'.", hint="Use a strip number or id.")


def _info(session: Session, row: Branch) -> BranchInfo:
    return BranchInfo(
        id=row.id,
        name=row.name,
        parent_branch_id=row.parent_branch_id,
        fork_strip_id=row.fork_strip_id,
        active=bool(row.active),
        strip_count=len(branch_strips(session, row)),
    )


def _clean_name(session: Session, project_id: str, name: str, *, except_id: str | None = None) -> str:
    cleaned = name.strip()
    if not cleaned or len(cleaned) > MAX_NAME:
        raise UsageError(f"A branch name needs 1 to {MAX_NAME} characters.")
    for row in session.scalars(select(Branch).where(Branch.project_id == project_id)):
        if row.name == cleaned and row.id != except_id:
            raise UsageError(f"A branch called '{cleaned}' already exists.", hint="Pick another name.")
    return cleaned


def _strip_json(strip: Strip, panels: list[Panel]) -> JsonObject:
    data: JsonObject = {c: getattr(strip, c) for c in (*STRIP_COLS, "approved_at")}
    data["panels"] = [
        {c: getattr(p, c) for c in ("id", "idx", "spec_json", "stale", "lettering_json", "crop_json")}
        for p in panels
    ]
    return data


@register_handler(CREATED)
def _apply_created(txn: Session, payload: JsonObject) -> None:
    txn.add(
        Branch(
            id=payload["id"],
            project_id=payload["project_id"],
            name=payload["name"],
            parent_branch_id=payload["parent_branch_id"],
            fork_strip_id=payload["fork_strip_id"],
            active=0,
        )
    )


@register_handler(DELETED)
def _apply_deleted(txn: Session, payload: JsonObject) -> None:
    branch_id = payload["branch_id"]
    for strip in txn.scalars(select(Strip).where(Strip.branch_id == branch_id)):
        for panel in txn.scalars(select(Panel).where(Panel.strip_id == strip.id)):
            txn.delete(panel)
        txn.flush()
        txn.delete(strip)
    txn.flush()
    row = txn.get(Branch, branch_id)
    if row is not None:
        txn.delete(row)


@register_handler(RESTORED)
def _apply_restored(txn: Session, payload: JsonObject) -> None:
    _apply_created(txn, payload["branch"])
    txn.flush()
    for data in payload["strips"]:
        fields = {k: v for k, v in data.items() if k != "panels"}
        txn.add(Strip(**fields))
        txn.flush()
        for panel in data["panels"]:
            txn.add(Panel(strip_id=data["id"], **panel))


@register_handler(SWITCHED)
def _apply_switched(txn: Session, payload: JsonObject) -> None:
    txn.execute(update(Branch).where(Branch.project_id == payload["project_id"]).values(active=0))
    txn.execute(update(Branch).where(Branch.id == payload["to_id"]).values(active=1))


@register_handler(RENAMED)
def _apply_renamed(txn: Session, payload: JsonObject) -> None:
    row = txn.get(Branch, payload["branch_id"])
    if row is not None:
        row.name = payload["name"]


def _fork_point(session: Session, current: Branch, from_strip: str | int | None) -> Strip:
    """The approved strip on the current branch to fork from (default: the latest approved)."""
    if from_strip is None:
        approved = [s for s in branch_strips(session, current) if s.status == "approved"]
        if not approved:
            raise PrerequisiteError(
                "A new branch forks from an approved strip, and none is approved yet.",
                hint="Approve a strip first.",
            )
        return approved[-1]
    strip = find_strip(session, current, from_strip)
    if strip.status != "approved":
        raise PrerequisiteError(
            f"Strip {strip.idx} is not approved, so it cannot be a fork point.",
            hint="Approve the strip first, or pick an approved one.",
        )
    return strip


def create_branch(
    ctx: Ctx, name: str, *, from_strip: str | int | None = None, switch: bool = False
) -> BranchInfo:
    """Fork the active branch at an approved strip (default: its latest approved strip)."""
    with ctx.project.session() as work:
        current = resolve_branch(work, ctx.project_id, None)
        assert_branch_open(work, current)
        fork = _fork_point(work, current, from_strip)
        payload: JsonObject = {
            "id": new_id(PREFIXES["branch"]),
            "project_id": ctx.project_id,
            "name": _clean_name(work, ctx.project_id, name),
            "parent_branch_id": current.id,
            "fork_strip_id": fork.id,
        }
        log = ctx.events(work)
        log.apply(CREATED, payload, Inverse(DELETED, {"branch_id": payload["id"]}), ctx.actor)
        if switch:
            _switch(ctx, work, str(payload["id"]))
        work.flush()
        return _info(work, resolve_branch(work, ctx.project_id, str(payload["id"])))


def _switch(ctx: Ctx, work: Session, target_id: str) -> None:
    previous = resolve_branch(work, ctx.project_id, None)
    payload: JsonObject = {"project_id": ctx.project_id, "to_id": target_id}
    back: JsonObject = {"project_id": ctx.project_id, "to_id": previous.id}
    ctx.events(work).apply(SWITCHED, payload, Inverse(SWITCHED, back), ctx.actor)


def switch_branch(ctx: Ctx, ref: str) -> BranchInfo:
    """Make a branch the active one."""
    with ctx.project.session() as work:
        target = resolve_branch(work, ctx.project_id, ref)
        if not target.active:
            _switch(ctx, work, target.id)
        work.flush()
        return _info(work, resolve_branch(work, ctx.project_id, target.id))


def rename_branch(ctx: Ctx, ref: str, new_name: str) -> BranchInfo:
    """Rename a branch; names are unique within a project."""
    with ctx.project.session() as work:
        branch = resolve_branch(work, ctx.project_id, ref)
        cleaned = _clean_name(work, ctx.project_id, new_name, except_id=branch.id)
        if cleaned == branch.name:
            return _info(work, branch)
        forward: JsonObject = {"branch_id": branch.id, "name": cleaned}
        back: JsonObject = {"branch_id": branch.id, "name": branch.name}
        ctx.events(work).apply(RENAMED, forward, Inverse(RENAMED, back), ctx.actor)
        work.flush()
        return _info(work, resolve_branch(work, ctx.project_id, branch.id))


def _check_deletable(work: Session, project_id: str, branch: Branch) -> None:
    if branch.active:
        raise UsageError(
            f"Branch '{branch.name}' is the active branch.", hint="Switch to another branch first."
        )
    children = list(work.scalars(select(Branch).where(Branch.parent_branch_id == branch.id)))
    if children:
        names = ", ".join(c.name for c in children)
        raise UsageError(
            f"Branch '{branch.name}' still has branches forked from it: {names}.",
            hint="Delete those branches first so shared strips are never lost.",
        )
    if latest_story(work, branch.id) is not None:
        raise ImmutableEntityError(
            f"Branch '{branch.name}' has a finalized story.", hint="Stories are kept; branch is locked."
        )


def delete_branch(ctx: Ctx, ref: str) -> None:
    """Delete a non-active branch and the strips only it owns; strips shared with others stay."""
    with ctx.project.session() as work:
        branch = resolve_branch(work, ctx.project_id, ref)
        _check_deletable(work, ctx.project_id, branch)
        strips = list(work.scalars(select(Strip).where(Strip.branch_id == branch.id)))
        owned = []
        for strip in strips:
            panels = list(work.scalars(select(Panel).where(Panel.strip_id == strip.id).order_by(Panel.idx)))
            owned.append(_strip_json(strip, panels))
        branch_json: JsonObject = {
            "id": branch.id,
            "project_id": branch.project_id,
            "name": branch.name,
            "parent_branch_id": branch.parent_branch_id,
            "fork_strip_id": branch.fork_strip_id,
        }
        restore = Inverse(RESTORED, {"branch": branch_json, "strips": owned})
        ctx.events(work).apply(DELETED, {"branch_id": branch.id}, restore, ctx.actor)


def list_branches(session: Session, project_id: str) -> list[BranchInfo]:
    """All branches, active first then by name."""
    rows = list(session.scalars(select(Branch).where(Branch.project_id == project_id)))
    rows.sort(key=lambda r: (not r.active, r.name))
    return [_info(session, r) for r in rows]
