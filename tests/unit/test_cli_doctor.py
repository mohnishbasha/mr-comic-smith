"""S0-T12 and S0-T02: doctor checks and the CLI front door."""

import json
import sys
from pathlib import Path

import pytest
from typer.testing import CliRunner

from comic_smith import doctor
from comic_smith.cli import app
from comic_smith.config import Settings, load_settings
from comic_smith.doctor import Check, CheckResult, core_checks, run_checks

runner = CliRunner()


def _ok(name: str, required: bool = True) -> Check:
    return Check(name=name, run=lambda _s: CheckResult(name=name, ok=True, required=required))


def test_doctor_check_registry_runs_all_checks(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(doctor, "chromium_path", lambda: "/bin/sh")
    report = run_checks(load_settings(), core_checks())
    assert [r.name for r in report.results] == ["python", "data_dir", "disk_space", "chromium", "fonts"]


def test_doctor_crashing_check_is_reported_not_raised() -> None:
    def boom(_s: Settings) -> CheckResult:
        raise RuntimeError("kaput")

    report = run_checks(load_settings(), [Check(name="boom", run=boom), _ok("fine")])
    assert not report.ok
    assert "kaput" in report.results[0].detail


def test_doctor_json_output_parses(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(doctor, "default_checks", lambda: [_ok("python"), _ok("fonts", required=False)])
    result = runner.invoke(app, ["doctor", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["ok"] is True
    assert [r["name"] for r in data["results"]] == ["python", "fonts"]


def test_doctor_table_output_lists_checks(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(doctor, "default_checks", lambda: [_ok("python")])
    result = runner.invoke(app, ["doctor"])
    assert result.exit_code == 0
    assert "python" in result.output


def test_doctor_required_failure_exits_three(monkeypatch: pytest.MonkeyPatch) -> None:
    failing = Check(name="x", run=lambda _s: CheckResult(name="x", ok=False, hint="fix it"))
    monkeypatch.setattr(doctor, "default_checks", lambda: [failing])
    result = runner.invoke(app, ["doctor"])
    assert result.exit_code == 3


def test_doctor_optional_failure_still_exits_zero(monkeypatch: pytest.MonkeyPatch) -> None:
    warn = Check(name="w", run=lambda _s: CheckResult(name="w", ok=False, required=False))
    monkeypatch.setattr(doctor, "default_checks", lambda: [warn])
    assert runner.invoke(app, ["doctor"]).exit_code == 0


def test_doctor_missing_chromium_reports_fix_hint(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(doctor, "chromium_path", lambda: None)
    result = doctor.check_chromium(load_settings())
    assert not result.ok
    assert result.hint is not None
    assert "doctor --fix" in result.hint


def test_doctor_chromium_present_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(doctor, "chromium_path", lambda: sys.executable)
    assert doctor.check_chromium(load_settings()).ok


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX permissions")
def test_doctor_unwritable_data_dir_fails(tmp_path: Path) -> None:
    locked = tmp_path / "locked"
    locked.mkdir()
    locked.chmod(0o500)
    try:
        result = doctor.check_data_dir(Settings(data_dir=locked / "sub"))
    finally:
        locked.chmod(0o700)
    assert not result.ok
    assert result.required
    assert "COMIC_SMITH_DATA_DIR" in (result.hint or "")


def test_doctor_python_and_disk_checks_pass() -> None:
    s = load_settings()
    assert doctor.check_python(s).ok
    assert doctor.check_disk(s).name == "disk_space"


def test_doctor_fonts_missing_is_warning(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(doctor, "FONTS_DIR", tmp_path / "none")
    result = doctor.check_fonts(load_settings())
    assert not result.ok
    assert not result.required


def test_doctor_fonts_present_ok(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    for fam in doctor.REQUIRED_FONT_FAMILIES:
        (tmp_path / f"{fam}-Regular.ttf").write_bytes(b"x")
    monkeypatch.setattr(doctor, "FONTS_DIR", tmp_path)
    assert doctor.check_fonts(load_settings()).ok


def test_doctor_fix_runs_playwright_install(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[list[str]] = []

    class Done:
        returncode = 0

    def fake_run(args: list[str], **_kw: object) -> Done:
        calls.append(args)
        return Done()

    monkeypatch.setattr(doctor.subprocess, "run", fake_run)
    assert doctor.fix_chromium()
    assert calls[0][-2:] == ["install", "chromium"]


def test_cli_doctor_fix_flag_calls_fix(monkeypatch: pytest.MonkeyPatch) -> None:
    called: list[bool] = []
    monkeypatch.setattr(doctor, "fix_chromium", lambda: called.append(True) or False)
    monkeypatch.setattr("comic_smith.api.fix_chromium", lambda: called.append(True) or False)
    monkeypatch.setattr(doctor, "default_checks", lambda: [_ok("python")])
    result = runner.invoke(app, ["doctor", "--fix"])
    assert called
    assert result.exit_code == 0


def test_cli_no_args_shows_help() -> None:
    result = runner.invoke(app, [])
    assert "doctor" in result.output


def test_cli_config_error_maps_to_exit_two(tmp_path: Path) -> None:
    from comic_smith import cli

    bad = tmp_path / "bad.toml"
    bad.write_text("studio_port = [\n", encoding="utf-8")
    with pytest.raises(SystemExit) as exc:
        sys_argv = ["mr-comic-smith", "--config", str(bad), "doctor"]
        monkey = pytest.MonkeyPatch()
        monkey.setattr(sys, "argv", sys_argv)
        try:
            cli.main()
        finally:
            monkey.undo()
    assert exc.value.code == 2


def test_cli_studio_passes_port_to_api(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, object] = {}

    def fake_run_studio(_s: Settings, *, host: str, port: int, open_browser: bool) -> None:
        seen.update(host=host, port=port, open_browser=open_browser)

    monkeypatch.setattr("comic_smith.api.run_studio", fake_run_studio)
    result = runner.invoke(app, ["studio", "--port", "7400", "--no-browser"])
    assert result.exit_code == 0
    assert seen == {"host": "127.0.0.1", "port": 7400, "open_browser": False}
