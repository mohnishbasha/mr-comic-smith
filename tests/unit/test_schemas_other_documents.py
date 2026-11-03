"""Models for character, style, layout, lettering, book, and API records (S1-T02)."""

import json
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from comic_smith.models import (
    BookManifest,
    Character,
    LayoutTemplate,
    LetteringDoc,
    ProjectInfo,
    StylePreset,
)


def load(fixtures_dir: Path, name: str) -> dict[str, Any]:
    data: dict[str, Any] = json.loads((fixtures_dir / "documents" / f"{name}.json").read_text())
    return data


@pytest.mark.parametrize(
    ("name", "model"),
    [
        ("character", Character),
        ("style", StylePreset),
        ("layout", LayoutTemplate),
        ("lettering", LetteringDoc),
        ("book", BookManifest),
    ],
)
def test_schemas_secondary_documents_roundtrip(fixtures_dir: Path, name: str, model: Any) -> None:
    parsed = model.model_validate(load(fixtures_dir, name))
    assert model.model_validate_json(parsed.model_dump_json()) == parsed


def test_schemas_character_id_prefix_and_dna_length(fixtures_dir: Path) -> None:
    raw = load(fixtures_dir, "character")
    raw["id"] = "puddle"
    with pytest.raises(ValidationError):
        Character.model_validate(raw)
    raw = load(fixtures_dir, "character")
    raw["visual_dna"] = "too short"
    with pytest.raises(ValidationError):
        Character.model_validate(raw)


def test_schemas_layout_reading_order_must_be_permutation(fixtures_dir: Path) -> None:
    raw = load(fixtures_dir, "layout")
    raw["reading_order"] = ["s1", "s2"]
    with pytest.raises(ValidationError, match="permutation"):
        LayoutTemplate.model_validate(raw)


def test_schemas_lettering_balloon_must_stay_inside_panel(fixtures_dir: Path) -> None:
    raw = load(fixtures_dir, "lettering")
    raw["balloons"][0]["x"] = 0.9
    with pytest.raises(ValidationError, match="inside the panel"):
        LetteringDoc.model_validate(raw)


def test_schemas_book_pages_consecutive(fixtures_dir: Path) -> None:
    raw = load(fixtures_dir, "book")
    raw["pages"][1]["idx"] = 5
    with pytest.raises(ValidationError):
        BookManifest.model_validate(raw)


def test_schemas_style_bad_hex_rejected(fixtures_dir: Path) -> None:
    raw = load(fixtures_dir, "style")
    raw["palette_hints"] = ["red"]
    with pytest.raises(ValidationError):
        StylePreset.model_validate(raw)


def test_schemas_project_info_fields(tmp_path: Path) -> None:
    info = ProjectInfo(
        id="prj_1", name="N", slug="n", audience="kids-5-8", style_id=None, created_at="t", path=tmp_path
    )
    assert info.archived is False
    assert info.audience == "kids-5-8"
