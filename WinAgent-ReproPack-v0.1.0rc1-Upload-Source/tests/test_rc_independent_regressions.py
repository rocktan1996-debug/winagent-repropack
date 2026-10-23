"""R3 audit regressions, using only synthetic input and canary metadata."""

import json
from dataclasses import asdict, replace
from pathlib import Path

import pytest

from winagent_repropack import cli
from winagent_repropack.aggregation import analyze_log
from winagent_repropack.classifier import classify_line, matching_categories
from winagent_repropack.doctor import DoctorInputError, _parse_doctor, summarize_doctor
from winagent_repropack.models import DoctorSummary, EventType
from winagent_repropack.reports import build_report, render_json, render_markdown

TOKEN_VERSIONS = (
    "sk-" + "A" * 32,
    "ghp_" + "B" * 32,
    "n7Q2m9W4x6R8t3Y5p1K0v2D4j6H8b0L9c5F3s7Z1",
    "1.2.3+sk-" + "A" * 32,
)


@pytest.mark.parametrize("assignment", ["=", ": "])
@pytest.mark.parametrize("value", [
    "30", "30s", "30ms", "0.5ms", "30 MS", "30secs", "2min", "1h", "3ns", "4us",
    "5\u00b5s", "6milliseconds", "7msecs", "8seconds", "9minutes", "10hours", "11hrs", "30ms.",
])
def test_timeout_configuration_with_units_is_not_an_event(assignment: str, value: str) -> None:
    line = f"Error: default timeout{assignment}{value} configured; retry failed elsewhere"
    assert EventType.TIMEOUT not in matching_categories(line)


@pytest.mark.parametrize(
    "line",
    [
        "request actually timed out",
        "error: timeout exceeded",
        "Error: default timeout=30ms; request actually timed out",
        "Error: timeout: 30s configured; independent timeout exceeded",
        "request failed: timeout; default timeout=30ms",
        "Error: timeout=30ms; timeout=2s; timeout exception",
        "Error: timeout=30msx",
        "Error: timeout=30.5msx",
    ],
)
def test_real_timeouts_are_not_suppressed(line: str) -> None:
    assert EventType.TIMEOUT in matching_categories(line)


@pytest.mark.parametrize(
    "prefix,expected",
    [
        ("Error running remote compact task", EventType.REMOTE_COMPACT_FAILURE),
        ("stream disconnected before completion", EventType.STREAM_DISCONNECT),
        ("server_overloaded HTTP 503", EventType.CAPACITY),
        ("HTTP 503", EventType.HTTP_503),
        ("Reconnecting 3/5", EventType.RECONNECT_LOOP),
    ],
)
@pytest.mark.parametrize("real_timeout", [False, True])
def test_unit_configuration_preserves_all_other_priorities(prefix, expected, real_timeout):
    line = f"{prefix}; Error: timeout=30ms configured"
    if real_timeout:
        line += "; request timed out"
    matches = matching_categories(line)
    assert classify_line(line) == expected
    assert (EventType.TIMEOUT in matches) == real_timeout


@pytest.mark.parametrize("version", TOKEN_VERSIONS)
def test_doctor_rejects_token_before_returning_a_model(version: str) -> None:
    data = json.dumps({"schemaVersion": 1, "checks": {}, "codexVersion": version}).encode()
    with pytest.raises(DoctorInputError) as caught:
        _parse_doctor(data)
    assert str(caught.value) == "Doctor JSON has an invalid version identifier."
    assert caught.value.__context__ is caught.value.__cause__ is None
    assert version[-16:] not in repr(caught.value)


