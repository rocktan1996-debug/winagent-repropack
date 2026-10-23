"""Conservative opt-in samples: scrub transient text, emit fixed symptom phrases."""

import re
import unicodedata

from winagent_repropack.models import EventType

MAX_EXCERPTS = 3
MAX_EXCERPT_CHARS = 200
_OSC = re.compile(r"\x1b\][^\x07\x1b]*(?:\x07|\x1b\\|$)")
_CSI = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")
_ESC = re.compile(r"\x1b[ -/]*[@-~]")
_REDACTIONS = tuple(
    re.compile(pattern, re.I)
    for pattern in (
        r"\b(?:https?|ftp)://[^\s<>\"'`]+",
        r"\b[A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,}\b",
        r"(?:[A-Z]:[\\/](?:Users|Documents and Settings)[\\/]|/(?:home|Users)/)[^\s<>\"'`|]+",
        r"\b(?:authorization|api[_-]?key|access[_-]?token|refresh[_-]?token|token|password|passwd|"
        r"session[_-]?id)\b\s*[:=]\s*(?:\"[^\"]*\"|'[^']*'|(?:bearer\s+)?[^\s,;]+)",
        r"\bbearer\s+[^\s,;]+",
        r"\b(?:sk-|ghp_|gho_|github_pat_)[A-Z0-9_\-]+\b",
        r"(?<![\w.])(?:[0-9]{1,3}\.){3}[0-9]{1,3}(?![\w.])",
        r"(?<!\w)(?:[0-9A-F]{0,4}:){2,}[0-9A-F:.%]+",
        r"\b[A-Z0-9_\-]{32,}\b",
    )
)
_PHRASES: dict[EventType, tuple[str, ...]] = {
    EventType.REMOTE_COMPACT_FAILURE: ("Error running remote compact task",),
    EventType.STREAM_DISCONNECT: (
        "stream disconnected before completion",
        "peer closed connection without sending TLS close_notify",
        "error decoding response body",
    ),
    EventType.CAPACITY: ("Selected model is at capacity", "server_overloaded"),
    EventType.HTTP_503: ("HTTP 503", "status code: 503", "503 Service Unavailable"),
    EventType.RECONNECT_LOOP: ("Reconnecting (counter observed; context omitted)",),
    EventType.TIMEOUT: ("operation timed out", "timeout with failure context"),
}
SAFE_EXCERPTS = frozenset(phrase for phrases in _PHRASES.values() for phrase in phrases)


def clean_controls(text: str) -> str:
    """Strip terminal sequences and replace controls/formatting with plain spaces."""
    text = _ESC.sub("", _CSI.sub("", _OSC.sub("", text)))
    return "".join(
        " " if unicodedata.category(char) in {"Cc", "Cf", "Cs"} else char for char in text
    )


def redact_sensitive(text: str) -> str:
    """Scrub known patterns in transient text; never promises exhaustive redaction.

    This intermediate text is not a report field. The excerpt boundary below
    discards arbitrary context rather than trusting regex for unknown secrets.
    """
    cleaned = clean_controls(text)
    for pattern in _REDACTIONS:
        cleaned = pattern.sub("[REDACTED]", cleaned)
    return cleaned


def safe_excerpt(line: str, kind: EventType) -> str:
    """Return a fixed symptom fragment after cleaning, never arbitrary context.

    Opt-in examples are canonical fragments, not verbatim lines. This keeps useful
    rule evidence while omitting unknown business text, instructions and secrets.
    Redaction precedes the length limit; no secret is cut into a partial token.
    """
    cleaned = redact_sensitive(line).casefold()
    phrases = _PHRASES[kind]
    if kind == EventType.TIMEOUT:
        selected = phrases[0] if "timed out" in cleaned else phrases[1]
    else:
        selected = next((p for p in phrases if p.casefold() in cleaned), phrases[0])
    return selected[:MAX_EXCERPT_CHARS]
