"""Unit tests for the event log and undo framework (ADR-010)."""

import ast
import tempfile
import uuid
from collections.abc import Iterator
from pathlib import Path

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from sqlalchemy import text
from sqlalchemy.orm import Session

import comic_smith
from comic_smith.db.base import JsonObject
from comic_smith.db.models import Event, Panel
from comic_smith.db.session import Project
from comic_smith.events import Actor, EventLog, HandlerRegistry, Inverse, UnknownEventTypeError

NOW = "2026-11-02T00:00:00Z"
LETTERING = "panel.lettering_edited"
REGISTRY = HandlerRegistry()


@REGISTRY.register(LETTERING)
def _set_lettering(session: Session, payload: JsonObject) -> None:
    panel = session.get(Panel, payload["panel_id"])
    assert panel is not None
    panel.lettering_json = payload["lettering"]


@REGISTRY.register("test.boom")
def _boom(session: Session, payload: JsonObject) -> None:
    raise RuntimeError("handler failed")


def seed(project: Project, pid: str, panels: int = 1) -> list[str]:
    ids = [f"{pid}_pn{i}" for i in range(panels)]
    with project.session() as s:
        s.execute(
            text(
                "INSERT INTO project (id,name,slug,created_at,updated_at,schema_version) VALUES (:p,'n','n',:t,:t,1)"
            ),
            {"p": pid, "t": NOW},
        )
        s.execute(
            text("INSERT INTO branch (id,project_id,name,active) VALUES (:b,:p,'main',1)"),
            {"b": f"{pid}_b", "p": pid},
        )
        s.execute(
            text(
                "INSERT INTO strip (id,project_id,branch_id,idx,beat_json,arc_stage,created_at) VALUES (:s,:p,:b,1,'{}','setup',:t)"
            ),
            {"s": f"{pid}_s", "p": pid, "b": f"{pid}_b", "t": NOW},
        )
        for i, panel_id in enumerate(ids, start=1):
            s.execute(
                text("INSERT INTO panel (id,strip_id,idx,spec_json) VALUES (:i,:s,:n,'{}')"),
                {"i": panel_id, "s": f"{pid}_s", "n": i},
            )
    return ids


def lettering(project: Project, panel_id: str) -> object:
    with project.session(readonly=True) as s:
        panel = s.get(Panel, panel_id)
        assert panel is not None
        return panel.lettering_json


def edit(log: EventLog, panel_id: str, new: JsonObject | None, old: JsonObject | None, **kw: object):
    return log.apply(
        LETTERING,
        {"panel_id": panel_id, "lettering": new},
        Inverse(LETTERING, {"panel_id": panel_id, "lettering": old}),
        **kw,  # type: ignore[arg-type]
    )


@pytest.fixture
def project(tmp_path: Path) -> Iterator[Project]:
    with Project.open(tmp_path / "p", create=True) as proj:
        yield proj


def test_events_apply_records_actor_and_inverse(project: Project) -> None:
    (pn,) = seed(project, "prj_a")
    with project.session() as s:
        rec = edit(EventLog(s, "prj_a", registry=REGISTRY), pn, {"t": "hi"}, None, actor=Actor.AGENT)
    assert (rec.type, rec.actor, rec.payload["lettering"], rec.undone) == (
        LETTERING,
        Actor.AGENT,
        {"t": "hi"},
        False,
    )
    assert rec.inverse == Inverse(LETTERING, {"panel_id": pn, "lettering": None})
    assert lettering(project, pn) == {"t": "hi"}
    with project.session(readonly=True) as s:
        row = s.get(Event, rec.id)
        assert row is not None
        assert (row.actor, row.project_id, row.undone, row.discarded) == ("agent", "prj_a", 0, 0)
        assert row.inverse_json == {"type": LETTERING, "payload": {"panel_id": pn, "lettering": None}}


def test_events_actor_accepts_strings_and_rejects_unknown(project: Project) -> None:
    (pn,) = seed(project, "prj_a")
    with project.session() as s:
        log = EventLog(s, "prj_a", registry=REGISTRY)
        assert edit(log, pn, None, None, actor="auto").actor is Actor.AUTO
        with pytest.raises(ValueError, match="robot"):
            edit(log, pn, None, None, actor="robot")


