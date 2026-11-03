"""Per-call context shared by every service: settings, the open project, and AI providers.

`open_ctx` resolves a project reference, opens it (taking the single-writer lock), and closes it
afterwards. Providers are created lazily through a factory so a missing or half-built backend
package never breaks code paths that do not need an LLM, and unit tests pass fakes explicitly.
"""

import importlib
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from comic_smith.backends.llm.base import EmbeddingsProvider, LLMProvider
from comic_smith.config import Settings
from comic_smith.db.base import JsonObject
from comic_smith.db.models import Project as ProjectRow
from comic_smith.db.session import Project
from comic_smith.errors import BackendUnavailableError
from comic_smith.events import EventLog
from comic_smith.projects import resolve_project_path

LLM_MODULE = "comic_smith.backends.llm"


class ProviderFactory:
    """Builds providers from settings; imports the backends package only when first asked."""

    def llm(self, settings: Settings) -> LLMProvider:
        """Create the configured LLM provider."""
        return self._call("get_llm", settings)  # type: ignore[no-any-return]

    def embeddings(self, settings: Settings) -> EmbeddingsProvider:
        """Create the configured embeddings provider."""
        return self._call("get_embeddings", settings)  # type: ignore[no-any-return]

    @staticmethod
    def _call(name: str, settings: Settings) -> Any:
        """Import `comic_smith.backends.llm` lazily and call a factory function on it."""
        try:
            fn = getattr(importlib.import_module(LLM_MODULE), name)
        except (ImportError, AttributeError) as exc:
            raise BackendUnavailableError(
                f"The story model backend is not available ({name}).",
                hint="Run 'mr-comic-smith doctor' to check the LLM setup.",
                detail=str(exc),
            ) from exc
        return fn(settings)


@dataclass
class Ctx:
    """Everything a story service needs for one operation."""

    settings: Settings
    project: Project
    project_id: str
    llm: LLMProvider | None = None
    embeddings: EmbeddingsProvider | None = None
    actor: str = "user"
    factory: Callable[[], ProviderFactory] = field(default=ProviderFactory, repr=False)

    def events(self, session: Session) -> EventLog:
        """Event log bound to the caller's session (the caller commits)."""
        return EventLog(session, self.project_id)

    def metadata(self, session: Session) -> JsonObject:
        """Copy of the project's `metadata_json`."""
        row = session.get(ProjectRow, self.project_id)
        return dict(row.metadata_json) if row is not None else {}

    def require_llm(self) -> LLMProvider:
        """The LLM provider, created from settings on first use when not supplied."""
        if self.llm is None:
            self.llm = self.factory().llm(self.settings)
        return self.llm

    def require_embeddings(self) -> EmbeddingsProvider:
        """The embeddings provider, created from settings on first use when not supplied."""
        if self.embeddings is None:
            self.embeddings = self.factory().embeddings(self.settings)
        return self.embeddings


@contextmanager
def open_ctx(
    settings: Settings,
    ref: str,
    *,
    llm: LLMProvider | None = None,
    embeddings: EmbeddingsProvider | None = None,
    actor: str = "user",
    factory: Callable[[], ProviderFactory] = ProviderFactory,
) -> Iterator[Ctx]:
    """Resolve and open a project, yield a `Ctx`, and always close the project afterwards.

    Args:
        settings: Runtime settings.
        ref: Slug, name, id, or folder path (see `resolve_project_path`).
        llm: Explicit LLM provider (tests pass a fake); otherwise created lazily.
        embeddings: Explicit embeddings provider; otherwise created lazily.
        actor: `user`, `auto`, or `agent`, recorded on events the service writes.
        factory: Callable returning the provider factory (override in tests).

    Raises:
        ProjectNotFoundError: No project matches `ref`.
        ProjectLockedError: Another process holds the project.
    """
    path = resolve_project_path(settings, ref)
    with Project.open(path) as project:
        with project.session(readonly=True) as view:
            project_id = view.execute(select(ProjectRow.id)).scalar_one()
        yield Ctx(
            settings=settings,
            project=project,
            project_id=project_id,
            llm=llm,
            embeddings=embeddings,
            actor=actor,
            factory=factory,
        )
