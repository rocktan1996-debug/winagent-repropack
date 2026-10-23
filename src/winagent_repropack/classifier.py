"""Deterministic symptom matching without root-cause inference."""

import re

from winagent_repropack.models import EventType

_RULES = (
    (EventType.REMOTE_COMPACT_FAILURE, r"\berror running remote compact task\b"),
    (
        EventType.STREAM_DISCONNECT,
        r"\bstream disconnected before completion\b|"
        r"\bpeer closed connection without sending TLS close_notify\b|"
        r"\berror decoding response body\b",
    ),
    (EventType.CAPACITY, r"\bselected model is at capacity\b|\bserver_overloaded\b"),
    (
        EventType.HTTP_503,
        r"\bHTTP\s+503(?!\w|\.[0-9])|"
        r"\bstatus code:\s*503(?!\w|\.[0-9])|"
        r"(?<![\w.])503\s+Service Unavailable\b",
    ),
    (EventType.RECONNECT_LOOP, r"\breconnecting\s+[0-9]+/[0-9]+\b"),
)
_PATTERNS = tuple((kind, re.compile(pattern, re.IGNORECASE)) for kind, pattern in _RULES)
_TIMED_OUT = re.compile(r"\btimed out\b", re.IGNORECASE)
_TIMEOUT = re.compile(r"\btimeout\b", re.IGNORECASE)
_CONFIG_VALUE = re.compile(
    r"\s*(?:=|:)\s*[0-9]+(?:\.[0-9]+)?"
    r"(?:\s*(?:ns|us|\u00b5s|ms|milliseconds?|msecs?|s|seconds?|secs?|"
    r"m|minutes?|mins?|h|hours?|hrs?))?(?!\w|\.[0-9])",
    re.IGNORECASE,
)
_FAILURE = re.compile(r"\b(?:error|failed|failure|exception|expired|exceeded|aborted)\b", re.I)


def matching_categories(line: str) -> tuple[EventType, ...]:
    """Return each matching category once, in the contractual priority order."""
    matches = tuple(kind for kind, pattern in _PATTERNS if pattern.search(line))
    # Exclude each numeric assignment, not the entire line: a separate failure
    # phrase on the same line must still count. These are limited symptom rules.
    failure_timeout = any(
        not _CONFIG_VALUE.match(line, token.end()) for token in _TIMEOUT.finditer(line)
    )
    if _TIMED_OUT.search(line) or (failure_timeout and _FAILURE.search(line)):
        matches += (EventType.TIMEOUT,)
    return matches


def classify_line(line: str) -> EventType | None:
    """Return at most one primary observed symptom for a line."""
    matches = matching_categories(line)
    return matches[0] if matches else None
