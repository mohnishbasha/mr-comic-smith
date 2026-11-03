"""Project service: create, resolve, list, rename (undo), archive, delete to trash (FR-001)."""

import sqlite3
from typing import Any

import pytest

from comic_smith.config import Settings
from comic_smith.db.models import Branch, Event
from comic_smith.db.models import Project as ProjectRow
from comic_smith.db.session import Project
from comic_smith.errors import ProjectError, ProjectNotFoundError, UsageError
from comic_smith.events import EventLog
from comic_smith.projects import (
    archive_project,
    create_project,
    delete_project,
    list_projects,
    rename_project,
    resolve_project_path,
    update_metadata,
)


@pytest.fixture
def settings() -> Settings:
    return Settings()


def test_projects_create_makes_folder_row_branch_and_metadata(settings: Settings) -> None:
    info = create_project(settings, "Puddle the Duck", narrative="A duck.", target_strips=6, arc="three-act")
    assert info.slug == "puddle-the-duck"
    assert info.path == settings.projects_dir / "puddle-the-duck"
    assert info.id.startswith("prj_")
    assert info.audience == "all-ages"
    assert info.style_id == "st_picture_book_watercolor"
    with Project.open(info.path) as project, project.session(readonly=True) as s:
        row = s.get(ProjectRow, info.id)
        assert row is not None
        assert row.metadata_json["narrative"] == "A duck."
        assert row.metadata_json["target_strips"] == 6
        assert row.metadata_json["arc"] == "three-act"
        branches = s.query(Branch).all()
        assert [(b.name, b.active) for b in branches] == [("main", 1)]
        created = s.query(Event).filter_by(type="project.created").one()
        assert created.inverse_json is None


def test_projects_create_uses_default_audience_and_explicit_audience(settings: Settings) -> None:
    assert create_project(settings, "A", audience="teen").audience == "teen"
    s2 = Settings(default_audience="kids-5-8")
    assert create_project(s2, "B").audience == "kids-5-8"


def test_projects_create_duplicate_slug_refused(settings: Settings) -> None:
    create_project(settings, "Puddle")
    with pytest.raises(ProjectError, match="already exists"):
        create_project(settings, "puddle!")


@pytest.mark.parametrize(
    "kwargs", [{"target_strips": 0}, {"target_strips": 41}, {"arc": "epic"}, {"audience": "toddler"}]
)
def test_projects_create_invalid_options_leave_no_folder(
    settings: Settings, kwargs: dict[str, object]
) -> None:
    with pytest.raises(UsageError):
        create_project(settings, "Bad", **kwargs)  # type: ignore[arg-type]
    assert not (settings.projects_dir / "bad").exists()


def test_projects_create_empty_name_refused(settings: Settings) -> None:
    with pytest.raises(UsageError):
        create_project(settings, "   ")


def test_projects_resolve_by_slug_name_id_and_path(settings: Settings) -> None:
    info = create_project(settings, "Puddle the Duck")
    assert resolve_project_path(settings, "puddle-the-duck") == info.path
    assert resolve_project_path(settings, "puddle the duck") == info.path
    assert resolve_project_path(settings, "PUDDLE THE DUCK") == info.path
    assert resolve_project_path(settings, info.id) == info.path
    assert resolve_project_path(settings, str(info.path)) == info.path
    with pytest.raises(ProjectNotFoundError):
        resolve_project_path(settings, "nope")


def test_projects_resolve_ambiguous_name_asks_for_id(settings: Settings) -> None:
    create_project(settings, "One")
    create_project(settings, "Two")
    rename_project(settings, "one", "Same Name")
    rename_project(settings, "two", "Same Name")
    with pytest.raises(ProjectError, match="More than one"):
        resolve_project_path(settings, "Same Name")


def test_projects_list_hides_archived_by_default(settings: Settings) -> None:
    assert list_projects(settings) == []
    create_project(settings, "One")
    create_project(settings, "Two")
    archive_project(settings, "one")
    assert [p.slug for p in list_projects(settings)] == ["two"]
    assert {p.slug for p in list_projects(settings, include_archived=True)} == {"one", "two"}
    assert next(p for p in list_projects(settings, True) if p.slug == "one").archived


def test_projects_rename_changes_name_not_folder_and_undo_restores(settings: Settings) -> None:
    info = create_project(settings, "Old Name")
    renamed = rename_project(settings, "old-name", "New Name")
    assert (renamed.name, renamed.slug, renamed.path) == ("New Name", "old-name", info.path)
    assert resolve_project_path(settings, "new name") == info.path
    with Project.open(info.path) as project:
        with project.session() as s:
            assert EventLog(s, info.id).undo() is not None
        with project.session(readonly=True) as s:
            assert s.get(ProjectRow, info.id).name == "Old Name"  # type: ignore[union-attr]
        with project.session() as s:
            EventLog(s, info.id).redo()
        with project.session(readonly=True) as s:
            assert s.get(ProjectRow, info.id).name == "New Name"  # type: ignore[union-attr]


def test_projects_archive_undo_restores(settings: Settings) -> None:
    info = create_project(settings, "Keep")
    assert archive_project(settings, "keep").archived is True
    with Project.open(info.path) as project, project.session() as s:
        EventLog(s, info.id).undo()
    assert [p.slug for p in list_projects(settings)] == ["keep"]
    assert archive_project(settings, "keep", archived=False).archived is False


def test_projects_update_metadata_merges_and_undoes(settings: Settings) -> None:
    info = create_project(settings, "Meta", narrative="seed")
    with Project.open(info.path) as project:
        with project.session() as s:
            new = update_metadata(s, info.id, {"extra": 1, "narrative": None})
            assert "narrative" not in new
            assert new["extra"] == 1
        with project.session() as s:
            EventLog(s, info.id).undo()
        with project.session(readonly=True) as s:
            meta = s.get(ProjectRow, info.id).metadata_json  # type: ignore[union-attr]
            assert meta["narrative"] == "seed"
            assert "extra" not in meta


def test_projects_scan_closes_its_read_only_connections(
    settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    # An open handle blocks moving the project folder on Windows, so every scan must close.
    create_project(settings, "Scanned")
    opened: list[sqlite3.Connection] = []
    real_connect = sqlite3.connect

    def tracking_connect(*args: Any, **kwargs: Any) -> sqlite3.Connection:
        conn = real_connect(*args, **kwargs)
        opened.append(conn)
        return conn

    monkeypatch.setattr(sqlite3, "connect", tracking_connect)
    assert len(list_projects(settings)) == 1
    assert opened
    for conn in opened:
        with pytest.raises(sqlite3.ProgrammingError):
            conn.execute("SELECT 1")


def test_projects_delete_moves_to_trash(settings: Settings) -> None:
    info = create_project(settings, "Doomed")
    trashed = delete_project(settings, "doomed")
    assert not info.path.exists()
    assert trashed.parent == settings.resolved(settings.data_dir) / ".trash"
    assert (trashed / "project.db").is_file()
    assert list_projects(settings, include_archived=True) == []
    with pytest.raises(ProjectNotFoundError):
        delete_project(settings, "doomed")
    again = create_project(settings, "Doomed")
    assert delete_project(settings, again.id) != trashed
