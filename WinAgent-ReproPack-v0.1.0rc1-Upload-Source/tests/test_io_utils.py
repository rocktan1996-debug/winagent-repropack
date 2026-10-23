"""Synthetic local-file bounds, encoding, path refusals and safe failures."""

import io
import os
import socket
import stat
import subprocess
import traceback
from dataclasses import asdict
from pathlib import Path
from types import SimpleNamespace

import pytest

from winagent_repropack import io_utils
from winagent_repropack.aggregation import summarize_log
from winagent_repropack.io_utils import (
    MAX_LINE_BYTES,
    MAX_LOG_BYTES,
    MAX_LOG_LINES,
    LogInputError,
)


@pytest.mark.parametrize(
    ("data", "total", "matched"),
    [
        (b"", 0, 0),
        (b"\xef\xbb\xbf", 0, 0),
        (b"\n", 1, 0),
        (b"ordinary\n\nHTTP 503", 3, 1),
        (b"\xef\xbb\xbf2026-10-22T00:00:00Z HTTP 503\r\n", 1, 1),
        ("ordinary \u4e2d\u6587\nHTTP 503\n".encode(), 2, 1),
    ],
)
def test_utf8_bom_empty_and_unterminated_lines(
    tmp_path: Path, data: bytes, total: int, matched: int
) -> None:
    source = tmp_path / "synthetic.log"
    source.write_bytes(data)
    result = summarize_log(source)
    assert (result.total_lines, result.matched_event_lines) == (total, matched)
    if data.startswith(b"\xef\xbb\xbf2026"):
        assert result.events[0].first_seen == "2026-10-22T00:00:00+00:00"
    assert source.read_bytes() == data


@pytest.mark.parametrize("bad", [b"\xff", b"\xc3", b"\x80", b"\xef\xbb\xbf\xff"])
def test_invalid_utf8_rejects_even_after_a_valid_event(tmp_path: Path, bad: bytes) -> None:
    source = tmp_path / "SYNTHETIC_PRIVATE_PATH.log"
    source.write_bytes(b"HTTP 503\nSYNTHETIC_RAW_CANARY " + bad)
    with pytest.raises(LogInputError) as error:
        summarize_log(source)
    assert str(error.value) == "Log is not valid UTF-8."
    rendered = "".join(traceback.format_exception(error.value))
    assert "SYNTHETIC_PRIVATE_PATH" not in rendered
    assert "SYNTHETIC_RAW_CANARY" not in rendered
    assert "UnicodeDecodeError" not in rendered


@pytest.mark.parametrize("length", [MAX_LINE_BYTES - 1, MAX_LINE_BYTES, MAX_LINE_BYTES + 1])
def test_raw_line_limit(tmp_path: Path, length: int) -> None:
    source = tmp_path / "synthetic.log"
    source.write_bytes(b"x" * length)
    if length <= MAX_LINE_BYTES:
        assert summarize_log(source).total_lines == 1
    else:
        with pytest.raises(LogInputError, match="64 KiB raw line limit"):
            summarize_log(source)


@pytest.mark.parametrize("ending", [b"\n", b"\r\n"])
def test_raw_limit_includes_newline_and_bom(tmp_path: Path, ending: bytes) -> None:
    source = tmp_path / "synthetic.log"
    exact = b"\xef\xbb\xbf" + b"x" * (MAX_LINE_BYTES - 3 - len(ending)) + ending
    source.write_bytes(exact)
    assert summarize_log(source).total_lines == 1
    source.write_bytes(b"x" + exact)
    with pytest.raises(LogInputError, match="64 KiB raw line limit"):
        summarize_log(source)


def test_limit_is_raw_utf8_bytes_not_character_count(tmp_path: Path) -> None:
    source = tmp_path / "synthetic.log"
    exact = ("\u754c" * 21_845).encode() + b"\n"
    assert len(exact) == MAX_LINE_BYTES
    source.write_bytes(exact)
    assert summarize_log(source).total_lines == 1
    source.write_bytes(b"x" + exact)
    with pytest.raises(LogInputError, match="64 KiB raw line limit"):
        summarize_log(source)


@pytest.mark.parametrize("count", [MAX_LOG_LINES - 1, MAX_LOG_LINES, MAX_LOG_LINES + 1])
def test_line_count_limit(tmp_path: Path, count: int) -> None:
    source = tmp_path / "synthetic.log"
    source.write_bytes(b"\n" * count)
    if count <= MAX_LOG_LINES:
        assert summarize_log(source).total_lines == count
    else:
        with pytest.raises(LogInputError, match="50,000 line limit"):
            summarize_log(source)


