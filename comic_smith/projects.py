"""Project service: create, resolve, list, rename, archive, delete (FR-001, ARCHITECTURE 4.4, 7.2).

A project is a folder `{projects_dir}/{slug}/` with its own database. User-visible mutations go
through the event log: `project.created` (history only, not undoable), `project.renamed` and
`project.archived` (undoable), and `project.settings_changed` (metadata merges, undoable). Handlers
are registered at import time, so any process that imports this module can undo those events.

Why folders keep their slug on rename: the folder is the lock and WAL home of an open database, and
other processes may hold paths to it, so a rename changes the display name only.
"""

import contextlib
import json
import logging
import shutil
import sqlite3
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from comic_smith.config import Settings
from comic_smith.db.base import JsonObject, utc_now_iso
from comic_smith.db.models import Branch, Style
from comic_smith.db.models import Project as ProjectRow
from comic_smith.db.session import DB_NAME, Project
from comic_smith.errors import ProjectError, ProjectNotFoundError, UsageError
from comic_smith.events import Actor, EventLog, Inverse, register_handler
from comic_smith.ids import PREFIXES, new_id
from comic_smith.models import ArcTemplate, Audience, ProjectInfo
from comic_smith.paths import safe_slug

log = logging.getLogger(__name__)

DEFAULT_STYLE = "picture-book-watercolor"
MAIN_BRANCH = "main"
TRASH_DIR = ".trash"
MIN_STRIPS, MAX_STRIPS = 1, 40

CREATED = "project.created"
RENAMED = "project.renamed"
ARCHIVED = "project.archived"
SETTINGS_CHANGED = "project.settings_changed"


def style_id_for(style: str) -> str:
    """Turn a preset slug such as `picture-book-watercolor` into `st_picture_book_watercolor`."""
    return style if style.startswith("st_") else "st_" + style.replace("-", "_")


# Handlers name their session `txn`: they are the one sanctioned place that writes rows directly
# (EventLog.apply runs them), which the "all mutations go through apply" test scanner relies on.
@register_handler(CREATED)
def _apply_created(txn: Session, payload: JsonObject) -> None:
    """Insert the project row and its active `main` branch.

    `style_id` is only linked when that style row exists, because the column is a foreign key and
    built-in styles are seeded by a later story; the requested id stays in `metadata_json`.
    """
    style_id = payload["style_id"] if txn.get(Style, payload["style_id"]) is not None else None
    txn.add(
        ProjectRow(
            id=payload["id"],
            name=payload["name"],
            slug=payload["slug"],
            created_at=payload["created_at"],
            updated_at=payload["created_at"],
            audience=payload["audience"],
            style_id=style_id,
            schema_version=payload["schema_version"],
            metadata_json=payload["metadata"],
        )
    )
    txn.flush()
    txn.add(Branch(id=payload["branch_id"], project_id=payload["id"], name=MAIN_BRANCH, active=1))


def _row(session: Session, project_id: str) -> ProjectRow:
    """Load the project row or raise."""
    row = session.get(ProjectRow, project_id)
    if row is None:
        raise ProjectNotFoundError(f"Project {project_id} is missing from its database.")
    return row


@register_handler(RENAMED)
def _apply_renamed(txn: Session, payload: JsonObject) -> None:
    """Set the display name."""
    row = _row(txn, payload["project_id"])
    row.name = payload["name"]
    row.updated_at = utc_now_iso()


@register_handler(ARCHIVED)
def _apply_archived(txn: Session, payload: JsonObject) -> None:
    """Set or clear the archived flag."""
    row = _row(txn, payload["project_id"])
    row.archived = 1 if payload["archived"] else 0
    row.updated_at = utc_now_iso()


@register_handler(SETTINGS_CHANGED)
def _apply_settings(txn: Session, payload: JsonObject) -> None:
    """Merge `set` into and remove `unset` keys from `metadata_json`."""
    row = _row(txn, payload["project_id"])
    merged = {k: v for k, v in row.metadata_json.items() if k not in payload.get("unset", [])}
    merged.update(payload.get("set", {}))
    row.metadata_json = merged
    row.updated_at = utc_now_iso()


def _info(row: ProjectRow | dict[str, Any], path: Path) -> ProjectInfo:
    """Build the API record from an ORM row or a raw sqlite row dict."""
    if isinstance(row, dict):
        data = row
    else:
        data = {c: getattr(row, c) for c in ("id", "name", "slug", "audience", "style_id", "created_at")}
        data["archived"] = row.archived
        data["metadata_json"] = row.metadata_json
    meta = data["metadata_json"]
    if isinstance(meta, str):
        meta = json.loads(meta)
    return ProjectInfo(
        id=data["id"],
        name=data["name"],
        slug=data["slug"],
        audience=Audience(str(data["audience"])),
        style_id=data["style_id"] or meta.get("style_id"),
        created_at=data["created_at"],
        path=path,
        archived=bool(data["archived"]),
    )