@pytest.mark.parametrize("format_name", ["markdown", "json"])
@pytest.mark.parametrize("include", [False, True])
@pytest.mark.parametrize("version", TOKEN_VERSIONS)
def test_doctor_version_cannot_export_token_shaped_metadata(
    tmp_path: Path, capsys, monkeypatch, format_name: str, include: bool, version: str
) -> None:
    log = tmp_path / "SYNTHETIC_LOG_PATH_CANARY.log"
    doctor = tmp_path / "SYNTHETIC_DOCTOR_PATH_CANARY.json"
    output = tmp_path / "SYNTHETIC_OUTPUT_PATH_CANARY.txt"
    log.write_text("HTTP 503 PRIVATE_CONTEXT_CANARY\n", encoding="utf-8")
    doctor.write_text(
        json.dumps({"schemaVersion": 1, "checks": {}, "codexVersion": version}),
        encoding="utf-8",
    )
    original = log.read_bytes(), doctor.read_bytes()

    def forbidden_model(*args, **kwargs):
        pytest.fail("Rejected Doctor metadata must not reach the report model builder")

    monkeypatch.setattr(cli, "build_report", forbidden_model)
    args = ["analyze", "--log", str(log), "--doctor-json", str(doctor),
            "--output", str(output), "--format", format_name]
    if include:
        args.append("--include-redacted-excerpts")
    assert cli.main(args) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == "repropack: error: input was refused; no report was created.\n"
    assert not output.exists()
    assert (log.read_bytes(), doctor.read_bytes()) == original
    with pytest.raises(DoctorInputError) as caught:
        summarize_doctor(doctor)
    assert caught.value.__context__ is caught.value.__cause__ is None
    visible = captured.out + captured.err + repr(caught.value)
    for canary in [version, version[-16:], str(tmp_path), log.name, doctor.name,
                   output.name, "PRIVATE_CONTEXT_CANARY", "Traceback"]:
        assert canary not in visible


@pytest.mark.parametrize("version", TOKEN_VERSIONS)
@pytest.mark.parametrize("renderer", [render_json, render_markdown])
def test_rendering_sinks_reject_injected_version_models(tmp_path, version, renderer):
    log = tmp_path / "synthetic.log"
    log.write_text("HTTP 503\n", encoding="utf-8")
    analysis = analyze_log(log)
    with pytest.raises(ValueError, match="^Report model failed validation\\.$") as caught:
        build_report(analysis, DoctorSummary(True, 1, version))
    assert caught.value.__context__ is caught.value.__cause__ is None
    safe = build_report(analysis, DoctorSummary(True, 1, "0.123.0"))
    forged = replace(safe, doctor=replace(safe.doctor, codex_version=version))
    with pytest.raises(ValueError, match="^Report model failed validation\\.$"):
        renderer(forged)


@pytest.mark.parametrize("format_name", ["markdown", "json"])
@pytest.mark.parametrize("version", ["0.123.0", "1.2.3-rc.1+build.2", None])
def test_valid_or_missing_version_survives_cli_without_private_context(
    tmp_path: Path, capsys, format_name: str, version: str | None
) -> None:
    log, doctor, output = (tmp_path / name for name in ["input.log", "doctor.json", "report.txt"])
    log.write_text("Error: timeout=30ms configured PRIVATE_CONTEXT_CANARY\n", encoding="utf-8")
    payload = {"schemaVersion": 1, "checks": {}, "details": "DOCTOR_CONTEXT_CANARY"}
    if version is not None:
        payload["codexVersion"] = version
    doctor.write_text(json.dumps(payload), encoding="utf-8")
    summary = summarize_doctor(doctor)
    assert summary.codex_version == version
    assert cli.main(["analyze", "--log", str(log), "--doctor-json", str(doctor),
                     "--output", str(output), "--format", format_name]) == 0
    captured = capsys.readouterr()
    text = output.read_text(encoding="utf-8")
    assert captured.err == ""
    assert "matched event lines: 0" in captured.out
    combined = text + captured.out + repr(asdict(summary))
    for canary in ["PRIVATE_CONTEXT_CANARY", "DOCTOR_CONTEXT_CANARY", str(tmp_path)]:
        assert canary not in combined
    if format_name == "json":
        assert json.loads(text)["doctor"]["codex_version"] == version


@pytest.mark.parametrize("version", [
    "", "1.2", "v1.2.3", "01.2.3", "1.02.3", "1.2.03", "1.2.3_4",
    "x" * 64, "1.2.3+" + "A" * 40, "1.2.3-alpha..1", "1.2.3+build_2",
    "1.2.3\n", "1.2.3+SK-FAKE", "1234567890.2.3",
])
def test_doctor_version_grammar_refuses_untrusted_or_unsupported_metadata(version: str) -> None:
    data = json.dumps({"schemaVersion": 1, "checks": {}, "codexVersion": version}).encode()
    with pytest.raises(
        DoctorInputError, match="^Doctor JSON has an invalid version identifier\\.$"
    ):
        _parse_doctor(data)
