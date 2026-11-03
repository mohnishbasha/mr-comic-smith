"""Story commands for the CLI: new, bible, suggest, strip, strips, approve, branch, finalize, auto, history.

Registered onto the main app by `cli.py`. Like `cli.py` this layer only parses flags, calls
`comic_smith.api`, prints, and maps errors to exit codes. Every command accepts `--json`, which
prints the pydantic result to stdout and nothing else (progress and errors go to stderr).
"""

from collections.abc import Callable
from enum import StrEnum
from pathlib import Path
from typing import Annotated, Any

import typer
from rich.console import Console
from rich.table import Table

from comic_smith import api
from comic_smith.cli_util import emit, guarded, parse_assignments
from comic_smith.errors import UsageError

JsonFlag = Annotated[bool, typer.Option("--json", help="Machine-readable output.")]
BranchOpt = Annotated[str | None, typer.Option("--branch", help="Branch name (default: the active branch).")]
story_app = typer.Typer()
console = Console()
err_console = Console(stderr=True)
settings_source: Callable[[], api.Settings] = api.load_settings


class Policy(StrEnum):
    """Choices for auto --policy."""

    BALANCED = "balanced"
    STEER = "steer"
    TWIST = "twist"


class BranchAction(StrEnum):
    """Sub-commands of `branch`."""

    CREATE = "create"
    SWITCH = "switch"
    LIST = "list"
    DELETE = "delete"
    RENAME = "rename"


def _bible_lines(bible: api.Bible) -> None:
    console.print(f"[bold]{bible.working_title}[/bold]  ({bible.audience.value}, {bible.arc.template.value})")
    console.print(bible.logline, markup=False)
    console.print(f"Premise: {bible.premise}", markup=False)
    console.print(f"Tone: {', '.join(bible.tone)}   Strips: {bible.arc.target_strips}", markup=False)
    for c in bible.cast:
        console.print(f"  {c.character_id}: {c.role}", markup=False)
    console.print(f"Arc: {' > '.join(bible.arc.stages)}", markup=False)


def _strip_lines(strip: api.StripDetail) -> None:
    console.print(
        f"Strip {strip.idx} [{strip.status}] {strip.beat.get('beat', '')} (stage: {strip.arc_stage})",
        markup=False,
    )
    for p in strip.panels:
        text = "; ".join(d.text for d in p.spec.dialogue) or (p.spec.caption or "")
        console.print(f"  {p.idx}. {p.spec.shot.value}: {p.spec.action} {text}".rstrip(), markup=False)


@story_app.command("new")
@guarded
def new_cmd(
    name: Annotated[str, typer.Argument(help="Project name.")],
    narrative: Annotated[
        str | None, typer.Option("--narrative", help="Seed story, 1 to 5,000 chars.")
    ] = None,
    image: Annotated[list[Path] | None, typer.Option("--image", help="Reference photo (Sprint 2).")] = None,
    style: Annotated[str, typer.Option("--style", help="Style preset.")] = "picture-book-watercolor",
    audience: Annotated[
        str | None, typer.Option("--audience", help="Audience (default from settings).")
    ] = None,
    strips: Annotated[int, typer.Option("--strips", min=1, max=40, help="Target strip count.")] = 8,
    arc: Annotated[str | None, typer.Option("--arc", help="Arc template id.")] = None,
    as_json: JsonFlag = False,
) -> None:
    """Create a project and its story bible from a narrative."""
    if not as_json:
        err_console.print("Writing the story bible...")
    info = api.create_project(
        name,
        narrative=narrative,
        image_paths=image,
        style=style,
        audience=audience,
        target_strips=strips,
        arc=arc,
        settings=settings_source(),
    )
    if as_json:
        emit(info)
        return
    console.print(f"Created project {info.slug} ({info.id}) at {info.path}", markup=False)
    _bible_lines(api.get_bible(info.slug, settings=settings_source()))


@story_app.command("bible")
@guarded
def bible_cmd(
    project: Annotated[str, typer.Argument(help="Project slug, id, or path.")],
    set_: Annotated[
        list[str] | None,
        typer.Option("--set", help="KEY=VALUE change, repeatable; dotted keys nest; VALUE may be JSON."),
    ] = None,
    as_json: JsonFlag = False,
) -> None:
    """Show the story bible, or change it with --set (each save is a new, undoable version)."""
    cfg = settings_source()
    found = (
        api.edit_bible(project, parse_assignments(set_), settings=cfg)
        if set_
        else api.get_bible(project, settings=cfg)
    )
    if as_json:
        emit(found)
    else:
        _bible_lines(found)