def project_info(project: Project) -> ProjectInfo:
    """Describe an open project (reads its single `project` row)."""
    with project.session(readonly=True) as s:
        row = s.query(ProjectRow).one()
        return _info(row, project.path)


def _validate_new(
    settings: Settings, name: str, audience: str | None, arc: str | None, target_strips: int
) -> tuple[str, Audience, str | None]:
    """Normalise and validate `create_project` inputs (name, audience, arc, strip count)."""
    name = name.strip()
    if not name:
        raise UsageError("A project needs a name.", hint="Pass a short name such as 'Puddle the Duck'.")
    if not MIN_STRIPS <= target_strips <= MAX_STRIPS:
        raise UsageError(f"target_strips must be {MIN_STRIPS} to {MAX_STRIPS}, got {target_strips}.")
    try:
        aud = Audience(audience or settings.default_audience)
        arc_id = ArcTemplate(arc).value if arc else None
    except ValueError as exc:
        raise UsageError(str(exc), hint="Use a listed audience and arc template id.") from exc
    return name, aud, arc_id


def create_project(
    settings: Settings,
    name: str,
    *,
    narrative: str | None = None,
    audience: str | None = None,
    style: str = DEFAULT_STYLE,
    target_strips: int = 8,
    arc: str | None = None,
) -> ProjectInfo:
    """Create `{projects_dir}/{safe_slug(name)}` with its database, `main` branch, and metadata.

    The seed narrative, requested style, `target_strips`, and `arc` live in `metadata_json` until
    the bible is generated from them (S1-T03).

    Args:
        settings: Provides `projects_dir` and `default_audience`.
        name: Display name; its slug names the folder.
        narrative: Seed story text, if any.
        audience: One of the audience values; defaults to `settings.default_audience`.
        style: Style preset slug or `st_` id.
        target_strips: 1 to 40.
        arc: An arc template id, or None to let the bible step choose.

    Raises:
        UsageError: Empty name, or an invalid audience, arc, or strip count.
        ProjectError: A project with the same slug already exists.
    """
    name, aud, arc_id = _validate_new(settings, name, audience, arc, target_strips)
    slug = safe_slug(name)
    path = settings.projects_dir / slug
    if path.exists():
        raise ProjectError(
            f"A project named '{slug}' already exists.", hint="Pick another name or open the existing one."
        )
    payload: JsonObject = {
        "id": new_id(PREFIXES["project"]),
        "branch_id": new_id(PREFIXES["branch"]),
        "name": name,
        "slug": slug,
        "audience": aud.value,
        "style_id": style_id_for(style),
        "created_at": utc_now_iso(),
        "metadata": {
            "narrative": narrative,
            "target_strips": target_strips,
            "arc": arc_id,
            "style": style,
            "style_id": style_id_for(style),
        },
    }
    return _create_on_disk(path, payload)


def _create_on_disk(path: Path, payload: JsonObject) -> ProjectInfo:
    """Open a fresh project folder and record `project.created`; remove the folder on failure."""
    try:
        with Project.open(path, create=True) as project:
            payload["schema_version"] = project.schema_version
            with project.session() as s:
                EventLog(s, payload["id"]).apply(CREATED, payload, None, Actor.USER)
            return project_info(project)
    except BaseException:
        shutil.rmtree(path, ignore_errors=True)
        raise


def _read_rows(db_file: Path) -> list[dict[str, Any]]:
    """Read project rows without taking the project lock or migrating (read-only sqlite)."""
    uri = f"file:{db_file}?mode=ro"
    # sqlite3's own context manager only commits; an unclosed handle blocks moving the folder on Windows.
    with contextlib.closing(sqlite3.connect(uri, uri=True)) as conn:
        conn.row_factory = sqlite3.Row
        return [dict(r) for r in conn.execute("SELECT * FROM project")]


def _scan(settings: Settings) -> list[ProjectInfo]:
    """Describe every project folder under `projects_dir`, skipping unreadable ones."""
    found: list[ProjectInfo] = []
    root = settings.projects_dir
    if not root.is_dir():
        return found
    for folder in sorted(root.iterdir()):
        db_file = folder / DB_NAME
        if not db_file.is_file():
            continue
        try:
            found.extend(_info(r, folder) for r in _read_rows(db_file))
        except sqlite3.Error:
            log.warning("skipping unreadable project at %s", folder)
    return found


