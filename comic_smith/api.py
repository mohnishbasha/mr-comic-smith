"""Public Python API: the only surface the CLI, server routes, MCP, and integrations call.

A thin facade over the services. Front doors never import db, backends, or service internals
directly (import-linter contract in pyproject.toml). Every story function takes the project
(slug, name, id, or path) and keyword-only `settings`, `llm`, and `embeddings`; tests inject fakes.
Functions return pydantic models, never ORM rows, and each mutation commits with its event.
"""

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from comic_smith import doctor as _doctor
from comic_smith import projects as _projects
from comic_smith.backends.llm.base import EmbeddingsProvider, LLMProvider
from comic_smith.config import Settings, load_settings
from comic_smith.context import Ctx, open_ctx
from comic_smith.doctor import DoctorReport
from comic_smith.errors import PrerequisiteError, UsageError
from comic_smith.events import EventLog
from comic_smith.models import Bible, EventInfo, PanelSpec, ProjectInfo, StoryInfo, SuggestionSet
from comic_smith.story import auto as _auto
from comic_smith.story import bible as _bible
from comic_smith.story import branches as _branches
from comic_smith.story import finalize as _finalize
from comic_smith.story import make as _make
from comic_smith.story import strips as _strips
from comic_smith.story import suggest as _suggest
from comic_smith.story.branches import BranchInfo
from comic_smith.story.strips import StripDetail, StripInfo

__all__ = [
    "Bible",
    "BranchInfo",
    "DoctorReport",
    "EventInfo",
    "Settings",
    "StripDetail",
    "StripInfo",
    "approve_strip",
    "archive_project",
    "create_branch",
    "create_project",
    "delete_branch",
    "delete_project",
    "doctor",
    "edit_bible",
    "edit_panel",
    "finalize_story",
    "fix_chromium",
    "get_bible",
    "history",
    "list_branches",
    "list_projects",
    "list_strips",
    "load_settings",
    "make_strip",
    "open_project",
    "redo",
    "rename_branch",
    "rename_project",
    "reopen_story",
    "run_auto",
    "run_studio",
    "suggest_next",
    "switch_branch",
    "unapprove_strip",
    "undo",
]


def fix_chromium() -> bool:
    """Install Playwright Chromium for exports (doctor --fix)."""
    return _doctor.fix_chromium()


def doctor(settings: Settings) -> DoctorReport:
    """Run every environment check and return the report."""
    return _doctor.run_checks(settings, _doctor.default_checks())


def run_studio(settings: Settings, *, host: str, port: int, open_browser: bool) -> None:
    """Serve the Studio (bundled static UI plus the REST API) until interrupted."""
    from comic_smith.server.run import run  # noqa: PLC0415

    run(settings, host=host, port=port, open_browser=open_browser)


@contextmanager
def _open(
    project: str,
    settings: Settings | None,
    llm: LLMProvider | None,
    embeddings: EmbeddingsProvider | None,
    actor: str = "user",
) -> Iterator[Ctx]:
    with open_ctx(settings or load_settings(), project, llm=llm, embeddings=embeddings, actor=actor) as ctx:
        yield ctx


def _active(ctx: Ctx, branch: str | None) -> str:
    """The named branch, or the active branch's name when None."""
    with ctx.project.session(readonly=True) as view:
        return _branches.resolve_branch(view, ctx.project_id, branch).name


# --- projects


def create_project(
    name: str,
    *,
    narrative: str | None = None,
    image_paths: list[Path] | None = None,
    style: str = _projects.DEFAULT_STYLE,
    audience: str | None = None,
    target_strips: int = 8,
    arc: str | None = None,
    settings: Settings | None = None,
    llm: LLMProvider | None = None,
    embeddings: EmbeddingsProvider | None = None,
) -> ProjectInfo:
    """Create a project and generate its story bible from the narrative (FR-002).

    Photo-only creation arrives in Sprint 2; until then a narrative is required. If the bible
    cannot be written the new project folder is removed again, so a failed run leaves nothing.

    Raises:
        UsageError: No narrative, an image was given, or a field is invalid.
        ProjectError: A project with that name already exists.
    """
    if image_paths:
        raise UsageError(
            "Starting from photos is not available yet.",
            hint="Use --narrative for now; photos arrive in Sprint 2.",
        )
    if not narrative or not narrative.strip():
        raise UsageError(
            "A narrative is required to start a story.", hint='Pass --narrative "a short story idea".'
        )
    cfg = settings or load_settings()
    info = _projects.create_project(
        cfg, name, narrative=narrative, audience=audience, style=style, target_strips=target_strips, arc=arc
    )
    try:
        with open_ctx(cfg, str(info.path), llm=llm, embeddings=embeddings) as ctx:
            draft = _bible.generate_bible(
                ctx, narrative=narrative, audience=info.audience.value, target_strips=target_strips, arc=arc
            )
            with ctx.project.session() as session:
                _bible.save_bible(ctx, session, draft, actor=ctx.actor)
    except BaseException:
        _remove_folder(info.path)
        raise
    return info


