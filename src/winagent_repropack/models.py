"""Fixed, aggregate-only data structures; no source text or paths."""

from dataclasses import dataclass
from enum import StrEnum


class EventType(StrEnum):
    """Observed symptom labels in classification priority order."""

    REMOTE_COMPACT_FAILURE = "remote_compact_failure"
    STREAM_DISCONNECT = "stream_disconnect"
    CAPACITY = "capacity"
    HTTP_503 = "http_503"
    RECONNECT_LOOP = "reconnect_loop"
    TIMEOUT = "timeout"


@dataclass(frozen=True, slots=True)
class EventSummary:
    """One category, with complete counts and at most twenty source line numbers."""

    type: EventType
    count: int
    first_observed_line: int
    last_observed_line: int
    first_seen: str | None
    last_seen: str | None
    line_numbers: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class WarningCounts:
    """Safe warning counters; no dynamic warning messages from the input."""

    ambiguous_event_lines: int
    timezone_unknown_lines: int


@dataclass(frozen=True, slots=True)
class LogSummary:
    """Complete aggregate result, returned only after the input is fully validated."""

    total_lines: int
    matched_event_lines: int
    unknown_timestamp_lines: int
    events: tuple[EventSummary, ...]
    warnings: WarningCounts


@dataclass(frozen=True, slots=True)
class DoctorCheckCounts:
    """Fixed status counters, without dynamic check identifiers."""

    ok: int = 0
    warning: int = 0
    fail: int = 0


@dataclass(frozen=True, slots=True)
class DoctorSummary:
    """Allowlisted import result; omission differs from an empty checks map."""

    included: bool = False
    schema_version: int | None = None
    codex_version: str | None = None
    overall_status: str | None = None
    check_counts: DoctorCheckCounts = DoctorCheckCounts()


@dataclass(frozen=True, slots=True)
class SafeExcerpts:
    """At most three canonical symptom fragments for one fixed category."""

    type: EventType
    samples: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class LogAnalysis:
    """Single-pass aggregate result plus optional safe samples only."""

    summary: LogSummary
    excerpts: tuple[SafeExcerpts, ...] = ()


class ClientType(StrEnum):
    CODEX_CLI = "codex-cli"
    CODEX_DESKTOP = "codex-desktop"
    GENERIC = "generic"


@dataclass(frozen=True, slots=True)
class GeneratorInfo:
    name: str
    version: str


@dataclass(frozen=True, slots=True)
class SourceInfo:
    type: str
    client: ClientType


@dataclass(frozen=True, slots=True)
class ReportSummary:
    total_lines: int
    matched_event_lines: int
    unknown_timestamp_lines: int
    ambiguous_event_lines: int
    timezone_unknown_lines: int


@dataclass(frozen=True, slots=True)
class ReportEvent(EventSummary):
    redacted_excerpts: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class PrivacyInfo:
    raw_log_embedded: bool
    redacted_excerpts_included: bool
    manual_review_required: bool


@dataclass(frozen=True, slots=True)
class DiagnosticReport:
    """Versioned report data; excludes source paths and freeform input text."""

    schema_version: int
    generator: GeneratorInfo
    source: SourceInfo
    summary: ReportSummary
    events: tuple[ReportEvent, ...]
    doctor: DoctorSummary
    warnings: tuple[str, ...]
    privacy: PrivacyInfo
