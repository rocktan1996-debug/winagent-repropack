"""Synthetic symptom tokens, precedence, duplicates and negative cases."""

import pytest

from winagent_repropack.classifier import classify_line, matching_categories
from winagent_repropack.models import EventType

EXAMPLES = [
    "Error running remote compact task",
    "stream disconnected before completion",
    "server_overloaded",
    "HTTP 503",
    "Reconnecting 3/5",
    "Failed operation timed out",
]


@pytest.mark.parametrize("index", range(6))
def test_six_categories_and_repeated_words(index: int) -> None:
    kind = tuple(EventType)[index]
    text = f"{EXAMPLES[index].upper()} {EXAMPLES[index]}"
    assert classify_line(text) == kind
    assert matching_categories(text) == (kind,)


@pytest.mark.parametrize("first", range(6))
def test_all_lower_priority_combinations(first: int) -> None:
    for second in range(first + 1, 6):
        text = f"{EXAMPLES[second]} {EXAMPLES[first]}"
        assert classify_line(text) == tuple(EventType)[first]
        assert len(matching_categories(text)) == 2


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("peer closed connection without sending TLS close_notify", EventType.STREAM_DISCONNECT),
        ("error decoding response body", EventType.STREAM_DISCONNECT),
        ("Selected model is at capacity", EventType.CAPACITY),
        ("status code: 503", EventType.HTTP_503),
        ("status code:503", EventType.HTTP_503),
        ("503 Service Unavailable", EventType.HTTP_503),
        ("Reconnecting 5/5", EventType.RECONNECT_LOOP),
        ("request failed: timeout", EventType.TIMEOUT),
        ("Timeout exception", EventType.TIMEOUT),
        ("HTTP 503 server_overloaded", EventType.CAPACITY),
    ],
)
def test_documented_variants(text: str, expected: EventType) -> None:
    assert classify_line(text) == expected


@pytest.mark.parametrize(
    "text",
    [
        "",
        "ordinary informational line",
        "503",
        "HTTP 5030",
        "status code: 1503",
        "1503 Service Unavailable",
        "5030 Service Unavailable",
        "HTTP 503.0",
        "HTTP 503suffix",
        "Reconnecting",
        "Reconnecting soon",
        "Reconnecting 3",
        "timeout=30",
        "request timeout setting",
        "no failure tokens here",
        "server_overloaded_suffix",
        "prefix_server_overloaded",
        "timeouts configured",
    ],
)
def test_unmatched_and_token_boundaries(text: str) -> None:
    assert classify_line(text) is None
