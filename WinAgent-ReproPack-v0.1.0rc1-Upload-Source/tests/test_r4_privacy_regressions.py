"""Independent R4 adversarial tests; inputs and canaries are entirely synthetic."""

import json
from dataclasses import replace
from pathlib import Path

import pytest

from winagent_repropack.aggregation import analyze_log
from winagent_repropack.cli import main
from winagent_repropack.doctor import DoctorInputError, _parse_doctor
from winagent_repropack.models import DoctorSummary
from winagent_repropack.reports import build_report, render_json, render_markdown

BAD_VERSIONS = (
    "1.2.3+ALICE.SSN.123456789",
    "1.2.3-ALICE",
    "1.2.3-rc.ALICE",
    "1.2.3+build.00001",
    "1.2.3+build.123456789",
    "1.2.3-rc.1+test.1",
    "1.2.3-rc.1+g1a2b3c4",
    "1.2.3-sk-DEMO123",
    "1.2.3-beta.0001",
    "1.2.3+build.1.CUSTOM",
    "1.2.3+build.1+another",
    "1.2.3-rc.1-ALICE",
)
GOOD_VERSIONS = (
    "0.0.0", "0.0.0-dev.1+build.1", "1.2.3-rc.1+build.2", "1.2.3-alpha", "1.2.3+build.0"
)


@pytest.mark.parametrize("value", BAD_VERSIONS)
def test_rejected_before_returning_doctor_summary(value: str) -> None:
    raw = json.dumps({"schemaVersion": 1, "checks": {}, "codexVersion": value}).encode()
    with pytest.raises(DoctorInputError) as err:
        _parse_doctor(raw)
    assert str(err.value) == "Doctor JSON has an invalid version identifier."
    assert err.value.__cause__ is None and err.value.__context__ is None
    assert value not in repr(err.value)


@pytest.mark.parametrize("version", GOOD_VERSIONS)
def test_narrow_versions_can_still_import(version: str) -> None:
    raw = json.dumps({"schemaVersion": 1, "checks": {}, "codexVersion": version}).encode()
    assert _parse_doctor(raw).codex_version == version


@pytest.mark.parametrize("version", BAD_VERSIONS)
@pytest.mark.parametrize("renderer", (render_json, render_markdown))
def test_forged_report_model_version_rejected(tmp_path: Path, version: str, renderer) -> None:
    log = tmp_path / "synthetic.log"
    log.write_text("HTTP 503\n", encoding="utf-8")
    analysis = analyze_log(log)
    with pytest.raises(ValueError, match="^Report model failed validation\\.$"):
        build_report(analysis, DoctorSummary(True, 1, version))
    safe = build_report(analysis, DoctorSummary(True, 1, "1.2.3"))
    forged = replace(safe, doctor=replace(safe.doctor, codex_version=version))
    with pytest.raises(ValueError, match="^Report model failed validation\\.$"):
        renderer(forged)


@pytest.mark.parametrize(
    "version", ("1.2.3+ALICE.SSN.123456789", "1.2.3-rc.ALICE", "1.2.3+build.00001")
)
@pytest.mark.parametrize("format_name", ("markdown", "json"))
@pytest.mark.parametrize("excerpts", (False, True))
def test_rejected_versions_never_reach_cli_output(
    tmp_path: Path, capsys, version: str, format_name: str, excerpts: bool
) -> None:
    log = tmp_path / "CANARY_LOG.log"
    doctor = tmp_path / "CANARY_DOCTOR.json"
    out = tmp_path / "CANARY_OUTPUT.md"
    log.write_text("HTTP 503 SECRET_CANARY\n", encoding="utf-8")
    doctor.write_text(
        json.dumps({"schemaVersion": 1, "checks": {}, "codexVersion": version}),
        encoding="utf-8",
    )
    args = ["analyze", "--log", str(log), "--doctor-json", str(doctor),
            "--output", str(out), "--format", format_name]
    if excerpts:
        args.append("--include-redacted-excerpts")
    assert main(args) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == "repropack: error: input was refused; no report was created.\n"
    assert not out.exists()
    assert "CANARY" not in captured.err and version not in captured.err
