"""Deterministic report schema, golden drafts and rendering sink validation."""

import json
from dataclasses import asdict, replace
from pathlib import Path

import pytest

from winagent_repropack import __version__
from winagent_repropack.aggregation import analyze_log
from winagent_repropack.doctor import summarize_doctor
from winagent_repropack.models import ClientType, DoctorSummary, GeneratorInfo, PrivacyInfo
from winagent_repropack.reports import (
    MAX_REPORT_BYTES,
    _bounded,
    build_report,
    escape_markdown,
    render_json,
    render_markdown,
)


def sample_report():
    return build_report(
        analyze_log("examples/synthetic.log"), summarize_doctor("examples/synthetic-doctor-v1.json")
    )


def test_golden_markdown_json_and_equivalent_counts() -> None:
    report = sample_report()
    markdown = render_markdown(report)
    encoded = render_json(report)
    assert markdown == Path("tests/golden/synthetic-report.md").read_text(encoding="utf-8")
    assert encoded == Path("tests/golden/synthetic-report.json").read_text(encoding="utf-8")
    data = json.loads(encoded)
    assert data["schema_version"] == 1
    assert data["generator"] == {"name": "WinAgent ReproPack", "version": __version__}
    assert data["source"] == {"type": "user-selected log", "client": "generic"}
    assert data["summary"] == {
        "total_lines": 9,
        "matched_event_lines": 6,
        "unknown_timestamp_lines": 0,
        "ambiguous_event_lines": 1,
        "timezone_unknown_lines": 0,
    }
    counts = {event["type"]: event["count"] for event in data["events"]}
    assert counts == {
        "remote_compact_failure": 1,
        "stream_disconnect": 1,
        "capacity": 2,
        "reconnect_loop": 1,
        "timeout": 1,
    }
    for event in data["events"]:
        assert f"| {escape_markdown(event['type'])} | {event['count']} |" in markdown
        assert event["redacted_excerpts"] == []
        for field in ["first_seen", "last_seen"]:
            assert escape_markdown(event[field]) in markdown
    assert data["doctor"]["check_counts"] == {"ok": 2, "warning": 1, "fail": 1}
    assert "ok=2, warning=1, fail=1" in markdown
    assert markdown.count("MANUAL REVIEW REQUIRED") == 2
    assert markdown.count("[USER TO FILL]") == 4
    assert data["privacy"] == {
        "raw_log_embedded": False,
        "redacted_excerpts_included": False,
        "manual_review_required": True,
    }


@pytest.mark.parametrize(
    "data,total,matched", [(b"", 0, 0), (b"\xef\xbb\xbf", 0, 0), (b"no supported patterns\n", 1, 0)]
)
def test_zero_events_and_omitted_empty_doctor(
    tmp_path: Path, data: bytes, total: int, matched: int
):
    source = tmp_path / "synthetic.log"
    source.write_bytes(data)
    analysis = analyze_log(source, include_excerpts=True)
    report = build_report(analysis, DoctorSummary())
    document = json.loads(render_json(report))
    assert document["summary"]["total_lines"] == total
    assert document["summary"]["matched_event_lines"] == matched
    assert document["events"] == []
    assert not document["doctor"]["included"]
    assert not document["privacy"]["redacted_excerpts_included"]
    assert "No supported symptom patterns matched" in render_markdown(report)
    assert "Doctor data not included" in render_markdown(report)
    empty = tmp_path / "synthetic.json"
    empty.write_text('{"schemaVersion":1,"checks":{}}', encoding="utf-8")
    present = build_report(analysis, summarize_doctor(empty))
    assert "Included: yes; schema: 1" in render_markdown(present)
    assert asdict(present.doctor) != document["doctor"]


@pytest.mark.parametrize("client", list(ClientType))
def test_client_and_timezone_uncertainty(tmp_path: Path, client: ClientType) -> None:
    source = tmp_path / "synthetic.log"
    source.write_text("2026-10-22T01:00:00 HTTP 503\nHTTP 503\n", encoding="utf-8")
    report = build_report(analyze_log(source), DoctorSummary(), client=client)
    data = json.loads(render_json(report))
    assert data["source"]["client"] == client.value
    assert data["events"][0]["first_seen"] is data["events"][0]["last_seen"] is None
    assert data["summary"]["timezone_unknown_lines"] == 1
    assert "timezone unknown" in render_markdown(report)


def test_markdown_escaping_defends_structure() -> None:
    text = escape_markdown("<script> | ``` [x](https://example.invalid) # title\r\n\u202e")
    assert "<script>" not in text and "&lt;script&gt;" in text
    assert "\\|" in text and "\\`\\`\\`" in text and "\\#" in text
    assert "\n" not in text and "\r" not in text and "\u202e" not in text


@pytest.mark.parametrize(
    "variant",
    [
        "schema",
        "generator",
        "source",
        "warnings",
        "summary",
        "duplicates",
        "order",
        "count",
        "line_numbers",
        "first_line",
        "last_line",
        "time_pair",
        "bad_time",
        "calendar",
        "excerpt",
        "privacy",
        "doctor_absent",
        "doctor_schema",
        "doctor_version",
        "doctor_counts",
    ],
)
def test_invalid_programmatic_models_are_refused(variant: str) -> None:
    report = sample_report()
    event = report.events[0]
    if variant == "schema":
        report = replace(report, schema_version=True)
    elif variant == "generator":
        report = replace(report, generator=GeneratorInfo("PRIVATE_CANARY", __version__))
    elif variant == "source":
        report = replace(report, source=replace(report.source, type="PRIVATE_CANARY"))
    elif variant == "warnings":
        report = replace(report, warnings=("PRIVATE_CANARY",))
    elif variant == "summary":
        report = replace(report, summary=replace(report.summary, total_lines=-1))
    elif variant == "duplicates":
        report = replace(report, events=(event, event))
    elif variant == "order":
        report = replace(report, events=report.events[::-1])
    elif variant == "count":
        event = replace(event, count=0)
    elif variant == "line_numbers":
        event = replace(event, line_numbers=(999_999,))
    elif variant == "first_line":
        event = replace(event, first_observed_line=0)
    elif variant == "last_line":
        event = replace(event, last_observed_line=0)
    elif variant == "time_pair":
        event = replace(event, first_seen=None)
    elif variant == "bad_time":
        event = replace(event, first_seen="PRIVATE_CANARY")
    elif variant == "calendar":
        event = replace(event, first_seen="2026-99-99T01:00:00+00:00")
    elif variant == "excerpt":
        event = replace(event, redacted_excerpts=("PRIVATE_CANARY",))
    elif variant == "privacy":
        report = replace(report, privacy=PrivacyInfo(True, False, False))
    elif variant == "doctor_absent":
        report = replace(report, doctor=replace(report.doctor, included=False))
    elif variant == "doctor_schema":
        report = replace(report, doctor=replace(report.doctor, schema_version=True))
    elif variant == "doctor_version":
        report = replace(report, doctor=replace(report.doctor, codex_version="PRIVATE_CANARY\n"))
    elif variant == "doctor_counts":
        report = replace(
            report,
            doctor=replace(report.doctor, check_counts=replace(report.doctor.check_counts, ok=-1)),
        )
    if event != report.events[0]:
        report = replace(report, events=(event, *report.events[1:]))
    for renderer in [render_json, render_markdown]:
        with pytest.raises(ValueError) as caught:
            renderer(report)
        assert "PRIVATE_CANARY" not in str(caught.value)


def test_output_text_bound() -> None:
    with pytest.raises(ValueError, match="byte limit"):
        _bounded("界" * MAX_REPORT_BYTES)
