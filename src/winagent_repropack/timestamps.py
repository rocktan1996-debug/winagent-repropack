"""Strict ISO prefix parsing without guessing a timezone."""

import re
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

_ISO_PREFIX = re.compile(
    r"\A(?P<value>[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}"
    r"(?:\.[0-9]{1,3})?(?P<zone>Z|[+-][0-9]{2}:[0-9]{2})?)(?=$|[ \t\r\n])"
)


class TimestampStatus(StrEnum):
    """A fixed indication of whether absolute comparison is possible."""

    AWARE = "aware"
    TIMEZONE_UNKNOWN = "timezone unknown"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class ParsedTimestamp:
    """Validated datetime only; never retains the input string."""

    status: TimestampStatus
    value: datetime | None


def parse_timestamp(line: str) -> ParsedTimestamp:
    """Accept a column-one ISO timestamp, followed by whitespace or end-of-line.

    Fractions have one to three decimal places. Offset hours/minutes must be in
    00..23/00..59. Calendar fields are validated by datetime. Unsupported suffixes
    invalidate the prefix; no local timezone is consulted.
    """
    match = _ISO_PREFIX.match(line)
    if match is None:
        return ParsedTimestamp(TimestampStatus.UNKNOWN, None)
    zone = match["zone"]
    if zone and zone != "Z" and (int(zone[1:3]) > 23 or int(zone[4:6]) > 59):
        return ParsedTimestamp(TimestampStatus.UNKNOWN, None)
    try:
        value = datetime.fromisoformat(match["value"])
    except ValueError:
        return ParsedTimestamp(TimestampStatus.UNKNOWN, None)
    if zone is None:
        return ParsedTimestamp(TimestampStatus.TIMEZONE_UNKNOWN, value.replace(tzinfo=None))
    return ParsedTimestamp(TimestampStatus.AWARE, value)
