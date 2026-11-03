"""Read the approved strips of a branch, following the parent chain up to each fork point."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from comic_smith.db.models import Branch, Strip
from comic_smith.errors import UsageError

APPROVED = "approved"


def branch_by_name(session: Session, project_id: str, name: str) -> Branch:
    branch = session.scalars(
        select(Branch).where(Branch.project_id == project_id, Branch.name == name)
    ).first()
    if branch is None:
        raise UsageError(f"There is no branch named '{name}'.", hint="List branches to see what exists.")
    return branch


def approved_strips(session: Session, project_id: str, branch_name: str = "main") -> list[Strip]:
    """Approved strips of the branch in reading order, including ancestors up to each fork."""
    branch = branch_by_name(session, project_id, branch_name)
    chain: list[Strip] = []
    limit_idx: int | None = None
    current: Branch | None = branch
    while current is not None:
        query = select(Strip).where(Strip.branch_id == current.id, Strip.status == APPROVED)
        if limit_idx is not None:
            query = query.where(Strip.idx <= limit_idx)
        chain = list(session.scalars(query.order_by(Strip.idx))) + chain
        fork = session.get(Strip, current.fork_strip_id) if current.fork_strip_id else None
        limit_idx = fork.idx if fork is not None else None
        current = session.get(Branch, current.parent_branch_id) if current.parent_branch_id else None
    return chain
