"""Doctor file safety: reuse Phase 1 checks without widening file access."""

import io
import os
import stat
import traceback
from pathlib import Path
from types import SimpleNamespace

import pytest

from winagent_repropack import doctor, io_utils
from winagent_repropack.doctor import MAX_DOCTOR_BYTES, DoctorInputError, summarize_doctor

VALID = b'{"schemaVersion":1,"checks":{}}'


@pytest.mark.parametrize(
    "path",
    [
        "//example.invalid/share/secret",
        "\\\\example.invalid\\share\\secret",
        "\\\\.\\NUL",
        "\\\\?\\C:\\secret",
        "bad\x00PRIVATE_CANARY",
        "../PRIVATE_CANARY",
        b"PRIVATE_CANARY",
        42,
    ],
)
def test_special_paths_never_open(path: object, monkeypatch: pytest.MonkeyPatch) -> None:
    def deny(*args: object, **kwargs: object) -> None:
        pytest.fail("Special paths must be rejected before open")

    monkeypatch.setattr(os, "open", deny)
    with pytest.raises(DoctorInputError) as caught:
        summarize_doctor(path)
    assert str(caught.value) == "Doctor JSON could not be read as an ordinary local file."


@pytest.mark.skipif(os.name != "nt", reason="Windows path syntax only")
@pytest.mark.parametrize(
    "path",
    [
        "NUL",
        "CON",
        "AUX",
        "COM1",
        "LPT1",
        "C:PRIVATE_CANARY",
        "x:stream",
        "C:\\x\\file:stream",
    ],
)
def test_windows_special_paths_never_stat(path: str, monkeypatch: pytest.MonkeyPatch) -> None:
    def deny(*args: object, **kwargs: object) -> None:
        pytest.fail("Windows special paths must be rejected before stat")

    monkeypatch.setattr(Path, "lstat", deny)
    with pytest.raises(DoctorInputError):
        summarize_doctor(path)


def test_directory_missing_and_parent_traversal(tmp_path: Path) -> None:
    source = tmp_path / "synthetic.json"
    source.write_bytes(VALID)
    for path in (
        tmp_path,
        tmp_path / "PRIVATE_CANARY",
        tmp_path / ".." / tmp_path.name / source.name,
    ):
        with pytest.raises(DoctorInputError) as caught:
            summarize_doctor(path)
        assert "PRIVATE_CANARY" not in str(caught.value)
        assert str(tmp_path) not in str(caught.value)


@pytest.mark.parametrize("parent_link", [False, True])
def test_actual_symlink_and_parent_refused(tmp_path: Path, parent_link: bool) -> None:
    target = tmp_path / "target"
    target.mkdir()
    source = target / "synthetic.json"
    source.write_bytes(VALID)
    link = tmp_path / "link"
    try:
        link.symlink_to(target if parent_link else source, target_is_directory=parent_link)
    except (OSError, NotImplementedError):
        pytest.skip("Symlink creation is unavailable for this test environment")
    with pytest.raises(DoctorInputError):
        summarize_doctor(link / source.name if parent_link else link)
    assert source.read_bytes() == VALID