@story_app.command("suggest")
@guarded
def suggest_cmd(
    project: Annotated[str, typer.Argument(help="Project slug, id, or path.")],
    branch: BranchOpt = None,
    as_json: JsonFlag = False,
) -> None:
    """Offer three different ideas for the next strip (plus an ending near the end)."""
    found = api.suggest_next(project, branch=branch, settings=settings_source())
    if as_json:
        emit(found)
        return
    table = Table(title=f"Next strip (arc {found.arc_progress:.0%})")
    for col in ("pick", "type", "idea", "what happens"):
        table.add_column(col)
    rows = [(str(i), o) for i, o in enumerate(found.options, 1)]
    if found.end_here is not None:
        rows.append(("end", found.end_here))
    for key, o in rows:
        table.add_row(key, o.intent.value, o.beat, o.description)
    console.print(table)


@story_app.command("strip")
@guarded
def strip_cmd(
    project: Annotated[str, typer.Argument(help="Project slug, id, or path.")],
    pick: Annotated[
        str | None, typer.Option("--pick", help="1, 2, 3, or end (from the latest suggestions).")
    ] = None,
    beat: Annotated[str | None, typer.Option("--beat", help="Your own idea, in plain words.")] = None,
    panels: Annotated[int, typer.Option("--panels", min=1, max=6, help="Panels in the strip.")] = 4,
    branch: BranchOpt = None,
    set_id: Annotated[str | None, typer.Option("--set", help="Suggestion set id (default: latest).")] = None,
    as_json: JsonFlag = False,
) -> None:
    """Write the next strip's script (no images yet) from a pick or your own words."""
    made = api.make_strip(
        project,
        pick=pick,
        beat=beat,
        set_id=set_id,
        panels=panels,
        branch=branch,
        settings=settings_source(),
    )
    if as_json:
        emit(made)
    else:
        _strip_lines(made)


@story_app.command("strips")
@guarded
def strips_cmd(
    project: Annotated[str, typer.Argument(help="Project slug, id, or path.")],
    branch: BranchOpt = None,
    as_json: JsonFlag = False,
) -> None:
    """List a branch's strips."""
    found = api.list_strips(project, branch=branch, settings=settings_source())
    if as_json:
        emit(found)
        return
    table = Table(title="Strips")
    for col in ("#", "status", "stage", "beat", "panels"):
        table.add_column(col)
    for s in found:
        table.add_row(str(s.idx), s.status, s.arc_stage, str(s.beat.get("beat", "")), str(s.panel_count))
    console.print(table)


@story_app.command("approve")
@guarded
def approve_cmd(
    project: Annotated[str, typer.Argument(help="Project slug, id, or path.")],
    strip: Annotated[int, typer.Option("--strip", min=1, help="Strip number.")],
    branch: BranchOpt = None,
    as_json: JsonFlag = False,
) -> None:
    """Approve a strip so the story can move on (it is locked until unapproved)."""
    done = api.approve_strip(project, strip, branch=branch, settings=settings_source())
    if as_json:
        emit(done)
    else:
        console.print(f"Approved strip {done.idx}.", markup=False)


@story_app.command("branch")
@guarded
def branch_cmd(
    project: Annotated[str, typer.Argument(help="Project slug, id, or path.")],
    action: Annotated[BranchAction, typer.Argument(help="create | switch | list | delete | rename")],
    names: Annotated[list[str] | None, typer.Argument(help="NAME (rename: OLD NEW).")] = None,
    from_strip: Annotated[
        int | None, typer.Option("--from-strip", help="create: fork at this strip.")
    ] = None,
    switch: Annotated[bool, typer.Option("--switch", help="create: also switch to the new branch.")] = False,
    yes: Annotated[bool, typer.Option("--yes", help="delete: do not ask.")] = False,
    as_json: JsonFlag = False,
) -> None:
    """Work with alternate story branches."""
    cfg, args = settings_source(), names or []
    need = {BranchAction.LIST: 0, BranchAction.RENAME: 2}.get(action, 1)
    if len(args) != need:
        raise UsageError(f"'branch {action.value}' takes {need} name(s), got {len(args)}.")
    result: Any
    if action is BranchAction.LIST:
        result = api.list_branches(project, settings=cfg)
    elif action is BranchAction.CREATE:
        result = api.create_branch(project, args[0], from_strip=from_strip, switch=switch, settings=cfg)
    elif action is BranchAction.SWITCH:
        result = api.switch_branch(project, args[0], settings=cfg)
    elif action is BranchAction.RENAME:
        result = api.rename_branch(project, args[0], args[1], settings=cfg)
    else:
        if not yes and (as_json or not typer.confirm(f"Delete branch '{args[0]}'?")):
            raise UsageError("Deleting a branch needs --yes.", hint="Add --yes to confirm.")
        api.delete_branch(project, args[0], settings=cfg)
        result = {"deleted": args[0]}
    if as_json:
        emit(result)
    elif action is BranchAction.LIST:
        for b in result:
            console.print(f"{'*' if b.active else ' '} {b.name} ({b.strip_count} strips)", markup=False)
    elif action is BranchAction.DELETE:
        console.print(f"Deleted branch {args[0]}.", markup=False)
    else:
        console.print(f"Branch {result.name} ({result.strip_count} strips).", markup=False)


