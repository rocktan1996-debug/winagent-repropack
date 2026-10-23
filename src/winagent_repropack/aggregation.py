"""Pure bounded aggregation and its explicit single-file adapter."""

from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from winagent_repropack.classifier import matching_categories
from winagent_repropack.io_utils import MAX_LOG_LINES, LogInputError, _read_log_lines
from winagent_repropack.models import (
    EventSummary,
    EventType,
    LogAnalysis,
    LogSummary,
    SafeExcerpts,
    WarningCounts,
)
from winagent_repropack.privacy import MAX_EXCERPTS, safe_excerpt
from winagent_repropack.timestamps import TimestampStatus, parse_timestamp

MAX_SAVED_LINE_NUMBERS = 20


@dataclass(slots=True)
class _EventAccumulator:
    count: int = 0
    first_line: int = 0
    last_line: int = 0
    first_time: datetime | None = None
    last_time: datetime | None = None
    comparable: bool = True
    line_numbers: list[int] = field(default_factory=list)

    def add(self, number: int, time: datetime | None) -> None:
        self.count += 1
        if self.count == 1:
            self.first_line = number
        self.last_line = number
        if len(self.line_numbers) < MAX_SAVED_LINE_NUMBERS:
            self.line_numbers.append(number)
        if time is None:
            self.comparable = False
            self.first_time = self.last_time = None
        elif self.comparable:
            self.first_time = time if self.first_time is None else min(self.first_time, time)
            self.last_time = time if self.last_time is None else max(self.last_time, time)

    def summary(self, kind: EventType) -> EventSummary:
        return EventSummary(
            type=kind,
            count=self.count,
            first_observed_line=self.first_line,
            last_observed_line=self.last_line,
            first_seen=self.first_time.isoformat() if self.first_time else None,
            last_seen=self.last_time.isoformat() if self.last_time else None,
            line_numbers=tuple(self.line_numbers),
        )


def _analyze_lines(lines: Iterable[str], include_excerpts: bool = False) -> LogAnalysis:
    groups: dict[EventType, _EventAccumulator] = {}
    samples: dict[EventType, list[str]] = {}
    total = matched = unknown = unzoned = ambiguous = 0
    for total, line in enumerate(lines, start=1):
        if total > MAX_LOG_LINES:
            raise LogInputError("Log exceeds the 50,000 line limit.")
        timestamp = parse_timestamp(line)
        aware = timestamp.status == TimestampStatus.AWARE
        unknown += int(not aware)
        unzoned += int(timestamp.status == TimestampStatus.TIMEZONE_UNKNOWN)
        matches = matching_categories(line)
        if matches:
            matched += 1
            ambiguous += int(len(matches) > 1)
            group = groups.setdefault(matches[0], _EventAccumulator())
            group.add(total, timestamp.value if aware else None)
            if include_excerpts:
                selected = samples.setdefault(matches[0], [])
                if len(selected) < MAX_EXCERPTS:
                    selected.append(safe_excerpt(line, matches[0]))
    summary = LogSummary(
        total_lines=total,
        matched_event_lines=matched,
        unknown_timestamp_lines=unknown,
        events=tuple(groups[kind].summary(kind) for kind in EventType if kind in groups),
        warnings=WarningCounts(ambiguous_event_lines=ambiguous, timezone_unknown_lines=unzoned),
    )
    return LogAnalysis(
        summary,
        tuple(SafeExcerpts(kind, tuple(samples[kind])) for kind in EventType if kind in samples),
    )


def aggregate_lines(lines: Iterable[str]) -> LogSummary:
    """Summarize already decoded/bounded lines without I/O or source retention.

    Production callers use summarize_log for byte/encoding/path validation. The
    timestamp warning counters include all input lines, including unmatched ones.
    """
    return _analyze_lines(lines).summary


def summarize_log(path: str | Path) -> LogSummary:
    """Read only the explicitly selected log and return aggregate-only data."""
    return aggregate_lines(_read_log_lines(path))


def analyze_log(path: str | Path, *, include_excerpts: bool = False) -> LogAnalysis:
    """Read exactly once; retain only aggregates and opt-in canonical fragments."""
    return _analyze_lines(_read_log_lines(path), include_excerpts)
