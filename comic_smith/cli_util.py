"""Helpers shared by the CLI story commands: JSON output, error mapping, KEY=VALUE parsing."""

import functools
import json
from collections.abc import Callable
from typing import Any

import typer
from pydantic import BaseModel
from rich.console import Console

from comic_smith.errors import ComicSmithError, UsageError

err_console = Console(stderr=True)


def _dump(obj: object) -> Any:
    if isinstance(obj, BaseModel):
        return obj.model_dump(mode="json")
    if isinstance(obj, list):
        return [_dump(o) for o in obj]
    return obj


def emit(obj: object) -> None:
    """Print JSON to stdout (never through rich, so it is never wrapped or colored)."""
    typer.echo(json.dumps(_dump(obj), indent=2, ensure_ascii=False))


def guarded[**P, R](fn: Callable[P, R]) -> Callable[P, R]:
    """Print a `ComicSmithError` (JSON problem object under --json) and exit with its code."""

    @functools.wraps(fn)
    def run(*args: P.args, **kwargs: P.kwargs) -> R:
        try:
            return fn(*args, **kwargs)
        except ComicSmithError as err:
            if kwargs.get("as_json"):
                body = {"code": err.code, "message": err.message, "hint": err.hint}
                typer.echo(json.dumps({"error": body}, indent=2), err=True)
            else:
                err_console.print(f"error [{err.code}]: {err.message}", markup=False)
                if err.hint:
                    err_console.print(f"hint: {err.hint}", markup=False)
            raise typer.Exit(code=err.exit_code) from err

    return run


def parse_assignments(items: list[str]) -> dict[str, Any]:
    """`KEY=VALUE` pairs to a nested dict: dotted keys nest, values parse as JSON else stay text."""
    changes: dict[str, Any] = {}
    for item in items:
        key, sep, raw = item.partition("=")
        if not sep or not key.strip():
            raise UsageError(f"'{item}' is not KEY=VALUE.", hint="Example: --set working_title='Puddle'.")
        try:
            value: Any = json.loads(raw)
        except json.JSONDecodeError:
            value = raw
        node = changes
        *parents, leaf = key.strip().split(".")
        for part in parents:
            node = node.setdefault(part, {})
        node[leaf] = value
    return changes