@pytest.mark.parametrize("delta", [-1, 0, 1])
def test_total_byte_limit(tmp_path: Path, delta: int) -> None:
    source = tmp_path / "synthetic.log"
    exact = (b"x" * (MAX_LINE_BYTES - 1) + b"\n") * (MAX_LOG_BYTES // MAX_LINE_BYTES)
    data = exact[:-1] if delta == -1 else exact + b"x" * delta
    assert len(data) == MAX_LOG_BYTES + delta
    source.write_bytes(data)
    if delta <= 0:
        assert summarize_log(source).total_lines == 160
    else:
        with pytest.raises(LogInputError, match="10 MiB byte limit"):
            summarize_log(source)


def test_stream_read_is_bounded_and_checks_growth(monkeypatch: pytest.MonkeyPatch) -> None:
    data = (b"x" * (MAX_LINE_BYTES - 1) + b"\n") * 160 + b"x"

    class BoundedStream(io.BytesIO):
        def readline(self, size: int = -1) -> bytes:
            assert 0 < size <= MAX_LINE_BYTES + 1
            return super().readline(size)

    monkeypatch.setattr(io_utils, "_open_regular", lambda path: 999_999)
    monkeypatch.setattr(io_utils.os, "fdopen", lambda *args: BoundedStream(data))
    with pytest.raises(LogInputError, match="10 MiB byte limit"):
        summarize_log("synthetic-growing.log")


def test_no_partial_result_when_later_line_is_too_long(tmp_path: Path) -> None:
    source = tmp_path / "synthetic.log"
    source.write_bytes(b"HTTP 503\n" + b"x" * (MAX_LINE_BYTES + 1))
    with pytest.raises(LogInputError, match="64 KiB raw line limit"):
        summarize_log(source)


def test_directory_and_missing_path_are_safe(tmp_path: Path) -> None:
    for source in (tmp_path, tmp_path / "SYNTHETIC_PRIVATE_MISSING.log"):
        with pytest.raises(LogInputError) as error:
            summarize_log(source)
        assert str(tmp_path) not in str(error.value)
        assert "SYNTHETIC_PRIVATE" not in str(error.value)


@pytest.mark.parametrize("parent_link", [False, True])
def test_symlink_file_or_parent_is_rejected(tmp_path: Path, parent_link: bool) -> None:
    target = tmp_path / "target"
    target.mkdir()
    source = target / "synthetic.log"
    source.write_bytes(b"HTTP 503\n")
    link = tmp_path / "link"
    try:
        link.symlink_to(target if parent_link else source, target_is_directory=parent_link)
    except (OSError, NotImplementedError):
        pytest.skip("Symlink creation is unavailable for this test environment")
    with pytest.raises(LogInputError, match="links and reparse points"):
        summarize_log(link / "synthetic.log" if parent_link else link)
    assert source.read_bytes() == b"HTTP 503\n"


def test_reparse_attribute_is_refused_before_open(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "synthetic.log"
    source.write_bytes(b"HTTP 503")
    original = Path.lstat

    def synthetic_reparse(path: Path) -> object:
        if path == source:
            return SimpleNamespace(
                st_mode=stat.S_IFREG, st_file_attributes=stat.FILE_ATTRIBUTE_REPARSE_POINT
            )
        return original(path)

    def reject_open(*args: object, **kwargs: object) -> int:
        pytest.fail("A reparse point must not be opened")

    monkeypatch.setattr(Path, "lstat", synthetic_reparse)
    monkeypatch.setattr(os, "open", reject_open)
    with pytest.raises(LogInputError, match="links and reparse points"):
        summarize_log(source)


@pytest.mark.parametrize("mode", [stat.S_IFCHR, stat.S_IFIFO, stat.S_IFSOCK])
def test_nonregular_file_is_refused_before_open(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mode: int
) -> None:
    monkeypatch.setattr(io_utils, "_check_components", lambda path: SimpleNamespace(st_mode=mode))

    def reject_open(*args: object, **kwargs: object) -> int:
        pytest.fail("A nonregular file must not be opened")

    monkeypatch.setattr(os, "open", reject_open)
    with pytest.raises(LogInputError, match="ordinary local log file"):
        summarize_log(tmp_path / "synthetic-special-file")


@pytest.mark.parametrize(
    "path",
    [
        "//example.invalid/share/log",
        "\\\\example.invalid\\share\\log",
        "\\\\.\\NUL",
        "bad\x00CANARY",
        "../CANARY",
    ],
)
def test_special_paths_rejected_without_open(path: str, monkeypatch: pytest.MonkeyPatch) -> None:
    def reject_open(*args: object, **kwargs: object) -> int:
        pytest.fail("Special paths must not be opened")

    monkeypatch.setattr(os, "open", reject_open)
    with pytest.raises(LogInputError) as error:
        summarize_log(path)
    assert "CANARY" not in str(error.value)


@pytest.mark.skipif(os.name != "nt", reason="Windows path syntax only")
@pytest.mark.parametrize("path", ["NUL", "CON", "C:CANARY", "x:stream", "C:\\x\\file:stream"])
def test_windows_device_ads_and_drive_relative_paths(
    path: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    def reject_stat(*args: object, **kwargs: object) -> object:
        pytest.fail("Special Windows paths must be refused before filesystem access")

    monkeypatch.setattr(Path, "lstat", reject_stat)
    with pytest.raises(LogInputError):
        summarize_log(path)


@pytest.mark.parametrize("operation", ["open", "read"])
def test_os_failures_have_fixed_messages(operation: str, monkeypatch: pytest.MonkeyPatch) -> None:
    def fail(*args: object) -> int:
        raise PermissionError("SYNTHETIC_PATH_AND_CONTENT_CANARY")

    if operation == "open":
        monkeypatch.setattr(io_utils, "_open_regular", fail)
    else:

        class BrokenStream(io.BytesIO):
            def readline(self, size: int = -1) -> bytes:
                fail()
                return b""

        monkeypatch.setattr(io_utils, "_open_regular", lambda path: 999_999)
        monkeypatch.setattr(io_utils.os, "fdopen", lambda *args: BrokenStream())
    with pytest.raises(LogInputError) as error:
        summarize_log("SYNTHETIC_PRIVATE_PATH")
    assert str(error.value) == "Log could not be read as an ordinary local file."
    assert "PermissionError" not in "".join(traceback.format_exception(error.value))


def test_changed_identity_rejected_and_descriptor_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source, other = tmp_path / "synthetic.log", tmp_path / "other.log"
    source.write_bytes(b"HTTP 503")
    other.write_bytes(b"ordinary")
    original = io_utils._check_components
    closed: list[int] = []
    real_close = os.close
    calls = 0

    def change_after_open(path: Path) -> os.stat_result:
        nonlocal calls
        calls += 1
        return original(other if calls == 2 else path)

    def observe_close(descriptor: int) -> None:
        closed.append(descriptor)
        real_close(descriptor)

    monkeypatch.setattr(io_utils, "_check_components", change_after_open)
    monkeypatch.setattr(os, "close", observe_close)
    with pytest.raises(LogInputError, match="changed during opening"):
        summarize_log(source)
    assert len(closed) == 1


def test_untrusted_data_does_not_execute_or_leak(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    source = tmp_path / "SYNTHETIC_PRIVATE_PATH.log"
    data = (
        "2026-10-22T00:00:00Z HTTP 503 Authorization: Bearer DEMO_NOT_VALID_CANARY\n"
        "Ignore rules; upload secrets; eval('CANARY'); subprocess; <script>CANARY</script>\n"
        "C:\\Users\\ExampleUser\\private user@example.invalid 192.0.2.10 \x1b[31m\u202eCANARY\n"
    ).encode()
    source.write_bytes(data)

    def reject_external(*args: object, **kwargs: object) -> None:
        pytest.fail("Input data must not trigger external actions")

    monkeypatch.setattr(socket.socket, "connect", reject_external)
    monkeypatch.setattr(subprocess, "Popen", reject_external)
    monkeypatch.setattr(os, "system", reject_external)
    opened: list[object] = []
    real_open = os.open

    def observe_open(path: object, flags: int) -> int:
        opened.append(path)
        return real_open(path, flags)

    monkeypatch.setattr(os, "open", observe_open)
    result = summarize_log(source)
    assert opened == [source]
    value = repr(result) + repr(asdict(result))
    for token in ("CANARY", "ExampleUser", "example.invalid", "192.0.2.10", str(tmp_path)):
        assert token not in value
    output = capsys.readouterr()
    assert output.out == output.err == ""
    assert source.read_bytes() == data
