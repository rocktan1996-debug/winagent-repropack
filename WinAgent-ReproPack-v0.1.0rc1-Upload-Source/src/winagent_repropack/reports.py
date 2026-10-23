"""Validated deterministic JSON v1 and editable Markdown issue drafts."""

import html
import json
import re
from dataclasses import asdict
from datetime import datetime

from winagent_repropack import __version__
from winagent_repropack.doctor import _VERSION
from winagent_repropack.models import (
    ClientType,
    DiagnosticReport,
    DoctorSummary,
    EventType,
    GeneratorInfo,
    LogAnalysis,
    PrivacyInfo,
    ReportEvent,
    ReportSummary,
    SourceInfo,
)
from winagent_repropack.privacy import MAX_EXCERPTS, SAFE_EXCERPTS, clean_controls

MAX_REPORT_BYTES = 64 * 1024
WARNINGS = (
    "Symptoms do not establish root cause.",
    "Review output before sharing.",
    "Unknown private information may remain; manual review required.",
    "Independent project; not affiliated with or endorsed by OpenAI.",
)
_TIME = re.compile(
    r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}"
    r"(?:\.[0-9]{6})?[+-][0-9]{2}:[0-9]{2}"
)


def build_report(
    analysis: LogAnalysis, doctor: DoctorSummary, *, client: ClientType = ClientType.GENERIC
) -> DiagnosticReport:
    """Combine validated aggregates, never source text or original filenames."""
    log = analysis.summary
    samples = {group.type: group.samples for group in analysis.excerpts}
    events = tuple(
        ReportEvent(**asdict(event), redacted_excerpts=samples.get(event.type, ()))
        for event in log.events
    )
    report = DiagnosticReport(
        schema_version=1,
        generator=GeneratorInfo("WinAgent ReproPack", __version__),
        source=SourceInfo("user-selected log", ClientType(client)),
        summary=ReportSummary(
            log.total_lines,
            log.matched_event_lines,
            log.unknown_timestamp_lines,
            log.warnings.ambiguous_event_lines,
            log.warnings.timezone_unknown_lines,
        ),
        events=events,
        doctor=doctor,
        warnings=WARNINGS,
        privacy=PrivacyInfo(False, any(event.redacted_excerpts for event in events), True),
    )
    validate_report(report)
    return report


def _require(condition: bool) -> None:
    if not condition:
        raise ValueError("Report model failed validation.")


def _integer(value: object, minimum: int = 0, maximum: int = 50_000) -> bool:
    return type(value) is int and minimum <= value <= maximum


def _time(value: str) -> datetime:
    _require(isinstance(value, str) and _TIME.fullmatch(value) is not None)
    try:
        result = datetime.fromisoformat(value)
    except ValueError:
        raise ValueError("Report model failed validation.") from None
    _require(result.tzinfo is not None and result.isoformat() == value)
    return result


def validate_report(report: DiagnosticReport) -> None:
    """Guard rendering sinks against malformed programmatic models as well."""
    _require(
        type(report) is DiagnosticReport
        and type(report.schema_version) is int
        and report.schema_version == 1
    )
    _require(report.generator == GeneratorInfo("WinAgent ReproPack", __version__))
    _require(report.source.type == "user-selected log" and type(report.source.client) is ClientType)
    _require(report.warnings == WARNINGS)
    summary = report.summary
    _require(all(_integer(value) for value in asdict(summary).values()))
    _require(
        summary.matched_event_lines <= summary.total_lines
        and summary.unknown_timestamp_lines <= summary.total_lines
        and summary.timezone_unknown_lines <= summary.unknown_timestamp_lines
        and summary.ambiguous_event_lines <= summary.matched_event_lines
    )
    _require(type(report.events) is tuple and len(report.events) <= len(EventType))
    order = [event.type for event in report.events]
    _require(all(type(kind) is EventType for kind in order))
    _require(order == [kind for kind in EventType if kind in order])
    _require(sum(event.count for event in report.events) == summary.matched_event_lines)
    for event in report.events:
        _require(type(event) is ReportEvent and _integer(event.count, 1))
        _require(
            _integer(event.first_observed_line, 1, summary.total_lines)
            and _integer(event.last_observed_line, event.first_observed_line, summary.total_lines)
        )
        _require(
            type(event.line_numbers) is tuple and len(event.line_numbers) == min(event.count, 20)
        )
        _require(
            all(
                _integer(n, event.first_observed_line, event.last_observed_line)
                for n in event.line_numbers
            )
        )
        _require(
            event.line_numbers == tuple(sorted(set(event.line_numbers)))
            and event.line_numbers[0] == event.first_observed_line
        )
        _require(event.count <= event.last_observed_line - event.first_observed_line + 1)
        if event.count <= 20:
            _require(event.line_numbers[-1] == event.last_observed_line)
        if event.first_seen is None:
            _require(event.last_seen is None)
        else:
            _require(_time(event.first_seen) <= _time(event.last_seen))
        _require(
            type(event.redacted_excerpts) is tuple and len(event.redacted_excerpts) <= MAX_EXCERPTS
        )
        _require(
            all(
                isinstance(value, str) and value in SAFE_EXCERPTS
                for value in event.redacted_excerpts
            )
        )
        _require(len(event.redacted_excerpts) <= event.count)
    doctor = report.doctor
    _require(type(doctor) is DoctorSummary and type(doctor.included) is bool)
    _require(all(_integer(count, 0, 1_048_576) for count in asdict(doctor.check_counts).values()))
    if doctor.included:
        _require(type(doctor.schema_version) is int and doctor.schema_version == 1)
        _require(
            doctor.overall_status is None or doctor.overall_status in ("ok", "warning", "fail")
        )
        _require(
            doctor.codex_version is None
            or (
                isinstance(doctor.codex_version, str)
                and _VERSION.fullmatch(doctor.codex_version) is not None
            )
        )
    else:
        _require(doctor.schema_version is doctor.overall_status is doctor.codex_version is None)
        _require(not any(asdict(doctor.check_counts).values()))
    privacy = report.privacy
    _require(privacy.raw_log_embedded is False and privacy.manual_review_required is True)
    _require(
        type(privacy.redacted_excerpts_included) is bool
        and privacy.redacted_excerpts_included == any(e.redacted_excerpts for e in report.events)
    )