def test_events_unknown_type_and_failing_handler_record_nothing(project: Project) -> None:
    seed(project, "prj_a")
    with project.session() as s:
        log = EventLog(s, "prj_a", registry=REGISTRY)
        with pytest.raises(UnknownEventTypeError):
            log.apply("nope.nothing", {}, None)
        with pytest.raises(RuntimeError, match="handler failed"):
            log.apply("test.boom", {}, None)
        assert log.history() == []
    assert "test.boom" in REGISTRY


def test_events_undo_redo_roundtrip_lettering_edit(project: Project) -> None:
    (pn,) = seed(project, "prj_a")
    with project.session() as s:
        log = EventLog(s, "prj_a", registry=REGISTRY)
        assert log.undo() is None
        assert log.redo() is None
        edit(log, pn, {"t": "one"}, None)
        edit(log, pn, {"t": "two"}, {"t": "one"})
        assert log.undo() is not None
        assert lettering_in(s, pn) == {"t": "one"}
        assert log.undo() is not None
        assert lettering_in(s, pn) is None
        assert not log.can_undo()
        assert log.redo() is not None
        assert log.redo() is not None
        assert lettering_in(s, pn) == {"t": "two"}
        assert not log.can_redo()
        types = [e.type for e in log.history()]
        assert types.count("event.undone") == 2
        assert types.count("event.redone") == 2


def lettering_in(session: Session, panel_id: str) -> object:
    panel = session.get(Panel, panel_id)
    assert panel is not None
    return panel.lettering_json


def test_events_redo_cleared_after_new_apply(project: Project) -> None:
    (pn,) = seed(project, "prj_a")
    with project.session() as s:
        log = EventLog(s, "prj_a", registry=REGISTRY)
        edit(log, pn, {"t": "one"}, None)
        edit(log, pn, {"t": "two"}, {"t": "one"})
        log.undo()
        assert log.can_redo()
        edit(log, pn, {"t": "three"}, {"t": "one"})
        assert not log.can_redo()
        assert log.redo() is None
        assert lettering_in(s, pn) == {"t": "three"}
        discarded = [e for e in log.history() if e.discarded]
        assert [e.payload["lettering"] for e in discarded] == [{"t": "two"}]


def test_events_non_undoable_event_does_not_clear_redo_or_enter_undo_stack(project: Project) -> None:
    (pn,) = seed(project, "prj_a")
    reg = HandlerRegistry()
    reg.register(LETTERING)(_set_lettering)
    reg.register("job.finished")(lambda session, payload: None)
    with project.session() as s:
        log = EventLog(s, "prj_a", registry=reg)
        edit(log, pn, {"t": "one"}, None)
        log.undo()
        log.apply("job.finished", {"id": "jb_1"}, None, actor=Actor.AUTO)
        assert log.can_redo()
        assert not log.can_undo()


def test_events_history_survives_restart(tmp_path: Path) -> None:
    path = tmp_path / "p"
    with Project.open(path, create=True) as proj:
        (pn,) = seed(proj, "prj_a")
        with proj.session() as s:
            log = EventLog(s, "prj_a", registry=REGISTRY)
            edit(log, pn, {"t": "one"}, None)
            edit(log, pn, {"t": "two"}, {"t": "one"})
            log.undo()
    with Project.open(path) as proj, proj.session() as s:
        log = EventLog(s, "prj_a", registry=REGISTRY)
        assert log.can_redo()
        assert log.can_undo()
        log.redo()
        assert lettering_in(s, pn) == {"t": "two"}
        log.undo()
        log.undo()
        assert lettering_in(s, pn) is None


def test_events_workspace_scopes_undo_and_redo(project: Project) -> None:
    pa, pb = seed(project, "prj_a", panels=2)
    with project.session() as s:
        mine = EventLog(s, "prj_a", registry=REGISTRY, workspace_id="ws_1")
        theirs = EventLog(s, "prj_a", registry=REGISTRY, workspace_id="ws_2")
        edit(mine, pa, {"t": "m"}, None)
        edit(theirs, pb, {"t": "t"}, None)
        mine.undo()
        assert lettering_in(s, pa) is None
        assert lettering_in(s, pb) == {"t": "t"}
        assert not mine.can_undo()
        assert theirs.can_undo()
        assert not theirs.can_redo()