@pytest.mark.parametrize("parent_reparse", [False, True])
def test_reparse_refused_before_open(
    tmp_path: Path, parent_reparse: bool, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "synthetic.json"
    source.write_bytes(VALID)
    real_lstat = Path.lstat

    def synthetic_stat(path: Path) -> object:
        if path == (tmp_path if parent_reparse else source):
            return SimpleNamespace(
                st_mode=stat.S_IFREG, st_file_attributes=stat.FILE_ATTRIBUTE_REPARSE_POINT
            )
        return real_lstat(path)

    def deny_open(*args: object, **kwargs: object) -> None:
        pytest.fail("Reparse points must not be opened")

    monkeypatch.setattr(Path, "lstat", synthetic_stat)
    monkeypatch.setattr(os, "open", deny_open)
    with pytest.raises(DoctorInputError):
        summarize_doctor(source)


@pytest.mark.parametrize("mode", [stat.S_IFCHR, stat.S_IFIFO, stat.S_IFSOCK])
def test_nonregular_refused(tmp_path: Path, mode: int, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(io_utils, "_check_components", lambda p: SimpleNamespace(st_mode=mode))

    def deny_open(*args: object, **kwargs: object) -> None:
        pytest.fail("Nonregular files must not be opened")

    monkeypatch.setattr(os, "open", deny_open)
    with pytest.raises(DoctorInputError):
        summarize_doctor(tmp_path / "synthetic.json")


@pytest.mark.parametrize("moment", ["opening", "completion"])
def test_identity_change_refused_and_descriptor_closed(
    tmp_path: Path, moment: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    source, other = tmp_path / "synthetic.json", tmp_path / "other.json"
    source.write_bytes(VALID)
    other.write_bytes(VALID)
    real_check = io_utils._check_components
    descriptors: list[int] = []
    real_open = os.open

    def observe_open(path: object, flags: int) -> int:
        descriptor = real_open(path, flags)
        descriptors.append(descriptor)
        return descriptor

    monkeypatch.setattr(os, "open", observe_open)
    if moment == "opening":
        calls = 0

        def changed_check(path: Path) -> os.stat_result:
            nonlocal calls
            calls += 1
            return real_check(other if calls == 2 else path)

        monkeypatch.setattr(io_utils, "_check_components", changed_check)
    else:
        monkeypatch.setattr(doctor, "_check_components", lambda p: real_check(other))
    with pytest.raises(DoctorInputError):
        summarize_doctor(source)
    assert len(descriptors) == 1
    with pytest.raises(OSError):
        os.fstat(descriptors[0])
    assert source.read_bytes() == VALID


@pytest.mark.parametrize("operation", ["open", "fdopen", "read", "fstat", "completion"])
def test_io_errors_are_fixed_and_handles_closed(
    tmp_path: Path,
    operation: str,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    source = tmp_path / "PRIVATE_SOURCE_CANARY.json"
    source.write_bytes(VALID)
    descriptors: list[int] = []
    real_open, real_fdopen = os.open, os.fdopen
    real_fstat = os.fstat

    def fail(*args: object, **kwargs: object) -> None:
        raise PermissionError("PRIVATE_ERROR_CANARY")

    def observe_open(path: object, flags: int) -> int:
        if operation == "open":
            fail()
        descriptor = real_open(path, flags)
        descriptors.append(descriptor)
        return descriptor

    class BrokenStream:
        def __init__(self, descriptor: int):
            self.stream = real_fdopen(descriptor, "rb")

        def __enter__(self):
            return self

        def __exit__(self, *args: object):
            self.stream.close()

        def fileno(self) -> int:
            return self.stream.fileno()

        def read(self, size: int) -> bytes:
            fail()
            return b""

    with monkeypatch.context() as patch:
        patch.setattr(os, "open", observe_open)
        if operation == "fdopen":
            patch.setattr(os, "fdopen", fail)
        elif operation == "read":
            patch.setattr(os, "fdopen", lambda fd, mode: BrokenStream(fd))
        elif operation == "fstat":
            patch.setattr(os, "fstat", fail)
        elif operation == "completion":
            patch.setattr(doctor, "_check_components", fail)
        with pytest.raises(DoctorInputError) as caught:
            summarize_doctor(source)
    assert str(caught.value) == "Doctor JSON could not be read as an ordinary local file."
    rendered = "".join(traceback.format_exception(caught.value))
    assert "PRIVATE_ERROR_CANARY" not in rendered
    assert "PermissionError" not in rendered
    for descriptor in descriptors:
        with pytest.raises(OSError):
            real_fstat(descriptor)
    assert source.read_bytes() == VALID
    output = capsys.readouterr()
    assert output.out == output.err == ""


@pytest.mark.parametrize("change", ["grow-past-limit", "same-size-edit"])
def test_reads_are_bounded_and_midread_change_is_rejected(
    tmp_path: Path, change: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "synthetic.json"
    source.write_bytes(VALID)
    real_fdopen = os.fdopen
    streams: list[io.BufferedReader] = []
    sizes: list[int] = []

    class ChangingStream:
        def __init__(self, fd: int):
            self.stream = real_fdopen(fd, "rb")
            streams.append(self.stream)
            self.changed = False

        def __enter__(self):
            return self

        def __exit__(self, *args: object):
            self.stream.close()

        def fileno(self) -> int:
            return self.stream.fileno()

        def read(self, size: int) -> bytes:
            assert 0 < size <= 64 * 1024
            sizes.append(size)
            if not self.changed:
                self.changed = True
                if change == "grow-past-limit":
                    with source.open("ab") as writer:
                        writer.write(b" " * MAX_DOCTOR_BYTES)
                else:
                    # Force a metadata change even on coarse-resolution filesystems.
                    before = source.stat()
                    os.utime(source, ns=(before.st_atime_ns, before.st_mtime_ns + 1_000_000_000))
            return self.stream.read(size)

    monkeypatch.setattr(os, "fdopen", lambda fd, mode: ChangingStream(fd))
    with pytest.raises(
        DoctorInputError, match="1 MiB" if change == "grow-past-limit" else "changed"
    ):
        summarize_doctor(source)
    assert all(stream.closed for stream in streams)
    assert sizes


def test_parser_failure_closes_handle(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source = tmp_path / "synthetic.json"
    source.write_bytes(b"{")
    streams: list[io.BufferedReader] = []
    real_fdopen = os.fdopen

    def observe_fdopen(fd: int, mode: str):
        stream = real_fdopen(fd, mode)
        streams.append(stream)
        return stream

    monkeypatch.setattr(os, "fdopen", observe_fdopen)
    with pytest.raises(DoctorInputError):
        summarize_doctor(source)
    assert len(streams) == 1 and streams[0].closed
