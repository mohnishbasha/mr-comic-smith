"""open_ctx: resolution, cleanup, lazy providers."""

from typing import Any

import pytest

from comic_smith.config import Settings
from comic_smith.context import Ctx, ProviderFactory, open_ctx
from comic_smith.db.models import Project as ProjectRow
from comic_smith.errors import BackendUnavailableError, ProjectLockedError, ProjectNotFoundError
from comic_smith.projects import create_project, rename_project


class FakeLLM:
    id = "fake"

    def preflight(self) -> list[Any]:
        return []

    def complete_json(self, *a: Any, **k: Any) -> dict[str, Any]:
        return {}


def test_ctx_opens_project_and_provides_helpers() -> None:
    settings = Settings()
    info = create_project(settings, "Ctx Demo", narrative="hello")
    llm = FakeLLM()
    with open_ctx(settings, "ctx-demo", llm=llm, actor="agent") as ctx:  # type: ignore[arg-type]
        assert isinstance(ctx, Ctx)
        assert ctx.project_id == info.id
        assert ctx.llm is llm
        assert ctx.actor == "agent"
        with ctx.project.session() as s:
            assert ctx.metadata(s)["narrative"] == "hello"
            ctx.events(s).history()
            assert s.get(ProjectRow, info.id) is not None
        with pytest.raises(ProjectLockedError):
            rename_project(settings, "ctx-demo", "x")
    rename_project(settings, "ctx-demo", "Renamed")  # lock released after the block


def test_ctx_unknown_project_raises() -> None:
    with pytest.raises(ProjectNotFoundError), open_ctx(Settings(), "ghost"):
        pass


def test_ctx_providers_are_lazy_and_use_factory() -> None:
    settings = Settings()
    create_project(settings, "Lazy")
    made: list[str] = []

    class Factory(ProviderFactory):
        def llm(self, settings: Settings) -> Any:
            made.append("llm")
            return FakeLLM()

    with open_ctx(settings, "lazy", factory=Factory) as ctx:
        assert made == []
        first = ctx.require_llm()
        assert ctx.require_llm() is first
        assert made == ["llm"]


def test_ctx_missing_backend_is_typed_error(monkeypatch: pytest.MonkeyPatch) -> None:
    from comic_smith import context

    monkeypatch.setattr(context, "LLM_MODULE", "comic_smith.backends.does_not_exist")
    settings = Settings()
    create_project(settings, "Nobackend")
    with open_ctx(settings, "nobackend") as ctx, pytest.raises(BackendUnavailableError):
        ctx.require_embeddings()