def _bounded(text: str) -> str:
    if len(text.encode("utf-8")) > MAX_REPORT_BYTES:
        raise ValueError("Report exceeds the output byte limit.")
    return text


def render_json(report: DiagnosticReport) -> str:
    """Stable JSON, with no non-finite numbers or arbitrary extra fields."""
    validate_report(report)
    text = json.dumps(asdict(report), indent=2, ensure_ascii=True, allow_nan=False) + "\n"
    json.loads(text)
    return _bounded(text)


def escape_markdown(value: str) -> str:
    """Escape all dynamic text even when already restricted to safe metadata."""
    text = html.escape(clean_controls(value), quote=True)
    return re.sub(r"([\\`*_{}\[\]()#+.!|~>\-])", r"\\\1", text)


def render_markdown(report: DiagnosticReport) -> str:
    """Fixed structure and empty human-authored reproduction placeholders."""
    validate_report(report)
    summary = report.summary
    lines = [
        "# Diagnostic issue report",
        "",
        "> **MANUAL REVIEW REQUIRED — Review before sharing.**",
        "",
        "Unknown private information may remain. Inspect this draft before disclosure.",
        "Independent project; not affiliated with or endorsed by OpenAI.",
        "Symptoms are observed text, not a verified diagnosis.",
        "",
        "## Environment",
        "",
        f"- Client: {escape_markdown(report.source.client.value)}",
        f"- Generator: WinAgent ReproPack {escape_markdown(report.generator.version)}",
        "",
        "## Observed symptom summary",
        "",
        f"- Total lines: {summary.total_lines}",
        f"- Matched event lines: {summary.matched_event_lines}",
        f"- Unknown or incomparable timestamp lines: {summary.unknown_timestamp_lines}",
        f"- Local/unzoned timestamp lines (timezone unknown): {summary.timezone_unknown_lines}",
        f"- Multiple-category lines counted once: {summary.ambiguous_event_lines}",
        "",
        "| Category | Count | First line | Last line | Saved line numbers | "
        "First seen | Last seen |",
        "| --- | ---: | ---: | ---: | --- | --- | --- |",
    ]
    for event in report.events:
        first = (
            escape_markdown(event.first_seen) if event.first_seen else "unknown / timezone unknown"
        )
        last = escape_markdown(event.last_seen) if event.last_seen else "unknown / timezone unknown"
        numbers = ", ".join(str(n) for n in event.line_numbers)
        lines.append(
            f"| {escape_markdown(event.type.value)} | {event.count} | "
            f"{event.first_observed_line} | {event.last_observed_line} | {numbers} | "
            f"{first} | {last} |"
        )
    if not report.events:
        lines += [
            "",
            "No supported symptom patterns matched. This does not prove absence of faults.",
        ]
    lines += [
        "",
        "Time bounds require comparable explicit offsets for every event in a category.",
        "Saved line numbers are capped at 20; counts and last observed line remain complete.",
        "",
        "## Doctor summary",
        "",
    ]
    doctor = report.doctor
    if doctor.included:
        lines += [
            f"- Included: yes; schema: {doctor.schema_version}",
            f"- Codex version: {escape_markdown(doctor.codex_version or 'not provided')}",
            f"- Overall status: {escape_markdown(doctor.overall_status or 'not provided')}",
            f"- Checks: ok={doctor.check_counts.ok}, warning={doctor.check_counts.warning}, "
            f"fail={doctor.check_counts.fail}",
        ]
    else:
        lines.append("Doctor data not included. No automatic diagnostic command was run.")
    lines += ["", "## Optional sanitized symptom fragments", ""]
    if report.privacy.redacted_excerpts_included:
        lines += ["Opt-in canonical fragments only; arbitrary surrounding context was omitted.", ""]
        for event in report.events:
            for index, sample in enumerate(event.redacted_excerpts, 1):
                lines.append(
                    f"- {escape_markdown(event.type.value)} sample {index}: "
                    f"{escape_markdown(sample)}"
                )
    else:
        lines.append("No excerpts included.")
    for title in ("Steps to reproduce", "Expected behavior", "Actual behavior", "What I tried"):
        lines += ["", f"## {title}", "", "[USER TO FILL]"]
    lines += [
        "",
        "## Limits and privacy checklist",
        "",
        "- Regex matches only some known symptoms and may miss or misclassify other formats.",
        "- No inferred cause, global outage, severity, subscription or fix is established.",
        "- [ ] Inspect names, paths, URLs, credentials and proprietary information.",
        "- [ ] Fill in only reproduction details you can personally verify.",
        "- [ ] Remove anything you do not intend to disclose.",
        "",
        "**MANUAL REVIEW REQUIRED — Review before sharing.**",
        "",
    ]
    return _bounded("\n".join(lines))
