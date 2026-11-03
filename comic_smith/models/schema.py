"""JSON Schema export and the provider-friendly `llm_schema` helper (ADR-007, ARCHITECTURE 5.10)."""

import json
from typing import Any

from pydantic import BaseModel

from comic_smith.models.book import BookManifest, LayoutTemplate, LetteringDoc
from comic_smith.models.cast import Character, StylePreset
from comic_smith.models.panel import ContinuityReport, PanelSpec
from comic_smith.models.story import Beat, Bible, SuggestionSet

JSON_SCHEMA_DIALECT = "https://json-schema.org/draft/2020-12/schema"
ID_BASE = "https://getcomicsmith.com/schemas/"

PUBLISHED: dict[str, tuple[str, type[BaseModel]]] = {
    "bible": ("comic-smith/bible@1", Bible),
    "suggestions": ("comic-smith/suggestions@1", SuggestionSet),
    "panel": ("comic-smith/panel@1", PanelSpec),
    "beat": ("comic-smith/beat@1", Beat),
    "continuity": ("comic-smith/continuity@1", ContinuityReport),
    "character": ("comic-smith/character@1", Character),
    "layout": ("comic-smith/layout@1", LayoutTemplate),
    "book": ("comic-smith/book@1", BookManifest),
    "style": ("comic-smith/style@1", StylePreset),
    "lettering": ("comic-smith/lettering@1", LetteringDoc),
}


def published_schema(name: str) -> dict[str, Any]:
    """Full JSON Schema for one published document, with `$schema` and `$id` set."""
    schema_id, model = PUBLISHED[name]
    schema = model.model_json_schema()
    doc: dict[str, Any] = {"$schema": JSON_SCHEMA_DIALECT, "$id": f"{ID_BASE}{name}.schema.json", **schema}
    doc["description"] = f"{schema_id}: generated from the pydantic models, do not edit."
    return doc


def render_schema(name: str) -> str:
    """Stable text form of a published schema (sorted keys, trailing newline)."""
    return json.dumps(published_schema(name), indent=2, sort_keys=True, ensure_ascii=True) + "\n"


def _inline(node: Any, defs: dict[str, Any], seen: tuple[str, ...]) -> Any:
    """Recursively resolve `$ref`s and strip fields that confuse structured-output providers."""
    if isinstance(node, list):
        return [_inline(n, defs, seen) for n in node]
    if not isinstance(node, dict):
        return node
    if "$ref" in node:
        name = str(node["$ref"]).rsplit("/", 1)[-1]
        if name in seen:
            raise ValueError(f"recursive schema {name!r} cannot be used for structured output")
        return _inline(defs[name], defs, (*seen, name))
    out: dict[str, Any] = {}
    for key, value in node.items():
        if key in {"title", "default", "$defs"}:
            continue
        if key == "const":
            out["enum"] = [value]
        elif key == "properties":
            out[key] = {k: _inline(v, defs, seen) for k, v in value.items() if k != "schema"}
        elif key == "required":
            out[key] = [r for r in value if r != "schema"]
        else:
            out[key] = _inline(value, defs, seen)
    return out


def llm_schema(model: type[BaseModel]) -> dict[str, Any]:
    """JSON Schema for LLM structured output (Ollama `format`, OpenAI `json_schema`).

    Why: providers reject or mishandle `$ref`/`$defs`, `title`, `default`, and `const`, and the model
    should not be asked to echo the fixed `schema` marker (callers rely on its default). This
    inlines definitions, drops those keywords, turns `const` into a one-value `enum`, and removes
    the `schema` property.

    Raises:
        ValueError: The model is recursive.
    """
    raw = model.model_json_schema()
    inlined: dict[str, Any] = _inline(raw, raw.get("$defs", {}), ())
    return inlined