def _remove_folder(path: Path) -> None:
    import shutil  # noqa: PLC0415

    shutil.rmtree(path, ignore_errors=True)


def open_project(project: str, *, settings: Settings | None = None) -> ProjectInfo:
    """Describe a project from a slug, name, id, or folder path."""
    with _open(project, settings, None, None) as ctx:
        return _projects.project_info(ctx.project)


def list_projects(*, include_archived: bool = False, settings: Settings | None = None) -> list[ProjectInfo]:
    """Projects under the data directory, newest first."""
    return _projects.list_projects(settings or load_settings(), include_archived)


def rename_project(project: str, name: str, *, settings: Settings | None = None) -> ProjectInfo:
    """Change a project's display name (undoable)."""
    return _projects.rename_project(settings or load_settings(), project, name)


def archive_project(project: str, archived: bool = True, *, settings: Settings | None = None) -> ProjectInfo:
    """Hide a project from the default list, or restore it (undoable)."""
    return _projects.archive_project(settings or load_settings(), project, archived)


def delete_project(project: str, *, settings: Settings | None = None) -> Path:
    """Move a project folder to the trash; returns its new location."""
    return _projects.delete_project(settings or load_settings(), project)


# --- bible, suggestions, strips


def get_bible(project: str, *, settings: Settings | None = None) -> Bible:
    """The current story bible."""
    with _open(project, settings, None, None) as ctx, ctx.project.session(readonly=True) as view:
        found = _bible.current_bible(view, ctx.project_id)
    if found is None:
        raise PrerequisiteError("There is no story bible yet.", hint="Create the story first.")
    return found


def edit_bible(
    project: str,
    changes: dict[str, Any],
    *,
    settings: Settings | None = None,
    llm: LLMProvider | None = None,
) -> Bible:
    """Merge `changes` into the bible and save a new version (undoable)."""
    with _open(project, settings, llm, None) as ctx:
        return _bible.edit_bible(ctx, changes)


def suggest_next(
    project: str,
    *,
    branch: str | None = None,
    settings: Settings | None = None,
    llm: LLMProvider | None = None,
    embeddings: EmbeddingsProvider | None = None,
) -> SuggestionSet:
    """Three distinct options (plus an end option near the end) for the next strip."""
    with _open(project, settings, llm, embeddings) as ctx:
        return _suggest.suggest_next(ctx, branch=_active(ctx, branch))


def make_strip(
    project: str,
    *,
    set_id: str | None = None,
    pick: int | str | None = None,
    beat: str | None = None,
    panels: int = 4,
    branch: str | None = None,
    settings: Settings | None = None,
    llm: LLMProvider | None = None,
    embeddings: EmbeddingsProvider | None = None,
) -> StripDetail:
    """Write the next strip script from a pick (1, 2, 3, or "end") or free text (`beat`)."""
    with _open(project, settings, llm, embeddings) as ctx:
        return _make.make_strip(
            ctx, pick=pick, beat=beat, set_id=set_id, panels=panels, branch=_active(ctx, branch)
        )


def list_strips(
    project: str, *, branch: str | None = None, settings: Settings | None = None
) -> list[StripInfo]:
    """The strips of a branch in reading order."""
    with _open(project, settings, None, None) as ctx, ctx.project.session(readonly=True) as view:
        return _strips.list_strips(view, ctx.project_id, branch)


def edit_panel(
    project: str, panel_id: str, changes: dict[str, Any], *, settings: Settings | None = None
) -> PanelSpec:
    """Change fields of a panel script (undoable); visual changes mark the panel stale."""
    with _open(project, settings, None, None) as ctx:
        return _strips.edit_panel_spec(ctx, panel_id, changes)


def _strip_detail(ctx: Ctx, info: StripInfo) -> StripDetail:
    with ctx.project.session(readonly=True) as view:
        return _strips.strip_detail(view, info.id)


def approve_strip(
    project: str,
    strip: int | str,
    *,
    branch: str | None = None,
    settings: Settings | None = None,
    llm: LLMProvider | None = None,
) -> StripDetail:
    """Approve a scripted strip; it is locked until unapproved."""
    with _open(project, settings, llm, None) as ctx:
        return _strip_detail(ctx, _strips.approve_strip(ctx, strip, branch=branch))


