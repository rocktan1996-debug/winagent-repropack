"""R1-01: numeric configuration fields are not timeout failure evidence."""

import pytest

from winagent_repropack.classifier import classify_line, matching_categories
from winagent_repropack.models import EventType


@pytest.mark.parametrize(
    "line",
    [
        "Error: default timeout=30 configured; retry pending",
        "Error: timeout: 30 seconds configured",
        "2026-10-22T00:00:00Z Error reading config; timeout=30 (setting)",
    ],
)
def test_timeout_setting_is_not_failure(line: str) -> None:
    assert classify_line(line) is None


@pytest.mark.parametrize(
    "line",
    [
        "request failed: timeout",
        "operation timed out",
        "Timeout exception",
        "timeout=30 configured; request failed: timeout",
        "timeout: 30 seconds configured; operation timed out",
    ],
)
def test_actual_timeout_is_still_failure(line: str) -> None:
    assert classify_line(line) == EventType.TIMEOUT


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
def test_timeout_setting_preserves_priority(prefix: str, expected: EventType) -> None:
    line = f"{prefix}; Error: timeout=30 configured"
    assert classify_line(line) == expected
    assert EventType.TIMEOUT not in matching_categories(line)
