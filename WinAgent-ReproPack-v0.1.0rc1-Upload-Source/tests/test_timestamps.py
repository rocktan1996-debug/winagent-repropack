"""Strict timestamp grammar and explicit timezone uncertainty."""

import pytest

from winagent_repropack.timestamps import TimestampStatus, parse_timestamp


@pytest.mark.parametrize(
    ("text", "canonical"),
    [
        ("2026-10-22T01:02:03Z", "2026-10-22T01:02:03+00:00"),
        ("2026-10-22T01:02:03.123+08:00", "2026-10-22T01:02:03.123000+08:00"),
        ("2026-10-22T01:02:03.1-07:00", "2026-10-22T01:02:03.100000-07:00"),
        ("2026-10-22T01:02:03.12Z", "2026-10-22T01:02:03.120000+00:00"),
        ("2024-02-29T00:00:00+00:00", "2024-02-29T00:00:00+00:00"),
        ("2026-10-22T01:02:03-00:00", "2026-10-22T01:02:03+00:00"),
    ],
)
def test_aware_iso_prefix(text: str, canonical: str) -> None:
    for suffix in ("", " event", "\tevent", "\r\n"):
        parsed = parse_timestamp(text + suffix)
        assert parsed.status == TimestampStatus.AWARE
        assert parsed.value is not None
        assert parsed.value.isoformat() == canonical


@pytest.mark.parametrize("fraction", ["", ".123"])
def test_unzoned_is_not_assigned_a_timezone(fraction: str) -> None:
    parsed = parse_timestamp(f"2026-10-22T01:02:03{fraction} error")
    assert parsed.status == TimestampStatus.TIMEZONE_UNKNOWN
    assert parsed.value is not None and parsed.value.tzinfo is None


@pytest.mark.parametrize(
    "text",
    [
        "",
        "10/22/2026 01:02:03",
        "2026-10-22",
        "2026-10-22 01:02:03Z",
        "2026-02-29T01:02:03Z",
        "2026-13-22T01:02:03Z",
        "2026-10-32T01:02:03Z",
        "2026-10-22T24:00:00Z",
        "2026-10-22T01:60:00Z",
        "2026-10-22T01:02:60Z",
        "2026-10-22T01:02:03+24:00",
        "2026-10-22T01:02:03+08:60",
        "2026-10-22T01:02:03-25:00",
        "2026-10-22T01:02:03+0800",
        "2026-10-22T01:02:03Z<script>",
        "2026-10-22T01:02:03ZCANARY",
        "2026-10-22T01:02:03.1234Z",
        "2026-10-22T01:02:03.Z",
        "2026-10-22t01:02:03z",
        "2026-10-22T01:02:03 UTC",
        " 2026-10-22T01:02:03Z",
        "[2026-10-22T01:02:03Z]",
        "２０２６-10-22T01:02:03Z",
    ],
)
def test_invalid_and_unsupported_prefixes(text: str) -> None:
    # A naive ISO prefix followed by a separate word is still a valid naive time.
    if text.endswith(" UTC"):
        assert parse_timestamp(text).status == TimestampStatus.TIMEZONE_UNKNOWN
    else:
        result = parse_timestamp(text)
        assert result.status == TimestampStatus.UNKNOWN
        assert result.value is None