def list_projects(settings: Settings, include_archived: bool = False) -> list[ProjectInfo]:
    """Projects under `projects_dir`, newest first; archived ones only when asked."""
    infos = [i for i in _scan(settings) if include_archived or not i.archived]
    return sorted(infos, key=lambda i: i.created_at, reverse=True)


def resolve_project_path(settings: Settings, ref: str) -> Path:
    """Find a project folder from a slug, project id, name, or an explicit folder path.

    Order: an explicit path (absolute, contains `/` or `\\`, or starts with `.`/`~`), the slug folder, a
    `prj_` id, then a case-insensitive name. Archived projects resolve too.

    Raises:
        ProjectNotFoundError: Nothing matches.
        ProjectError: The name matches more than one project.
    """
    if "/" in ref or "\\" in ref or ref.startswith((".", "~")) or Path(ref).is_absolute():
        explicit = Path(ref).expanduser()
        if (explicit / DB_NAME).is_file():
            return explicit
    direct = settings.projects_dir / safe_slug(ref)
    if (direct / DB_NAME).is_file():
        return direct
    infos = _scan(settings)
    for info in infos:
        if info.id == ref:
            return info.path
    named = [i for i in infos if i.name.casefold() == ref.casefold()]
    if len(named) > 1:
        raise ProjectError(f"More than one project is named '{ref}'.", hint="Use the project id instead.")
    if named:
        return named[0].path
    raise ProjectNotFoundError(
        f"No project matches '{ref}'.", hint="Run 'mr-comic-smith projects' to see what exists."
    )


def rename_project(settings: Settings, ref: str, name: str, *, actor: str = "user") -> ProjectInfo:
    """Change the display name (undoable; the folder and slug stay)."""
    name = name.strip()
    if not name:
        raise UsageError("A project needs a name.")
    with Project.open(resolve_project_path(settings, ref)) as project, project.session() as s:
        row = _row_for_open(s)
        inverse = Inverse(RENAMED, {"project_id": row.id, "name": row.name})
        EventLog(s, row.id).apply(RENAMED, {"project_id": row.id, "name": name}, inverse, actor)
        return _info(row, project.path)


def archive_project(
    settings: Settings, ref: str, archived: bool = True, *, actor: str = "user"
) -> ProjectInfo:
    """Archive (hide from the default list) or restore a project (undoable)."""
    with Project.open(resolve_project_path(settings, ref)) as project, project.session() as s:
        row = _row_for_open(s)
        was = bool(row.archived)
        inverse = Inverse(ARCHIVED, {"project_id": row.id, "archived": was})
        EventLog(s, row.id).apply(ARCHIVED, {"project_id": row.id, "archived": archived}, inverse, actor)
        return _info(row, project.path)


def update_metadata(
    session: Session, project_id: str, changes: JsonObject, *, actor: str = "user"
) -> JsonObject:
    """Merge keys into `metadata_json` through the event log (undoable); None values unset a key.

    Returns:
        The new metadata object.
    """
    row = _row(session, project_id)
    old = row.metadata_json
    unset = sorted(k for k, v in changes.items() if v is None)
    sets = {k: v for k, v in changes.items() if v is not None}
    undo_set = {k: old[k] for k in changes if k in old}
    undo_unset = sorted(k for k in changes if k not in old)
    inverse = Inverse(SETTINGS_CHANGED, {"project_id": project_id, "set": undo_set, "unset": undo_unset})
    EventLog(session, project_id).apply(
        SETTINGS_CHANGED, {"project_id": project_id, "set": sets, "unset": unset}, inverse, actor
    )
    return dict(row.metadata_json)


def delete_project(settings: Settings, ref: str) -> Path:
    """Move the project folder to `{data_dir}/.trash/` (never deletes data outright, FR-001).

    The project is opened first, which fails with `ProjectLockedError` if another process is using
    it and checkpoints the WAL so the moved folder is self-contained.

    Returns:
        The new location inside the trash.
    """
    path = resolve_project_path(settings, ref)
    Project.open(path).close()
    trash = settings.resolved(settings.data_dir) / TRASH_DIR
    trash.mkdir(parents=True, exist_ok=True)
    stamp = utc_now_iso().replace(":", "").replace("-", "")
    target = trash / f"{path.name}-{stamp}"
    counter = 1
    while target.exists():
        counter += 1
        target = trash / f"{path.name}-{stamp}-{counter}"
    shutil.move(str(path), str(target))
    return target


def _row_for_open(session: Session) -> ProjectRow:
    """The single project row of an open project database."""
    return session.query(ProjectRow).one()
