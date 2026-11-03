"""Environment checks so missing pieces surface before a run fails mid-way (FR-031).

Each check is a small function from Settings to CheckResult, registered in a list. Later sprints
contribute checks for image backends, LLM, vision, GPU, and cloud keys through `default_checks`.
"""

import shutil
import subprocess
import sys
import tempfile
from collections.abc import Callable
from pathlib import Path

from pydantic import BaseModel

from comic_smith.config import Settings

MIN_PYTHON = (3, 12)
MIN_FREE_BYTES = 2 * 1024**3
FONTS_DIR = Path(__file__).resolve().parent / "letter" / "fonts"
REQUIRED_FONT_FAMILIES = ("ComicNeue", "Bangers", "AtkinsonHyperlegible")
PLAYWRIGHT_INSTALL_TIMEOUT_S = 600


class CheckResult(BaseModel):
    name: str
    ok: bool
    required: bool = True
    detail: str = ""
    hint: str | None = None


class Check(BaseModel):
    name: str
    run: Callable[[Settings], CheckResult]


class DoctorReport(BaseModel):
    ok: bool
    results: list[CheckResult]


def check_python(_: Settings) -> CheckResult:
    v = sys.version_info
    ok = (v.major, v.minor) >= MIN_PYTHON
    return CheckResult(
        name="python",
        ok=ok,
        detail=f"{v.major}.{v.minor}.{v.micro}",
        hint=None if ok else "Install Python 3.12 or newer (uv python install 3.12).",
    )


def _existing_parent(path: Path) -> Path:
    for p in [path, *path.parents]:
        if p.exists():
            return p
    return Path.cwd()


def check_data_dir(settings: Settings) -> CheckResult:
    path = settings.resolved(settings.data_dir)
    try:
        path.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=path):
            pass
    except OSError as e:
        return CheckResult(
            name="data_dir",
            ok=False,
            detail=str(e),
            hint=f"Make {path} writable or set COMIC_SMITH_DATA_DIR.",
        )
    return CheckResult(name="data_dir", ok=True, detail=str(path))


def check_disk(settings: Settings) -> CheckResult:
    free = shutil.disk_usage(_existing_parent(settings.resolved(settings.data_dir))).free
    ok = free >= MIN_FREE_BYTES
    return CheckResult(
        name="disk_space",
        ok=ok,
        detail=f"{free / 1024**3:.1f} GiB free",
        hint=None if ok else "Free at least 2 GiB, or run `mr-comic-smith gc <project>`.",
    )


def chromium_path() -> str | None:
    """Path of the Playwright Chromium build, or None when it is not installed."""
    try:
        from playwright.sync_api import sync_playwright  # noqa: PLC0415

        with sync_playwright() as p:
            exe = p.chromium.executable_path
    except Exception:
        return None
    return exe if exe and Path(exe).exists() else None


def check_chromium(_: Settings) -> CheckResult:
    exe = chromium_path()
    if exe is None:
        return CheckResult(
            name="chromium",
            ok=False,
            required=False,
            detail="Playwright Chromium not installed (needed for PNG and PDF exports)",
            hint="Run `mr-comic-smith doctor --fix` or `uv run playwright install chromium`.",
        )
    return CheckResult(name="chromium", ok=True, required=False, detail=exe)


def check_fonts(_: Settings) -> CheckResult:
    present = {p.name for p in FONTS_DIR.glob("*.ttf")} if FONTS_DIR.is_dir() else set()
    missing = [f for f in REQUIRED_FONT_FAMILIES if not any(n.startswith(f) for n in present)]
    if missing:
        return CheckResult(
            name="fonts",
            ok=False,
            required=False,
            detail=f"missing lettering fonts: {', '.join(missing)}",
            hint="Reinstall mr-comic-smith; lettering fonts ship inside the package.",
        )
    return CheckResult(name="fonts", ok=True, required=False, detail=f"{len(present)} font files")


def core_checks() -> list[Check]:
    return [
        Check(name="python", run=check_python),
        Check(name="data_dir", run=check_data_dir),
        Check(name="disk_space", run=check_disk),
        Check(name="chromium", run=check_chromium),
        Check(name="fonts", run=check_fonts),
    ]


def default_checks() -> list[Check]:
    """Core checks plus backend checks; later sprints append vision and GPU checks here."""
    from comic_smith.backends.llm.checks import llm_checks  # noqa: PLC0415 - avoids an import cycle

    return [*core_checks(), *llm_checks()]


def run_checks(settings: Settings, checks: list[Check]) -> DoctorReport:
    """Run every check; an exception inside a check is reported as a failure, never raised."""
    results: list[CheckResult] = []
    for check in checks:
        try:
            results.append(check.run(settings))
        except Exception as e:
            results.append(
                CheckResult(name=check.name, ok=False, detail=f"check crashed: {e}", hint="Report a bug.")
            )
    ok = all(r.ok for r in results if r.required)
    return DoctorReport(ok=ok, results=results)


def fix_chromium() -> bool:
    """Install Playwright Chromium (doctor --fix). Returns True on success."""
    proc = subprocess.run(
        [sys.executable, "-m", "playwright", "install", "chromium"],
        check=False,
        timeout=PLAYWRIGHT_INSTALL_TIMEOUT_S,
    )
    return proc.returncode == 0