def test_events_projects_have_separate_stacks(project: Project) -> None:
    (pa,) = seed(project, "prj_a")
    (pb,) = seed(project, "prj_b")
    with project.session() as s:
        edit(EventLog(s, "prj_a", registry=REGISTRY), pa, {"t": "a"}, None)
        other = EventLog(s, "prj_b", registry=REGISTRY)
        assert other.undo() is None
        edit(other, pb, {"t": "b"}, None)
        other.undo()
        assert lettering_in(s, pa) == {"t": "a"}


@settings(max_examples=60, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(
    ops=st.lists(
        st.one_of(
            st.just(("undo", 0)),
            st.just(("redo", 0)),
            st.tuples(st.just("set"), st.integers(0, 2)),
            st.tuples(st.just("clear"), st.integers(0, 2)),
        ),
        max_size=25,
    )
)
def test_events_property_random_apply_undo_redo_restores_state(ops: list[tuple[str, int]]) -> None:
    """Model: two stacks of full snapshots; the DB must match the model after every step."""
    with tempfile.TemporaryDirectory() as tmp, Project.open(Path(tmp) / "p", create=True) as proj:
        pid = f"prj_{uuid.uuid4().hex[:8]}"
        panels = seed(proj, pid, panels=2)
        with proj.session() as s:
            log = EventLog(s, pid, registry=REGISTRY)
            state: dict[str, object] = dict.fromkeys(panels)
            undo_stack: list[dict[str, object]] = []
            redo_stack: list[dict[str, object]] = []
            for n, (op, arg) in enumerate(ops):
                if op == "undo" and undo_stack:
                    redo_stack.append(dict(state))
                    state = undo_stack.pop()
                    assert log.undo() is not None
                elif op == "redo" and redo_stack:
                    undo_stack.append(dict(state))
                    state = redo_stack.pop()
                    assert log.redo() is not None
                elif op in ("set", "clear"):
                    target = panels[arg % 2]
                    new: JsonObject | None = {"n": n} if op == "set" else None
                    undo_stack.append(dict(state))
                    redo_stack.clear()
                    old = state[target]
                    state[target] = new
                    edit(log, target, new, old)  # type: ignore[arg-type]
                else:
                    assert (log.undo() if op == "undo" else log.redo()) is None
                assert {p: lettering_in(s, p) for p in panels} == state
            while undo_stack:
                assert log.undo() is not None
                undo_stack.pop()
            assert {p: lettering_in(s, p) for p in panels} == dict.fromkeys(panels)


ALLOWED_WRITERS = {"events.py"}
WRITE_CALLS = {"add", "add_all", "delete", "merge", "execute", "bulk_save_objects"}
SESSION_NAMES = {"session", "sess", "s", "db"}


def _direct_writes(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return [
        f"{path.name}:{n.lineno}"
        for n in ast.walk(tree)
        if isinstance(n, ast.Call)
        and isinstance(n.func, ast.Attribute)
        and n.func.attr in WRITE_CALLS
        and isinstance(n.func.value, ast.Name)
        and n.func.value.id in SESSION_NAMES
    ]


def test_events_service_mutations_all_go_through_apply() -> None:
    """Only the db layer, the asset store, and the event log may write through a session."""
    root = Path(comic_smith.__file__).parent
    offenders: list[str] = []
    for path in root.rglob("*.py"):
        rel = path.relative_to(root)
        if rel.parts[0] in {"db", "assets"} or rel.name in ALLOWED_WRITERS:
            continue
        offenders += _direct_writes(path)
    assert offenders == [], f"write through apply() instead: {offenders}"


def test_events_write_scanner_detects_direct_session_writes(tmp_path: Path) -> None:
    bad = tmp_path / "svc.py"
    bad.write_text("def f(session):\n    session.add(1)\n    other.add(2)\n", encoding="utf-8")
    assert _direct_writes(bad) == ["svc.py:2"]
