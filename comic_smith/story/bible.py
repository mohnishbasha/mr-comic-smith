"""Story bible service (S1-T03, FR-009): generate, version, edit, and read the bible.

The bible is versioned: every change adds a row to `bible` and the highest version is current.
`bible.updated` sets one version's JSON (or deletes that version when `json` is null), so its
inverse is "delete the new version" for a normal save and "restore the old JSON" for a rewrite.
"""

import logging
import re
from typing import Any, NamedTuple

from pydantic import Field, ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from comic_smith.context import Ctx
from comic_smith.db.base import JsonObject, utc_now_iso
from comic_smith.db.models import Bible as BibleRow
from comic_smith.db.models import Project as ProjectRow
from comic_smith.errors import PrerequisiteError, ProjectNotFoundError, UsageError
from comic_smith.events import Inverse, register_handler
from comic_smith.ids import PREFIXES, new_id
from comic_smith.models import ARC_STAGES, Arc, ArcTemplate, Audience, Bible, CastEntry, Setting
from comic_smith.models._base import Opt200, Str30, Str60, Str120, Str300, Str2000, Strict
from comic_smith.projects import DEFAULT_STYLE, MAX_STRIPS, MIN_STRIPS, style_id_for
from comic_smith.story._llm import call_model
from comic_smith.story._wire import context_block
from comic_smith.story.moderation import check_texts
from comic_smith.story.prompts import wrap_untrusted

log = logging.getLogger(__name__)

BIBLE_UPDATED = "bible.updated"
KIDS_AUDIENCES = (Audience.KIDS_5_8, Audience.KIDS_9_12)
MAX_NARRATIVE_CHARS = 5000
MAX_CHARACTERS_PER_BEAT = 6


class DraftCast(Strict):
    """A character as the LLM names it, before it has a character id."""

    name: Str60
    role: Str30
    want: Opt200 = ""
    need: Opt200 = ""


class BibleDraft(Strict):
    """What the LLM writes for the bible; the service adds audience, arc, style, and ids."""

    working_title: Str120
    logline: Str300
    premise: Str2000
    tone: list[Str30] = Field(min_length=1, max_length=6)
    setting: Setting
    cast: list[DraftCast] = Field(min_length=1, max_length=12)
    themes: list[Str60] = Field(default_factory=list, max_length=8)


class BibleVersion(NamedTuple):
    version: int
    created_at: str
    bible: Bible


def arc_templates() -> dict[ArcTemplate, tuple[str, ...]]:
    """All five arc templates with their stage lists (gag-a-day has none)."""
    return dict(ARC_STAGES)


def default_arc(audience: Audience | str) -> ArcTemplate:
    """Kids audiences get problem-try-try-succeed; everyone else gets three-act."""
    return (
        ArcTemplate.PROBLEM_TRY_TRY_SUCCEED if Audience(audience) in KIDS_AUDIENCES else ArcTemplate.THREE_ACT
    )


def _check_inputs(narrative: str, audience: str, target_strips: int, arc: str | None) -> tuple[Audience, Arc]:
    text = narrative.strip()
    if not text:
        raise UsageError("Start with a story idea.", hint="Write a sentence or two about what happens.")
    if len(text) > MAX_NARRATIVE_CHARS:
        raise UsageError("Your idea is a bit long. Keep it under 5,000 characters.")
    if not MIN_STRIPS <= target_strips <= MAX_STRIPS:
        raise UsageError(
            f"A story needs {MIN_STRIPS} to {MAX_STRIPS} strips, not {target_strips}.",
            hint="Pick a length in that range.",
        )
    try:
        aud = Audience(audience)
        template = ArcTemplate(arc) if arc else default_arc(aud)
    except ValueError as e:
        raise UsageError(str(e), hint="Use a listed audience and arc template.") from e
    return aud, Arc(template=template, target_strips=target_strips)


def _character_ids(draft: BibleDraft) -> list[CastEntry]:
    seen: set[str] = set()
    cast: list[CastEntry] = []
    for member in draft.cast:
        base = "ch_" + (re.sub(r"[^a-z0-9]+", "_", member.name.lower()).strip("_") or "hero")
        cid, n = base, 1
        while cid in seen:
            n += 1
            cid = f"{base}_{n}"
        seen.add(cid)
        cast.append(CastEntry(character_id=cid, role=member.role, want=member.want, need=member.need))
    return cast


def bible_texts(bible: Bible) -> list[str]:
    """Free-text fields of a bible, for moderation."""
    cast = [t for c in bible.cast for t in (c.want, c.need)]
    return [bible.working_title, bible.logline, bible.premise, bible.setting.world, *bible.themes, *cast]


def _project_style_id(ctx: Ctx) -> str:
    with ctx.project.session(readonly=True) as s:
        value = ctx.metadata(s).get("style_id")
    return str(value) if value else style_id_for(DEFAULT_STYLE)


