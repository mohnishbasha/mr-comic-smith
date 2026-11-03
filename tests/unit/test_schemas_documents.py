"""Schema and model tests for the story documents (S1-T02)."""

import importlib.util
import json
from pathlib import Path
from typing import Any

import jsonschema
import pytest
from pydantic import BaseModel, ValidationError

from comic_smith.models import (
    PUBLISHED,
    ArcTemplate,
    Beat,
    Bible,
    ContinuityReport,
    IssueKind,
    ModerationVerdict,
    PanelSpec,
    StripScript,
    SuggestionSet,
    llm_schema,
    published_schema,
)

FIVE = {
    "bible": Bible,
    "suggestions": SuggestionSet,
    "panel": PanelSpec,
    "beat": Beat,
    "continuity": ContinuityReport,
}


def load(fixtures_dir: Path, name: str) -> dict[str, Any]:
    data: dict[str, Any] = json.loads((fixtures_dir / "documents" / f"{name}.json").read_text())
    return data


def _drop_none(node: Any) -> Any:
    if isinstance(node, dict):
        return {k: _drop_none(v) for k, v in node.items() if v is not None}
    if isinstance(node, list):
        return [_drop_none(v) for v in node]
    return node


def test_schemas_models_roundtrip_all_five_documents(fixtures_dir: Path) -> None:
    for name, model in FIVE.items():
        raw = load(fixtures_dir, name)
        parsed = model.model_validate(raw)
        dumped = json.loads(parsed.model_dump_json())
        assert dumped["schema"] == raw["schema"]
        assert model.model_validate(dumped) == parsed
        assert _drop_none(dumped) == _drop_none(raw), name


def test_schemas_export_json_schemas_are_current(repo_root: Path) -> None:
    spec = importlib.util.spec_from_file_location(
        "export_schemas", repo_root / "scripts" / "export-schemas.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.main(["--check"]) == 0
    assert {p.name for p in (repo_root / "schemas").glob("*.schema.json")} == {
        f"{n}.schema.json" for n in PUBLISHED
    }


def test_schemas_fixture_documents_validate(fixtures_dir: Path) -> None:
    for name, (schema_id, model) in PUBLISHED.items():
        raw = load(fixtures_dir, name)
        assert raw["schema"] == schema_id
        model.model_validate(raw)
        jsonschema.validate(raw, published_schema(name))


def test_schemas_panel_spec_invalid_shot_rejected(fixtures_dir: Path) -> None:
    raw = load(fixtures_dir, "panel")
    raw["shot"] = "dolly-zoom"
    with pytest.raises(ValidationError):
        PanelSpec.model_validate(raw)
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(raw, published_schema("panel"))


def test_schemas_beat_requires_arc_stage(fixtures_dir: Path) -> None:
    raw = load(fixtures_dir, "beat")
    del raw["arc_stage"]
    with pytest.raises(ValidationError, match="arc_stage"):
        Beat.model_validate(raw)


def test_schemas_continuity_report_issue_kinds_enum(fixtures_dir: Path) -> None:
    assert {k.value for k in IssueKind} == {
        "unresolved_thread",
        "vanished_character",
        "inconsistent_prop",
        "tone_break",
    }
    raw = load(fixtures_dir, "continuity")
    raw["issues"][0]["kind"] = "plot_hole"
    with pytest.raises(ValidationError):
        ContinuityReport.model_validate(raw)


def test_schemas_schema_field_has_default_and_is_fixed(fixtures_dir: Path) -> None:
    raw = load(fixtures_dir, "beat")
    del raw["schema"]
    assert Beat.model_validate(raw).schema_id == "comic-smith/beat@1"
    raw["schema"] = "comic-smith/beat@2"
    with pytest.raises(ValidationError):
        Beat.model_validate(raw)


def test_schemas_suggestions_require_three_ordered_options(fixtures_dir: Path) -> None:
    raw = load(fixtures_dir, "suggestions")
    raw["options"].reverse()
    with pytest.raises(ValidationError, match="continue, twist, steer"):
        SuggestionSet.model_validate(raw)
    raw = load(fixtures_dir, "suggestions")
    raw["options"].pop()
    with pytest.raises(ValidationError):
        SuggestionSet.model_validate(raw)


def test_schemas_bible_arc_stages_filled_and_checked(fixtures_dir: Path) -> None:
    raw = load(fixtures_dir, "bible")
    del raw["arc"]["stages"]
    assert len(Bible.model_validate(raw).arc.stages) == 7
    raw["arc"]["stages"] = ["only"]
    with pytest.raises(ValidationError, match="stages"):
        Bible.model_validate(raw)
    raw["arc"] = {"template": "gag-a-day", "target_strips": 3}
    assert Bible.model_validate(raw).arc.stages == []
    assert "heros-journey-lite" in {t.value for t in ArcTemplate}


def test_schemas_target_strips_bounds(fixtures_dir: Path) -> None:
    raw = load(fixtures_dir, "bible")
    for bad in (0, 41):
        raw["arc"]["target_strips"] = bad
        with pytest.raises(ValidationError):
            Bible.model_validate(raw)


def test_schemas_strip_script_panels_numbered(fixtures_dir: Path) -> None:
    panel = load(fixtures_dir, "panel")
    panel["idx"] = 1
    assert len(StripScript.model_validate({"panels": [panel]}).panels) == 1
    with pytest.raises(ValidationError):
        StripScript.model_validate({"panels": [{**panel, "idx": 2}]})
    with pytest.raises(ValidationError):
        StripScript.model_validate({"panels": []})


def test_schemas_moderation_verdict_defaults() -> None:
    assert ModerationVerdict(allowed=True).rule is None


def _walk(node: Any) -> list[str]:
    keys: list[str] = []
    if isinstance(node, dict):
        for k, v in node.items():
            keys.append(k)
            keys.extend(_walk(v))
    elif isinstance(node, list):
        for v in node:
            keys.extend(_walk(v))
    return keys


@pytest.mark.parametrize("model", [Bible, SuggestionSet, PanelSpec, Beat, ContinuityReport, StripScript])
def test_schemas_llm_schema_is_inlined_and_plain(model: type[BaseModel]) -> None:
    schema = llm_schema(model)
    keys = _walk(schema)
    for banned in ("$ref", "$defs", "title", "default", "const"):
        assert banned not in keys
    assert "schema" not in schema["properties"]
    assert schema["additionalProperties"] is False


def test_schemas_llm_schema_still_validates_documents(fixtures_dir: Path) -> None:
    raw = load(fixtures_dir, "panel")
    del raw["schema"]
    jsonschema.validate(raw, llm_schema(PanelSpec))
