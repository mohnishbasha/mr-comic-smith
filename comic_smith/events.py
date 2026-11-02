"""Append-only event log with undo and redo (ADR-010, ARCHITECTURE section 4.4).

Every service mutation goes through `EventLog.apply`: it runs the registered handler for the event
type, then appends an `event` row holding the payload and an inverse. Undo applies the inverse of the
newest undoable event that is not yet undone; redo re-applies the oldest undone event. The cursor is
stored in the table itself (`undone`, `discarded`), so history and the redo stack survive a restart.

Why an inverse payload instead of replaying the log backwards: handlers are plain "set this state"
functions, so an inverse is just another event of a known type carrying the previous state. That
keeps undo independent of how the forward change was computed.
"""

from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from comic_smith.db.base import JsonObject, utc_now_iso
from comic_smith.db.models import Event
from comic_smith.errors import ProjectError

Handler = Callable[[Session, JsonObject], None]

UNDONE_MARKER = "event.undone"
REDONE_MARKER = "event.redone"


class Actor(StrEnum):
    """Who caused an event (ARCHITECTURE 4.2)."""

    USER = "user"
    AUTO = "auto"
    AGENT = "agent"


class UnknownEventTypeError(ProjectError):
    """No handler is registered for an event type."""

    code = "event_type_unknown"
    title = "Unknown change type"
    http_status = 500


@dataclass(frozen=True)
class Inverse:
    """The event that reverses another: a known event type plus its payload."""

    type: str
    payload: JsonObject

    def to_json(self) -> JsonObject:
        """Serialise for `event.inverse_json`."""
        return {"type": self.type, "payload": self.payload}

    @classmethod
    def from_json(cls, data: JsonObject) -> "Inverse":
        """Rebuild from `event.inverse_json`."""
        return cls(type=str(data["type"]), payload=dict(data["payload"]))


@dataclass(frozen=True)
class EventRecord:
    """Read-only view of one `event` row."""

    id: int
    type: str
    actor: Actor
    payload: JsonObject
    inverse: Inverse | None
    undone: bool
    discarded: bool
    ts: str


class HandlerRegistry:
    """Maps event type to the function that applies it to the database."""

    def __init__(self) -> None:
        """Start empty; services register their types at import time."""
        self._handlers: dict[str, Handler] = {}

    def register(self, event_type: str) -> Callable[[Handler], Handler]:
        """Decorator registering `fn(session, payload)` for an event type."""

        def decorate(fn: Handler) -> Handler:
            self._handlers[event_type] = fn
            return fn

        return decorate

    def get(self, event_type: str) -> Handler:
        """Return the handler or raise `UnknownEventTypeError`."""
        try:
            return self._handlers[event_type]
        except KeyError:
            raise UnknownEventTypeError(
                f"No handler is registered for {event_type!r}.",
                hint="Register it with register_handler before applying events of this type.",
            ) from None

    def __contains__(self, event_type: str) -> bool:
        """True when a handler exists."""
        return event_type in self._handlers


DEFAULT_REGISTRY = HandlerRegistry()
register_handler = DEFAULT_REGISTRY.register


def _record(row: Event) -> EventRecord:
    """Convert an ORM row to the public record."""
    inverse = Inverse.from_json(row.inverse_json) if row.inverse_json is not None else None
    return EventRecord(
        id=row.id,
        type=row.type,
        actor=Actor(row.actor),
        payload=row.payload_json,
        inverse=inverse,
        undone=bool(row.undone),
        discarded=bool(row.discarded),
        ts=row.ts,
    )


