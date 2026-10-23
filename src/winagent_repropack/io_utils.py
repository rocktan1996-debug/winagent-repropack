"""Read one explicit regular file, with hard bounds and fixed safe errors."""

import os
import stat
from collections.abc import Iterator
from pathlib import Path

MAX_LOG_BYTES = 10 * 1024 * 1024
MAX_LOG_LINES = 50_000
MAX_LINE_BYTES = 64 * 1024
_BOM = b"\xef\xbb\xbf"


class LogInputError(ValueError):
    """An input refusal whose message contains no source content or source path."""


def _check_components(path: Path) -> os.stat_result:
    """Reject symlinks and Windows reparse points on every path component."""
    for component in (*reversed(path.parents), path):
        info = component.lstat()
        if stat.S_ISLNK(info.st_mode) or (
            getattr(info, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT
        ):
            raise LogInputError("Log path links and reparse points are not supported.")
    return info


def _open_regular(path: str | Path) -> int:
    """Open read-only, reject special paths, and compare pre/post-open identity.

    Component checks are conservative checks, not an atomic filesystem snapshot.
    Callers must use a stable local file and stable ancestor directories.
    """
    value = os.fspath(path)
    if not isinstance(value, str) or value.startswith(("\\\\", "//")) or "\x00" in value:
        raise LogInputError("Select one ordinary local log file.")
    candidate = Path(value)
    if os.name == "nt":
        if candidate.drive and not candidate.root:
            raise LogInputError("Drive-relative log paths are not supported.")
        if any(
            ":" in part or Path(part).is_reserved()
            for part in candidate.parts
            if part != candidate.anchor
        ):
            raise LogInputError("Special log paths are not supported.")
        if not candidate.drive and ":" in value:
            raise LogInputError("Special log paths are not supported.")
    # Do not normalize away '..' before examining components that could be links.
    if ".." in candidate.parts:
        raise LogInputError("Parent traversal in log paths is not supported.")
    candidate = Path(os.path.abspath(candidate))
    before = _check_components(candidate)
    if not stat.S_ISREG(before.st_mode):
        raise LogInputError("Select one ordinary local log file.")
    if before.st_size > MAX_LOG_BYTES:
        raise LogInputError("Log exceeds the 10 MiB byte limit.")
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
    descriptor = os.open(candidate, flags)
    try:
        opened = os.fstat(descriptor)
        after = _check_components(candidate)
        if not stat.S_ISREG(opened.st_mode) or not os.path.samestat(before, opened):
            raise LogInputError("Log changed during opening; select a stable local file.")
        if not os.path.samestat(after, opened):
            raise LogInputError("Log changed during opening; select a stable local file.")
        return descriptor
    except BaseException:
        os.close(descriptor)
        raise


def _read_log_lines(path: str | Path) -> Iterator[str]:
    """Yield transient decoded lines; no raw text is kept in aggregate models.

    Raw byte limits include the BOM and CR/LF terminators. LF separates physical
    lines; a final unterminated line counts. Empty and BOM-only files have zero
    lines. Invalid UTF-8 is rejected. No partial summary is returned on failure.
    """
    try:
        descriptor = _open_regular(path)
        try:
            stream = os.fdopen(descriptor, "rb")
        except BaseException:
            os.close(descriptor)
            raise
        with stream:
            total_bytes = 0
            line_count = 0
            while True:
                raw = stream.readline(min(MAX_LINE_BYTES + 1, MAX_LOG_BYTES - total_bytes + 1))
                if not raw:
                    break
                total_bytes += len(raw)
                if total_bytes > MAX_LOG_BYTES:
                    raise LogInputError("Log exceeds the 10 MiB byte limit.")
                if len(raw) > MAX_LINE_BYTES:
                    raise LogInputError("Log exceeds the 64 KiB raw line limit.")
                first = line_count == 0
                if first and raw == _BOM:
                    break
                line_count += 1
                if line_count > MAX_LOG_LINES:
                    raise LogInputError("Log exceeds the 50,000 line limit.")
                yield raw.decode("utf-8-sig" if first else "utf-8")
    except UnicodeError:
        message = "Log is not valid UTF-8."
    except (OSError, ValueError, TypeError) as error:
        if isinstance(error, LogInputError):
            raise
        message = "Log could not be read as an ordinary local file."
    else:
        return
    # Leave the handler before raising: suppressing display with `from None`
    # alone would retain the raw decode/OS exception in __context__.
    raise LogInputError(message) from None
