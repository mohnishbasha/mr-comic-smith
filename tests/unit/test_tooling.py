"""S0-T02, S0-T04, S0-T05, S0-T09, S0-T10: packaging, lint config, harness scripts, CI, versions."""

import importlib.util
import json
import re
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path
from types import ModuleType

import pytest
import yaml

from scripts.check_em_dash import find_dashes
from tests.conftest import ROOT


def _load_script(name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name.replace("-", "_"), ROOT / "scripts" / f"{name}.py")
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


check_coverage_mod = _load_script("check-coverage")
PYPROJECT = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
BASH = shutil.which("bash")
needs_bash = pytest.mark.skipif(BASH is None or sys.platform == "win32", reason="needs a POSIX bash")


def test_cli_version_prints_pyproject_version() -> None:
    from typer.testing import CliRunner

    from comic_smith.cli import app

    result = CliRunner().invoke(app, ["--version"])
    assert result.exit_code == 0
    assert PYPROJECT["project"]["version"] in result.output


def test_packaging_base_install_does_not_pull_torch() -> None:
    deps = " ".join(PYPROJECT["project"]["dependencies"])
    assert "torch" not in deps
    lock = (ROOT / "uv.lock").read_text(encoding="utf-8")
    assert 'name = "torch"' not in lock


def test_packaging_optional_extras_declared() -> None:
    extras = set(PYPROJECT["project"]["optional-dependencies"])
    assert {"comfyui", "gemini", "openai", "anthropic", "ocr", "server", "mcp", "dev"} <= extras


def test_packaging_python_range_is_312_to_313() -> None:
    assert PYPROJECT["project"]["requires-python"] == ">=3.12,<3.14"


def test_lint_ruff_rules_configured_as_specified() -> None:
    selected = set(PYPROJECT["tool"]["ruff"]["lint"]["select"])
    assert {"E", "F", "W", "I", "N", "UP", "B", "A", "C4", "SIM", "RUF", "S", "PTH", "TID", "PL"} <= selected


def test_lint_mypy_strict_enabled() -> None:
    assert PYPROJECT["tool"]["mypy"]["strict"] is True


def test_lint_em_dash_hook_rejects_u2014(tmp_path: Path) -> None:
    bad = tmp_path / "bad.md"
    bad.write_text("a " + chr(0x2014) + " b\n", encoding="utf-8")
    assert find_dashes([str(bad)])


def test_lint_en_dash_hook_rejects_u2013(tmp_path: Path) -> None:
    bad = tmp_path / "bad.py"
    bad.write_text("x = 1  # 1" + chr(0x2013) + "2\n", encoding="utf-8")
    assert find_dashes([str(bad)])
    good = tmp_path / "good.py"
    good.write_text("x = 1\n", encoding="utf-8")
    assert not find_dashes([str(good)])


def test_lint_makefile_targets_all_defined() -> None:
    text = (ROOT / "Makefile").read_text(encoding="utf-8")
    targets = set(re.findall(r"(?m)^([a-z0-9-]+):", text))
    required = {
        "lint",
        "format",
        "typecheck",
        "test",
        "test-int",
        "visual",
        "coverage",
        "smoke",
        "e2e",
        "check-versions",
        "build",
        "studio-dev",
    }
    assert required <= targets


def _coverage(files: dict[str, tuple[int, int]], percent: float) -> dict[str, object]:
    return {
        "files": {k: {"summary": {"covered_lines": c, "num_statements": t}} for k, (c, t) in files.items()},
        "totals": {"percent_covered": percent},
    }


def test_harness_coverage_script_fails_under_threshold() -> None:
    cov = _coverage({"comic_smith/letter/layout.py": (80, 100)}, 90.0)
    assert check_coverage_mod.check(cov, {"comic_smith/letter": 92, "overall": 85}) == ["comic_smith/letter"]


def test_harness_coverage_script_passes_at_threshold() -> None:
    cov = _coverage({"comic_smith/letter/layout.py": (92, 100)}, 85.0)
    assert check_coverage_mod.check(cov, {"comic_smith/letter": 92, "overall": 85}) == []


def test_harness_thresholds_toml_matches_test_plan() -> None:
    plan = (ROOT / "docs" / "TEST_PLAN.md").read_text(encoding="utf-8")
    block = plan.split("```toml", 1)[1].split("```", 1)[0]
    in_plan = tomllib.loads(block)
    in_repo = tomllib.loads((ROOT / ".coverage-thresholds.toml").read_text(encoding="utf-8"))
    assert in_plan == in_repo