@story_app.command("finalize")
@guarded
def finalize_cmd(
    project: Annotated[str, typer.Argument(help="Project slug, id, or path.")],
    branch: BranchOpt = None,
    title: Annotated[
        str | None, typer.Option("--title", help="Story title (default: the first suggestion).")
    ] = None,
    force: Annotated[
        bool, typer.Option("--force", "--yes", help="Finalize even with open continuity issues.")
    ] = False,
    as_json: JsonFlag = False,
) -> None:
    """Check continuity and lock the story."""
    story = api.finalize_story(project, branch=branch, title=title, force=force, settings=settings_source())
    if as_json:
        emit(story)
    else:
        console.print(f"Finalized '{story.title}' (version {story.version}).", markup=False)


@story_app.command("auto")
@guarded
def auto_cmd(
    project: Annotated[str, typer.Argument(help="Project slug, id, or path.")],
    policy: Annotated[Policy, typer.Option("--policy", help="How picks lean.")] = Policy.BALANCED,
    until_target: Annotated[
        bool,
        typer.Option("--until-target/--one-step", help="Run to the target length (default) or one strip."),
    ] = True,
    branch: BranchOpt = None,
    as_json: JsonFlag = False,
) -> None:
    """Write and approve strips automatically up to the target length; never finalizes."""

    def progress(strip: api.StripDetail) -> None:
        if not as_json:
            err_console.print(f"strip {strip.idx} approved: {strip.beat.get('beat', '')}", markup=False)

    made = api.run_auto(
        project,
        policy=policy.value,
        until_target=until_target,
        branch=branch,
        on_strip=progress,
        settings=settings_source(),
    )
    if as_json:
        emit(made)
    else:
        console.print(f"Wrote and approved {len(made)} strip(s). Finalize when you are happy.", markup=False)


def _history_step(name: str, call: Callable[..., api.EventInfo | None]) -> None:
    @story_app.command(name)
    @guarded
    def step(
        project: Annotated[str, typer.Argument(help="Project slug, id, or path.")],
        as_json: JsonFlag = False,
    ) -> None:
        event = call(project, settings=settings_source())
        if as_json:
            emit(event)
        elif event is None:
            console.print(f"Nothing to {name}.", markup=False)
        else:
            console.print(f"{name.capitalize()}: {event.type} (event {event.id})", markup=False)

    step.__doc__ = f"{name.capitalize()} the latest change."


_history_step("undo", api.undo)
_history_step("redo", api.redo)


@story_app.command("history")
@guarded
def history_cmd(
    project: Annotated[str, typer.Argument(help="Project slug, id, or path.")],
    limit: Annotated[int, typer.Option("--limit", min=1, help="Most recent events to show.")] = 20,
    as_json: JsonFlag = False,
) -> None:
    """Show recent changes, newest first."""
    events = api.history(project, limit=limit, settings=settings_source())
    if as_json:
        emit(events)
        return
    table = Table(title="History")
    for col in ("id", "when", "actor", "event", "undone"):
        table.add_column(col)
    for e in events:
        table.add_row(str(e.id), e.ts, e.actor, e.type, "yes" if e.undone else "")
    console.print(table)


def register(app: typer.Typer, get_settings: Callable[[], api.Settings]) -> None:
    """Add the story commands to `app`; `get_settings` honors the global --config."""
    global settings_source  # noqa: PLW0603
    settings_source = get_settings
    app.add_typer(story_app)