def generate_bible(
    ctx: Ctx,
    *,
    narrative: str,
    audience: str,
    target_strips: int,
    arc: str | None = None,
    cast_hints: list[CastEntry] | None = None,
) -> Bible:
    """Draft a bible from the seed narrative with the `bible` prompt; the caller saves it.

    Args:
        ctx: Providers and project.
        narrative: Seed story text (1 to 5,000 characters).
        audience: An audience value.
        target_strips: 1 to 40.
        arc: An arc template id; default by audience (see `default_arc`).
        cast_hints: Existing characters to use instead of letting the model invent ids.

    Raises:
        UsageError: Empty narrative, bad audience or arc, or strips out of range.
        OriginalityBlockedError, AudienceBlockedError: The seed or the draft failed moderation.
    """
    aud, arc_model = _check_inputs(narrative, audience, target_strips, arc)
    hints = [h.model_dump(mode="json") for h in cast_hints or []]
    facts = {
        "audience": aud.value,
        "target_strips": target_strips,
        "arc_template": arc_model.template.value,
        "stages": arc_model.stages,
        "cast_hints": hints,
    }
    user = f"{context_block(facts)}\n\n{wrap_untrusted('seed narrative', narrative)}"
    draft = call_model(ctx, "bible", BibleDraft, audience=aud.value, user=user, temperature=0.8)
    bible = Bible(
        working_title=draft.working_title,
        logline=draft.logline,
        premise=draft.premise,
        audience=aud,
        tone=draft.tone,
        setting=draft.setting,
        cast=list(cast_hints) if cast_hints else _character_ids(draft),
        themes=draft.themes,
        arc=arc_model,
        style_id=_project_style_id(ctx),
    )
    check_texts(ctx, "bible", [narrative.strip(), *bible_texts(bible)], aud.value)
    return bible


def current_bible(session: Session, project_id: str) -> Bible | None:
    """Return the highest-version bible for the project, or None before one exists."""
    row = session.scalars(
        select(BibleRow).where(BibleRow.project_id == project_id).order_by(BibleRow.version.desc()).limit(1)
    ).first()
    return Bible.model_validate(row.json) if row is not None else None


def bible_history(session: Session, project_id: str) -> list[BibleVersion]:
    """Every saved version, oldest first."""
    rows = session.scalars(
        select(BibleRow).where(BibleRow.project_id == project_id).order_by(BibleRow.version)
    ).all()
    return [BibleVersion(r.version, r.created_at, Bible.model_validate(r.json)) for r in rows]


@register_handler(BIBLE_UPDATED)
def _apply_bible_updated(txn: Session, payload: JsonObject) -> None:
    """Set the JSON of one bible version, creating it; a null `json` deletes the version."""
    row = txn.scalars(
        select(BibleRow).where(
            BibleRow.project_id == payload["project_id"], BibleRow.version == payload["version"]
        )
    ).first()
    if payload["json"] is None:
        if row is not None:
            txn.delete(row)
    elif row is None:
        txn.add(
            BibleRow(
                id=payload["id"],
                project_id=payload["project_id"],
                version=payload["version"],
                json=payload["json"],
                created_at=payload["created_at"],
            )
        )
    else:
        row.json = payload["json"]


def save_bible(ctx: Ctx, session: Session, bible: Bible, *, actor: str) -> int:
    """Store `bible` as the next version through the event log (undoable); return the version."""
    latest = session.scalars(
        select(BibleRow.version)
        .where(BibleRow.project_id == ctx.project_id)
        .order_by(BibleRow.version.desc())
        .limit(1)
    ).first()
    version = (latest or 0) + 1
    payload: JsonObject = {
        "id": new_id(PREFIXES["bible"]),
        "project_id": ctx.project_id,
        "version": version,
        "json": bible.model_dump(mode="json"),
        "created_at": utc_now_iso(),
    }
    undo: JsonObject = {**payload, "json": None}
    ctx.events(session).apply(BIBLE_UPDATED, payload, Inverse(BIBLE_UPDATED, undo), actor)
    return version


def _merge(base: dict[str, Any], changes: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in changes.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def _strings(value: object) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        return [s for v in value.values() for s in _strings(v)]
    if isinstance(value, list):
        return [s for v in value for s in _strings(v)]
    return []


def edit_bible(ctx: Ctx, changes: dict[str, Any]) -> Bible:
    """Merge `changes` into the current bible and save a new version (undoable).

    Nested objects (`setting`, `arc`) merge key by key; lists and scalars replace. Changing
    `arc.template` without `arc.stages` refills the stages from the template.

    Raises:
        PrerequisiteError: No bible yet.
        UsageError: The result is not a valid bible (for example target_strips out of range).
    """
    with ctx.project.session() as session:
        current = current_bible(session, ctx.project_id)
        if current is None:
            raise PrerequisiteError("There is no story bible yet.", hint="Create the story first.")
        data = _merge(current.model_dump(mode="json"), changes)
        if "template" in changes.get("arc", {}) and "stages" not in changes["arc"]:
            data["arc"]["stages"] = []
        try:
            edited = Bible.model_validate(data)
        except ValidationError as e:
            first = e.errors()[0]
            where = ".".join(str(p) for p in first["loc"])
            raise UsageError(
                f"That change does not fit the story bible ({where}: {first['msg']}).",
                hint="Check the value and try again.",
            ) from e
        check_texts(ctx, "bible", _strings(changes), edited.audience.value)
        save_bible(ctx, session, edited, actor=ctx.actor)
        return edited


def fit_characters(bible: Bible, ids: list[str]) -> list[str]:
    """Keep only cast ids (in order, unique, at most six); fall back to the first cast member."""
    known = {c.character_id for c in bible.cast}
    kept = list(dict.fromkeys(i for i in ids if i in known))[:MAX_CHARACTERS_PER_BEAT]
    return kept or [bible.cast[0].character_id]


def project_audience(ctx: Ctx, session: Session) -> str:
    """The audience stored on the project row (used before a bible exists)."""
    row = session.get(ProjectRow, ctx.project_id)
    if row is None:
        raise ProjectNotFoundError(f"Project {ctx.project_id} is missing from its database.")
    return str(row.audience)