class EventLog:
    """The event log of one project, bound to a caller-owned session and transaction."""

    def __init__(
        self,
        session: Session,
        project_id: str,
        *,
        registry: HandlerRegistry = DEFAULT_REGISTRY,
        workspace_id: str | None = None,
    ) -> None:
        """Bind to a session; the caller commits (usually via `Project.session()`).

        Args:
            session: Session whose transaction also holds the handler's writes.
            project_id: Project the events belong to.
            registry: Event type to handler map; tests pass their own.
            workspace_id: In classroom mode, restricts undo/redo to this workspace's events.
        """
        self._session = session
        self.project_id = project_id
        self._registry = registry
        self.workspace_id = workspace_id

    def apply(
        self,
        event_type: str,
        payload: JsonObject,
        inverse: Inverse | None,
        actor: Actor | str = Actor.USER,
    ) -> EventRecord:
        """Apply a change through its handler and record it.

        An undoable event (one with an inverse) discards the redo tail, because history has forked.

        Args:
            event_type: Dotted type from ARCHITECTURE 4.4; must have a registered handler.
            payload: The new state or diff, passed to the handler.
            inverse: The event that reverses this one, or None for non-undoable events.
            actor: Who caused it.

        Returns:
            The recorded event.
        """
        handler = self._registry.get(event_type)
        who = Actor(actor)
        with self._session.begin_nested():
            handler(self._session, payload)
            if inverse is not None:
                self._discard_redo_tail()
            row = self._insert(event_type, who, payload, inverse)
        return _record(row)

    def _insert(self, event_type: str, actor: Actor, payload: JsonObject, inverse: Inverse | None) -> Event:
        """Append one row and flush so it has an id."""
        row = Event(
            project_id=self.project_id,
            ts=utc_now_iso(),
            actor=actor.value,
            type=event_type,
            payload_json=payload,
            inverse_json=inverse.to_json() if inverse is not None else None,
            workspace_id=self.workspace_id,
        )
        self._session.add(row)
        self._session.flush()
        return row

    def _scope(self) -> list[Any]:
        """WHERE clauses limiting a query to this project (and workspace in classroom mode)."""
        clauses: list[Any] = [Event.project_id == self.project_id, Event.discarded == 0]
        if self.workspace_id is not None:
            clauses.append(Event.workspace_id == self.workspace_id)
        return clauses

    def _discard_redo_tail(self) -> None:
        """Mark undone events non-redoable; they stay in the log as history."""
        self._session.execute(update(Event).where(*self._scope(), Event.undone == 1).values(discarded=1))

    def _next_undo(self) -> Event | None:
        """Newest undoable event that is still in effect."""
        stmt = (
            select(Event)
            .where(*self._scope(), Event.inverse_json.is_not(None), Event.undone == 0)
            .order_by(Event.id.desc())
            .limit(1)
        )
        return self._session.scalars(stmt).first()

    def _next_redo(self) -> Event | None:
        """Oldest undone event: undo walks newest to oldest, so redo walks back the other way."""
        stmt = select(Event).where(*self._scope(), Event.undone == 1).order_by(Event.id.asc()).limit(1)
        return self._session.scalars(stmt).first()

    def can_undo(self) -> bool:
        """True when `undo` would do something."""
        return self._next_undo() is not None

    def can_redo(self) -> bool:
        """True when `redo` would do something."""
        return self._next_redo() is not None

    def undo(self) -> EventRecord | None:
        """Reverse the latest undoable event and record an `event.undone` marker.

        Returns:
            The event that was undone, or None when there is nothing to undo.
        """
        row = self._next_undo()
        if row is None or row.inverse_json is None:
            return None
        inverse = Inverse.from_json(row.inverse_json)
        with self._session.begin_nested():
            self._registry.get(inverse.type)(self._session, inverse.payload)
            row.undone = 1
            self._insert(UNDONE_MARKER, Actor(row.actor), {"event_id": row.id, "via": inverse.type}, None)
        return _record(row)

    def redo(self) -> EventRecord | None:
        """Re-apply the oldest undone event and record an `event.redone` marker.

        Returns:
            The event that was redone, or None when there is nothing to redo.
        """
        row = self._next_redo()
        if row is None:
            return None
        with self._session.begin_nested():
            self._registry.get(row.type)(self._session, row.payload_json)
            row.undone = 0
            self._insert(REDONE_MARKER, Actor(row.actor), {"event_id": row.id, "via": row.type}, None)
        return _record(row)

    def history(self, limit: int = 100) -> list[EventRecord]:
        """Newest-first events for this project, including undo/redo markers."""
        stmt = select(Event).where(Event.project_id == self.project_id).order_by(Event.id.desc()).limit(limit)
        return [_record(r) for r in self._session.scalars(stmt)]