def _ci() -> dict[str, object]:
    return yaml.safe_load((ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8"))


def test_ci_workflow_declares_all_required_jobs() -> None:
    jobs = set(_ci()["jobs"])  # type: ignore[call-overload]
    required = {
        "lint-and-typecheck",
        "unit-tests",
        "coverage",
        "integration-tests",
        "visual-regression",
        "e2e-tests",
        "check-versions",
        "smoke",
        "gpu-integration",
        "nightly-cloud",
        "harness-smoke-tests",
    }
    assert required <= jobs


def test_ci_concurrency_cancels_superseded_runs() -> None:
    assert _ci()["concurrency"]["cancel-in-progress"] is True  # type: ignore[index]


def test_ci_dependabot_covers_uv_npm_actions_docker() -> None:
    cfg = yaml.safe_load((ROOT / ".github" / "dependabot.yml").read_text(encoding="utf-8"))
    ecosystems = {u["package-ecosystem"] for u in cfg["updates"]}
    assert {"uv", "npm", "github-actions", "docker"} <= ecosystems


def test_ci_gpu_integration_targets_self_hosted_gpu_label() -> None:
    runs_on = _ci()["jobs"]["gpu-integration"]["runs-on"]  # type: ignore[index]
    assert "self-hosted" in runs_on
    assert "gpu" in runs_on


def _fake_repo(tmp_path: Path, version: str = "1.2.3", studio: str = "1.2.3") -> Path:
    repo = tmp_path / "repo"
    (repo / "scripts").mkdir(parents=True)
    for s in ("check-versions.sh", "bump-version.sh", "extract-changelog.sh"):
        shutil.copy(ROOT / "scripts" / s, repo / "scripts" / s)
    (repo / "pyproject.toml").write_text(f'[project]\nname = "x"\nversion = "{version}"\n', encoding="utf-8")
    (repo / "web" / "studio").mkdir(parents=True)
    (repo / "web" / "studio" / "package.json").write_text(json.dumps({"version": studio}), encoding="utf-8")
    chart = repo / "charts" / "mr-comic-smith"
    chart.mkdir(parents=True)
    (chart / "Chart.yaml").write_text(f'version: {version}\nappVersion: "{version}"\n', encoding="utf-8")
    return repo


def _run(repo: Path, script: str, *args: str) -> subprocess.CompletedProcess[str]:
    env = {"PATH": str(Path(sys.executable).parent) + ":/usr/bin:/bin", "COMIC_SMITH_REPO_ROOT": str(repo)}
    return subprocess.run(
        [BASH or "bash", f"scripts/{script}", *args],
        cwd=repo,
        env=env,
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
    )


@needs_bash
def test_scripts_check_versions_mismatch_exits_one_naming_file(tmp_path: Path) -> None:
    repo = _fake_repo(tmp_path, studio="9.9.9")
    out = _run(repo, "check-versions.sh")
    assert out.returncode == 1
    assert "web/studio/package.json" in out.stdout


@needs_bash
def test_scripts_check_versions_match_exits_zero(tmp_path: Path) -> None:
    out = _run(_fake_repo(tmp_path), "check-versions.sh")
    assert out.returncode == 0, out.stdout + out.stderr


@needs_bash
def test_scripts_bump_version_updates_all_files(tmp_path: Path) -> None:
    repo = _fake_repo(tmp_path)
    out = _run(repo, "bump-version.sh", "2.0.0")
    assert out.returncode == 0, out.stdout + out.stderr
    assert 'version = "2.0.0"' in (repo / "pyproject.toml").read_text(encoding="utf-8")
    assert json.loads((repo / "web/studio/package.json").read_text(encoding="utf-8"))["version"] == "2.0.0"
    chart = yaml.safe_load((repo / "charts/mr-comic-smith/Chart.yaml").read_text(encoding="utf-8"))
    assert chart["version"] == "2.0.0"
    assert chart["appVersion"] == "2.0.0"


@needs_bash
def test_scripts_extract_changelog_prints_only_requested_section(tmp_path: Path) -> None:
    repo = _fake_repo(tmp_path)
    (repo / "CHANGELOG.md").write_text(
        "# Changelog\n\n## [Unreleased]\n\n- next\n\n## [1.1.0] - 2026-12-01\n\n- new thing\n\n"
        "## [1.0.0] - 2026-11-01\n\n- old thing\n",
        encoding="utf-8",
    )
    out = _run(repo, "extract-changelog.sh", "1.1.0")
    assert out.returncode == 0
    assert "new thing" in out.stdout
    assert "old thing" not in out.stdout
    assert "next" not in out.stdout


@needs_bash
def test_scripts_extract_changelog_missing_section_fails(tmp_path: Path) -> None:
    repo = _fake_repo(tmp_path)
    (repo / "CHANGELOG.md").write_text("# Changelog\n\n## [Unreleased]\n", encoding="utf-8")
    assert _run(repo, "extract-changelog.sh", "3.0.0").returncode != 0
