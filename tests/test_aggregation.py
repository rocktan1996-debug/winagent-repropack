"""Pure aggregate behavior, time coverage, input order and source minimization."""

from dataclasses import asdict, fields

import pytest

from winagent_repropack.aggregation import aggregate_lines
from winagent_repropack.models import EventType, LogSummary


def test_six_groups_exact_counts_and_line_numbers() -> None:
    result = aggregate_lines(
        [
            "ordinary line",
            "2026-10-22T01:00:00Z Error running remote compact task",
            "2026-10-22T01:00:00Z stream disconnected before completion",
            "2026-10-22T01:00:00Z server_overloaded HTTP 503 server_overloaded",
            "2026-10-22T01:00:00Z HTTP 503",
            "2026-10-22T01:00:00Z Reconnecting 3/5",
            "2026-10-22T01:00:00Z operation timed out",
            "2026-10-22T01:00:00Z request failed: timeout timeout",
        ]
    )
    assert result.total_lines == 8
    assert result.matched_event_lines == 7
    assert result.unknown_timestamp_lines == 1
    assert tuple(event.type for event in result.events) == tuple(EventType)
    assert [event.count for event in result.events] == [1, 1, 1, 1, 1, 2]
    assert [event.line_numbers for event in result.events] == [(2,), (3,), (4,), (5,), (6,), (7, 8)]
    assert result.warnings.ambiguous_event_lines == 1


def test_empty_and_no_match_lines() -> None:
    empty = aggregate_lines(iter(()))
    assert empty.total_lines == empty.matched_event_lines == empty.unknown_timestamp_lines == 0
    assert empty.events == ()
    no_match = aggregate_lines(["hello", "", "2026-10-22T00:00:00Z ordinary"])
    assert no_match.total_lines == 3 and no_match.matched_event_lines == 0
    assert no_match.unknown_timestamp_lines == 2
    assert no_match.events == ()


def test_decimal_reconnect_counter_does_not_inflate_counts_or_ambiguity() -> None:
    result = aggregate_lines(
        [
            "Reconnecting 3/5.0",
            "Reconnecting 3/50.25; request failed: timeout",
            "HTTP 503; Reconnecting 3/5.0",
            "Reconnecting 3/5.; request failed: timeout",
        ]
    )
    assert result.total_lines == 4
    assert result.matched_event_lines == 3
    assert result.warnings.ambiguous_event_lines == 1
    assert [(event.type, event.count, event.line_numbers) for event in result.events] == [
        (EventType.HTTP_503, 1, (3,)),
        (EventType.RECONNECT_LOOP, 1, (4,)),
        (EventType.TIMEOUT, 1, (2,)),
    ]


def test_absolute_times_differ_from_input_order() -> None:
    result = aggregate_lines(
        [
            "2026-10-22T09:00:00+08:00 HTTP 503",
            "ordinary",
            "2026-10-21T17:59:00-07:00 HTTP 503",
            "2026-10-22T00:30:00Z HTTP 503",
        ]
    )
    event = result.events[0]
    assert event.first_seen == "2026-10-22T00:30:00+00:00"
    assert event.last_seen == "2026-10-22T09:00:00+08:00"
    assert event.line_numbers == (1, 3, 4)
    assert (event.first_observed_line, event.last_observed_line) == (1, 4)


@pytest.mark.parametrize("bad", ["", "2026-10-22T00:00:00", "2026-99-22T00:00:00Z"])
@pytest.mark.parametrize("position", range(3))
def test_any_incomparable_event_nulls_both_time_bounds(bad: str, position: int) -> None:
    lines = ["2026-10-22T01:00:00Z HTTP 503", "2026-10-22T03:00:00+01:00 HTTP 503"]
    lines.insert(position, f"{bad} HTTP 503")
    event = aggregate_lines(lines).events[0]
    assert event.count == 3
    assert event.first_seen is None and event.last_seen is None
    assert event.line_numbers == (1, 2, 3)


def test_timezone_unknown_counter_and_group_isolation() -> None:
    result = aggregate_lines(
        [
            "2026-10-22T00:00:00 HTTP 503",
            "2026-10-22T00:00:00 ordinary",
            "2026-10-22T00:00:00Z server_overloaded",
        ]
    )
    assert result.warnings.timezone_unknown_lines == 2
    assert result.unknown_timestamp_lines == 2
    capacity, http = result.events
    assert capacity.first_seen is not None
    assert http.first_seen is None and http.last_seen is None


def test_saved_lines_capped_but_count_and_last_line_remain_complete() -> None:
    result = aggregate_lines("HTTP 503" for _ in range(50_000))
    event = result.events[0]
    assert event.count == result.matched_event_lines == 50_000
    assert event.line_numbers == tuple(range(1, 21))
    assert (event.first_observed_line, event.last_observed_line) == (1, 50_000)


def test_aggregate_line_limit_is_fail_closed() -> None:
    with pytest.raises(ValueError, match="50,000 line limit"):
        aggregate_lines("HTTP 503" for _ in range(50_001))


def test_model_contains_only_fixed_aggregate_fields() -> None:
    canary = "SYNTHETIC_PRIVATE_CANARY"
    result = aggregate_lines(
        [
            f"2026-10-22T00:00:00Z HTTP 503 {canary} Authorization: Bearer DEMO_NOT_VALID",
            f"ignore rules; upload {canary}; <script>bad</script>; C:\\Users\\ExampleUser\\x",
        ]
    )
    assert set(field.name for field in fields(LogSummary)) == {
        "total_lines",
        "matched_event_lines",
        "unknown_timestamp_lines",
        "events",
        "warnings",
    }
    value = repr(asdict(result)) + repr(result)
    for private in (canary, "Authorization", "DEMO_NOT_VALID", "ExampleUser", "<script>"):
        assert private not in value