def unapprove_strip(
    project: str, strip: int | str, *, branch: str | None = None, settings: Settings | None = None
) -> StripDetail:
    """Make an approved strip editable again."""
    with _open(project, settings, None, None) as ctx:
        return _strip_detail(ctx, _strips.unapprove_strip(ctx, strip, branch=branch))


def run_auto(
    project: str,
    *,
    policy: str = "balanced",
    until_target: bool = True,
    branch: str | None = None,
    on_strip: Callable[[StripDetail], None] | None = None,
    settings: Settings | None = None,
    llm: LLMProvider | None = None,
    embeddings: EmbeddingsProvider | None = None,
) -> list[StripDetail]:
    """Auto mode: write and approve strips by policy up to the target length; never finalizes."""
    with _open(project, settings, llm, embeddings, actor="auto") as ctx:
        return _auto.run_auto(ctx, policy=policy, until_target=until_target, branch=branch, on_strip=on_strip)


# --- branches and finalize


def create_branch(
    project: str,
    name: str,
    *,
    from_strip: int | str | None = None,
    switch: bool = False,
    settings: Settings | None = None,
) -> BranchInfo:
    """Fork the active branch at an approved strip (default: its latest approved strip)."""
    with _open(project, settings, None, None) as ctx:
        return _branches.create_branch(ctx, name, from_strip=from_strip, switch=switch)


def switch_branch(project: str, name: str, *, settings: Settings | None = None) -> BranchInfo:
    """Make a branch the active one."""
    with _open(project, settings, None, None) as ctx:
        return _branches.switch_branch(ctx, name)


def rename_branch(project: str, name: str, new_name: str, *, settings: Settings | None = None) -> BranchInfo:
    """Rename a branch."""
    with _open(project, settings, None, None) as ctx:
        return _branches.rename_branch(ctx, name, new_name)


def list_branches(project: str, *, settings: Settings | None = None) -> list[BranchInfo]:
    """All branches, the active one first."""
    with _open(project, settings, None, None) as ctx, ctx.project.session(readonly=True) as view:
        return _branches.list_branches(view, ctx.project_id)


def delete_branch(project: str, name: str, *, settings: Settings | None = None) -> None:
    """Delete a non-active branch that has no finalized story and no child branches."""
    with _open(project, settings, None, None) as ctx:
        _branches.delete_branch(ctx, name)


def finalize_story(
    project: str,
    *,
    branch: str | None = None,
    title: str | None = None,
    force: bool = False,
    settings: Settings | None = None,
    llm: LLMProvider | None = None,
) -> StoryInfo:
    """Run the continuity check and lock the branch's story; `force` finalizes despite open issues."""
    with _open(project, settings, llm, None) as ctx:
        return _finalize.finalize(ctx, branch=branch, title=title, force=force)


def reopen_story(project: str, story_id: str, *, settings: Settings | None = None) -> StoryInfo:
    """Unlock a finalized story as a new version."""
    with _open(project, settings, None, None) as ctx:
        return _finalize.reopen(ctx, story_id)


# --- history


def undo(project: str, *, settings: Settings | None = None) -> EventInfo | None:
    """Reverse the latest undoable change; None when there is nothing to undo."""
    with _open(project, settings, None, None) as ctx, ctx.project.session() as session:
        rec = EventLog(session, ctx.project_id).undo()
    return _info(rec.id, rec.type, rec.actor.value, rec.ts, True) if rec else None


def redo(project: str, *, settings: Settings | None = None) -> EventInfo | None:
    """Re-apply the latest undone change; None when there is nothing to redo."""
    with _open(project, settings, None, None) as ctx, ctx.project.session() as session:
        rec = EventLog(session, ctx.project_id).redo()
    return _info(rec.id, rec.type, rec.actor.value, rec.ts, False) if rec else None


def history(project: str, *, limit: int = 100, settings: Settings | None = None) -> list[EventInfo]:
    """Newest-first events, including undo and redo markers."""
    with _open(project, settings, None, None) as ctx, ctx.project.session(readonly=True) as view:
        records = EventLog(view, ctx.project_id).history(limit)
    return [_info(r.id, r.type, r.actor.value, r.ts, r.undone) for r in records]


def _info(event_id: int, event_type: str, actor: str, ts: str, undone: bool) -> EventInfo:
    return EventInfo(id=event_id, type=event_type, actor=actor, ts=ts, undone=undone)
