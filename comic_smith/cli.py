"""Command line front door. A thin layer: parse flags, call the API, map errors to exit codes."""

import sys
from enum import StrEnum
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from comic_smith import __version__, api
from comic_smith.errors import ComicSmithError, PreflightError
from comic_smith.logging import configure_logging

LOCALHOST = "127.0.0.1"


class LogFormat(StrEnum):
    """Choices for --log-format (typer vendors click, so click is not imported directly)."""

    PRETTY = "pretty"
    JSON = "json"


app = typer.Typer(
    name="mr-comic-smith",
    help="A local-first comic studio. Every story deserves panels.",
    no_args_is_help=True,
    add_completion=False,
)
console = Console()
err_console = Console(stderr=True)
_state: dict[str, Path | None] = {"config": None}


def _version_callback(value: bool) -> None:
    if value:
        console.print(f"mr-comic-smith {__version__}")
        raise typer.Exit()


def settings(**overrides: object) -> api.Settings:
    """Load settings with the global --config path and command-level flag overrides."""
    return api.load_settings(overrides, config_path=_state["config"])


@app.callback()
def _root(
    version: Annotated[
        bool, typer.Option("--version", callback=_version_callback, is_eager=True, help="Print the version.")
    ] = False,
    debug: Annotated[bool, typer.Option("--debug", help="Show stack traces on errors.")] = False,
    config: Annotated[Path | None, typer.Option("--config", help="Path to a comic-smith.toml.")] = None,
    log_format: Annotated[
        LogFormat | None,
        typer.Option("--log-format", help="Log rendering on stderr (default: COMIC_SMITH_LOG_FORMAT)."),
    ] = None,
) -> None:
    """mr-comic-smith command line."""
    _state["config"] = config
    s = settings(log_format=log_format.value if log_format else None)
    configure_logging(s.log_format, s.log_level)


@app.command("doctor")
def doctor_cmd(
    as_json: Annotated[bool, typer.Option("--json", help="Machine-readable output.")] = False,
    fix: Annotated[bool, typer.Option("--fix", help="Install what can be installed (Chromium).")] = False,
) -> None:
    """Check Python, disk, data directory, Chromium, fonts, and backends."""
    s = settings()
    if fix and not api.fix_chromium():
        err_console.print("warning: Chromium install failed; see the output above")
    report = api.doctor(s)
    if as_json:
        typer.echo(report.model_dump_json(indent=2))
    else:
        table = Table(title="mr-comic-smith doctor")
        for col in ("check", "status", "detail", "hint"):
            table.add_column(col)
        for r in report.results:
            status = "ok" if r.ok else ("FAIL" if r.required else "warn")
            table.add_row(r.name, status, r.detail, r.hint or "")
        console.print(table)
        for w in s.config_warnings:
            err_console.print(f"warning: {w}")
    if not report.ok:
        raise typer.Exit(code=PreflightError.exit_code)


@app.command("studio")
def studio_cmd(
    port: Annotated[int | None, typer.Option("--port", help="Port (default 7351).")] = None,
    host: Annotated[str, typer.Option("--host", help="Bind address.")] = LOCALHOST,
    no_browser: Annotated[bool, typer.Option("--no-browser", help="Do not open a browser.")] = False,
) -> None:
    """Open the Studio in your browser (served on 127.0.0.1 by default)."""
    s = settings(studio_port=port)
    api.run_studio(s, host=host, port=s.studio_port, open_browser=not no_browser)


def _print_error(err: ComicSmithError, debug: bool) -> None:
    if debug:
        err_console.print_exception()
    err_console.print(f"error [{err.code}]: {err.message}", markup=False)
    if err.hint:
        err_console.print(f"hint: {err.hint}", markup=False)


def main() -> None:
    """Console entry point: typer handles usage errors (exit 2); ComicSmithError maps to its code."""
    debug = "--debug" in sys.argv
    try:
        app(prog_name="mr-comic-smith")
    except ComicSmithError as err:
        _print_error(err, debug)
        sys.exit(err.exit_code)
    except KeyboardInterrupt:
        err_console.print("aborted")
        sys.exit(130)


if __name__ == "__main__":  # pragma: no cover
    main()
