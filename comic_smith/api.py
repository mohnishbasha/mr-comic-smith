"""Public Python API: the only surface the CLI, server routes, MCP, and integrations call.

A thin facade over the services. Front doors never import db, backends, or service internals
directly (import-linter contract in pyproject.toml).
"""

from comic_smith import doctor as _doctor
from comic_smith.config import Settings, load_settings
from comic_smith.doctor import DoctorReport

__all__ = ["DoctorReport", "Settings", "doctor", "fix_chromium", "load_settings", "run_studio"]


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
