"""S0-T01, S0-T03, S0-T11: spec docs, hygiene files, and agent files exist with required content."""

import re
import subprocess
from pathlib import Path

from tests.conftest import ROOT

SPECS = ("PRD.md", "ARCHITECTURE.md", "DESIGN.md", "SPRINT_PLAN.md", "TEST_PLAN.md")
REQUIRED_HEADINGS = {
    "PRD.md": [
        "Overview",
        "Personas",
        "Core loop",
        "User stories",
        "Functional requirements",
        "Non-functional requirements",
        "Success metrics",
        "Constraints",
        "Out of scope",
        "Glossary",
    ],
    "ARCHITECTURE.md": [
        "System overview",
        "Decision log",
        "Module map",
        "Data model",
        "Data formats",
        "Pipelines",
        "Contracts",
        "Job system",
        "Caching",
        "Error model",
        "Security",
        "Deployment",
    ],
    "DESIGN.md": [
        "principles",
        "Information architecture",
        "Wireframes",
        "Component inventory",
        "Lettering",
        "layout templates",
        "Motion",
        "Copy",
        "Child mode",
        "Reader",
        "Anti-patterns",
    ],
    "TEST_PLAN.md": [
        "Strategy",
        "Coverage targets",
        "Naming convention",
        "Fixtures",
        "Scenario",
        "evaluation",
        "Visual regression",
        "Smoke checklist",
        "Regression",
    ],
}
GITIGNORE_REQUIRED = [
    "__pycache__/",
    ".venv/",
    "node_modules/",
    ".env",
    "coverage/",
    "/projects/",
    "/exports/",
    "*.db",
    "/models/",
    "*.safetensors",
    ".DS_Store",
    "CLAUDE.local.md",
]


def _read(name: str) -> str:
    return (ROOT / name).read_text(encoding="utf-8")


def _ignored(path: str) -> bool:
    out = subprocess.run(["git", "check-ignore", "-q", "--no-index", path], cwd=ROOT, check=False)
    return out.returncode == 0


def test_docs_spec_files_all_five_present() -> None:
    assert all((ROOT / "docs" / s).is_file() for s in SPECS)


def test_docs_required_sections_present_in_each_spec() -> None:
    for doc, headings in REQUIRED_HEADINGS.items():
        text = _read(f"docs/{doc}")
        found = "\n".join(line for line in text.splitlines() if line.startswith("#")).lower()
        missing = [h for h in headings if h.lower() not in found]
        assert not missing, f"{doc} missing {missing}"


def test_docs_every_fr_has_acceptance_criteria() -> None:
    text = _read("docs/PRD.md")
    sections = re.split(r"(?m)^#+ (?=FR-\d{3})", text)[1:]
    assert len(sections) >= 34
    for section in sections:
        body = re.split(r"(?m)^#+ ", section, maxsplit=1)[0]
        assert "Acceptance criteria" in body, section[:7]


def test_docs_every_us_maps_to_at_least_one_fr() -> None:
    text = _read("docs/PRD.md")
    us_ids = set(re.findall(r"US-\d{3}", text))
    assert len(us_ids) >= 24
    for us in us_ids:
        rows = [ln for ln in text.splitlines() if us in ln and "FR-" in ln]
        assert rows, f"{us} has no FR mapping"


def test_docs_no_em_or_en_dash_in_committed_files() -> None:
    from scripts.check_em_dash import find_dashes, tracked_files

    assert find_dashes(tracked_files()) == []


def test_repo_gitignore_contains_required_groups() -> None:
    lines = _read(".gitignore").splitlines()
    assert all(p in lines for p in GITIGNORE_REQUIRED)


def test_repo_gitignore_fixtures_not_ignored() -> None:
    assert not _ignored("tests/fixtures/projects/finalized-duck/project.db")


def test_repo_gitignore_user_projects_ignored() -> None:
    assert _ignored("projects/duck/project.db")
    assert _ignored("scratch.db")


def test_repo_gitattributes_lfs_patterns_declared() -> None:
    text = _read(".gitattributes")
    for pattern in ("tests/fixtures/images/*", "tests/fixtures/goldens/*", "comic_smith/letter/fonts/*"):
        assert re.search(re.escape(pattern) + r" filter=lfs", text), pattern


def test_repo_license_names_serverless_ventures_2026() -> None:
    text = _read("LICENSE")
    assert "MIT License" in text
    assert "2026 Serverless Ventures LLC" in text


def test_repo_hygiene_files_all_present() -> None:
    names = (
        ".gitignore",
        ".editorconfig",
        ".gitattributes",
        "LICENSE",
        "THIRD_PARTY_LICENSES.md",
        "CHANGELOG.md",
        "SECURITY.md",
        "CODE_OF_CONDUCT.md",
        "CONTRIBUTING.md",
    )
    assert all((ROOT / n).is_file() for n in names)
    assert "## [Unreleased]" in _read("CHANGELOG.md")
    assert "Developer Certificate of Origin" in _read("CONTRIBUTING.md")


def test_agent_files_all_present() -> None:
    assert all((ROOT / n).is_file() for n in ("AGENTS.md", "CLAUDE.md", "SKILLS.md", "SOUL.md"))


def test_agent_claude_md_starts_with_import_agents_md() -> None:
    assert _read("CLAUDE.md").splitlines()[0] == "@import AGENTS.md"


def test_agent_soul_md_has_at_least_six_hard_constraints() -> None:
    section = _read("SOUL.md").split("## Hard constraints", 1)[1].split("\n## ", 1)[0]
    assert len([ln for ln in section.splitlines() if ln.startswith("- ")]) >= 6


def test_agent_soul_md_contains_no_commands_or_paths() -> None:
    text = _read("SOUL.md")
    assert "```" not in text
    assert "`" not in text
    assert not re.search(r"(?<!\w)(\./|/\w+/|\w+\.(py|sh|md|ts)\b)", text)


def test_agent_skills_run_tests_check_types_make_fixture_comic_exist() -> None:
    for skill in ("run-tests", "check-types", "make-fixture-comic"):
        base = ROOT / ".agent" / "skills" / skill
        assert (base / "SKILL.md").read_text(encoding="utf-8").startswith("---\nname: " + skill)
        run = base / "run.sh"
        assert run.is_file()
        assert run.stat().st_mode & 0o111 or Path(run).read_text(encoding="utf-8").startswith("#!")
