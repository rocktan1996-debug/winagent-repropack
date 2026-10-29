"""Exclusive writes, aliases, path safety and ownership-constrained fault cleanup."""

import os
import stat
from pathlib import Path
from types import SimpleNamespace

import pytest

from winagent_repropack import output
from winagent_repropack.output import OutputPathError, write_report
from winagent_repropack.reports import MAX_REPORT_BYTES


def test_exclusive_new_output_and_short_writes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    target = tmp_path / "new.md"
    real_write = os.write
    calls = []

    def short_write(fd: int, data: bytes) -> int:
        calls.append(len(data))
        return real_write(fd, data[:3])

    monkeypatch.setattr(os, "write", short_write)
    write_report(target, "synthetic report", inputs=())
    assert target.read_bytes() == b"synthetic report"
    assert len(calls) > 1
    with pytest.raises(OutputPathError):
        write_report(target, "overwrite forbidden", inputs=())
    assert target.read_bytes() == b"synthetic report"


@pytest.mark.parametrize("kind", ["existing", "directory", "input", "hardlink", "absent-parent"])
def test_conflicts_and_parent_policy(tmp_path: Path, kind: str) -> None:
    source = tmp_path / "synthetic.log"
    source.write_bytes(b"SYNTHETIC_EXISTING_CANARY")
    target = tmp_path / "new.md"
    if kind == "existing":
        target.write_bytes(b"existing")
    elif kind == "directory":
        target.mkdir()
    elif kind == "input":
        target = source
    elif kind == "hardlink":
        os.link(source, target)
    else:
        target = tmp_path / "absent" / "new.md"
    before = target.read_bytes() if target.is_file() else None
    with pytest.raises(OutputPathError):
        write_report(target, "new report", inputs=(source,))
    assert source.read_bytes() == b"SYNTHETIC_EXISTING_CANARY"
    if before is not None:
        assert target.read_bytes() == before


@pytest.mark.parametrize(
    "path",
    ["//example.invalid/share/out", "\\\\.\\NUL", "../CANARY", "bad\x00CANARY", "", 123, b"CANARY"],
)
def test_special_paths_refused(path: object) -> None:
    with pytest.raises(OutputPathError) as caught:
        write_report(path, "safe", inputs=())
    assert "CANARY" not in str(caught.value)


@pytest.mark.skipif(os.name != "nt", reason="Windows path syntax only")
@pytest.mark.parametrize(
    "path",
    [
        "NUL",
        "CON",
        "C:CANARY",
        "x:stream",
        "C:\\x\\file:stream",
        "trailing.",
        "trailing ",
        "bad?name",
    ],
)
def test_windows_special_output_paths(path: str) -> None:
    with pytest.raises(OutputPathError):
        write_report(path, "safe", inputs=())


@pytest.mark.parametrize("parent_link", [False, True])
def test_output_symlink_and_ancestor_rejected(tmp_path: Path, parent_link: bool) -> None:
    directory = tmp_path / "real"
    directory.mkdir()
    protected = directory / "protected.md"
    protected.write_bytes(b"protected")
    link = tmp_path / "link"
    try:
        link.symlink_to(directory if parent_link else protected, target_is_directory=parent_link)
    except (OSError, NotImplementedError):
        pytest.skip("Symlink creation unavailable")
    with pytest.raises(OutputPathError):
        write_report(link / "new.md" if parent_link else link, "safe", inputs=())
    assert protected.read_bytes() == b"protected"
    assert not (directory / "new.md").exists()


def test_ancestor_reparse_or_non_directory_refused(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    original = Path.lstat
    for mode, attributes in [(stat.S_IFDIR, stat.FILE_ATTRIBUTE_REPARSE_POINT), (stat.S_IFREG, 0)]:

        def unsafe(path: Path):
            return (
                SimpleNamespace(st_mode=mode, st_file_attributes=attributes)
                if path == tmp_path
                else original(path)
            )

        with monkeypatch.context() as patch:
            patch.setattr(Path, "lstat", unsafe)
            with pytest.raises(OutputPathError):
                write_report(tmp_path / "new.md", "safe", inputs=())


def test_create_permission_error_is_safe(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    def denied(*args: object, **kwargs: object) -> None:
        raise PermissionError("PRIVATE_OS_CANARY")

    monkeypatch.setattr(os, "open", denied)
    with pytest.raises(OutputPathError) as caught:
        write_report(tmp_path / "new.md", "safe", inputs=())
    assert "PRIVATE_OS_CANARY" not in str(caught.value)


def test_late_existing_target_is_not_overwritten(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    target = tmp_path / "new.md"
    real_open = os.open

    def race(path: Path, flags: int, mode: int):
        assert flags & os.O_EXCL and flags & os.O_CREAT
        target.write_bytes(b"concurrent-existing")
        return real_open(path, flags, mode)

    monkeypatch.setattr(os, "open", race)
    with pytest.raises(OutputPathError):
        write_report(target, "safe", inputs=())
    assert target.read_bytes() == b"concurrent-existing"


@pytest.mark.parametrize("fault", ["partial-write", "zero-write", "fsync", "close", "interrupt"])
def test_owned_partial_output_cleanup(tmp_path: Path, fault: str, monkeypatch: pytest.MonkeyPatch):
    target = tmp_path / "new.md"
    real_write, real_close = os.write, os.close
    descriptors = []

    def write(fd: int, data: bytes):
        descriptors.append(fd)
        if fault == "zero-write":
            return 0
        real_write(fd, data[:3])
        if fault == "interrupt":
            raise KeyboardInterrupt()
        raise OSError("PRIVATE_WRITE_CANARY")

    def fail(*args: object):
        raise OSError("PRIVATE_WRITE_CANARY")

    if fault in {"partial-write", "zero-write", "interrupt"}:
        monkeypatch.setattr(os, "write", write)
    elif fault == "fsync":
        monkeypatch.setattr(os, "fsync", fail)
    else:
        calls = 0

        def close(fd: int):
            nonlocal calls
            calls += 1
            if calls == 1:
                fail()
            real_close(fd)

        monkeypatch.setattr(os, "close", close)
    with pytest.raises((OSError, KeyboardInterrupt)):
        write_report(target, "safe report", inputs=())
    assert not target.exists()
    for fd in descriptors:
        with pytest.raises(OSError):
            os.fstat(fd)


def test_cleanup_never_deletes_replacement_or_unsafe_parent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    target = tmp_path / "new.md"
    target.write_bytes(b"owned")
    original = target.stat()
    parents = output._parents(target)
    target.rename(tmp_path / "owned-moved.md")
    target.write_bytes(b"concurrent-existing")
    output._remove_owned(target, original, parents)
    assert target.read_bytes() == b"concurrent-existing"
    monkeypatch.setattr(output, "_parents_unchanged", lambda *args: False)
    output._remove_owned(target, target.stat(), parents)
    assert target.read_bytes() == b"concurrent-existing"
    output._remove_owned(target, None, parents)


def test_parent_race_fails_closed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    target = tmp_path / "new.md"
    original = output._parents_unchanged
    calls = 0

    def changed_once(*args):
        nonlocal calls
        calls += 1
        return False if calls == 1 else original(*args)

    monkeypatch.setattr(output, "_parents_unchanged", changed_once)
    with pytest.raises(OSError):
        write_report(target, "safe", inputs=())
    assert not target.exists()


def test_output_size_refused_before_creation(tmp_path: Path) -> None:
    target = tmp_path / "new.md"
    with pytest.raises(ValueError):
        write_report(target, "x" * (MAX_REPORT_BYTES + 1), inputs=())
    assert not target.exists()


def test_unidentifiable_created_file_is_not_deleted(tmp_path: Path, monkeypatch):
    target = tmp_path / "new.md"

    def fail(fd):
        raise OSError("SYNTHETIC_FSTAT_FAILURE")

    # Keep the fault local to the operation, not pytest or the verification read.
    with monkeypatch.context() as patch:
        patch.setattr(os, "fstat", fail)
        with pytest.raises(OSError, match="SYNTHETIC_FSTAT_FAILURE"):
            write_report(target, "safe", inputs=())
    assert target.read_bytes() == b""


def test_cleanup_failure_does_not_mask_original_error(tmp_path: Path, monkeypatch):
    target = tmp_path / "new.md"

    def fail_write(fd, data):
        raise OSError("SYNTHETIC_ORIGINAL_FAILURE")

    def fail_unlink(path, *args, **kwargs):
        raise PermissionError("SYNTHETIC_CLEANUP_FAILURE")

    monkeypatch.setattr(os, "write", fail_write)
    monkeypatch.setattr(Path, "unlink", fail_unlink)
    with pytest.raises(OSError, match="SYNTHETIC_ORIGINAL_FAILURE"):
        write_report(target, "safe", inputs=())
    assert target.read_bytes() == b""


def test_replacement_after_creation_is_preserved(tmp_path: Path, monkeypatch):
    target = tmp_path / "new.md"
    real_fsync, real_close, real_open = os.fsync, os.close, os.open

    def replace_after_flush(fd):
        real_fsync(fd)
        # Windows denies renaming this ordinary open handle. Inject a namespace
        # replacement at this boundary and restore its descriptor explicitly so
        # the real post-write identity checks, rather than a bad-fd error, fail.
        real_close(fd)
        target.rename(tmp_path / "owned-moved.md")
        target.write_bytes(b"concurrent-replacement")
        reopened = real_open(tmp_path / "owned-moved.md", os.O_WRONLY)
        if reopened != fd:
            os.dup2(reopened, fd)
            real_close(reopened)

    monkeypatch.setattr(os, "fsync", replace_after_flush)
    with pytest.raises(OSError):
        write_report(target, "safe report", inputs=())
    assert target.read_bytes() == b"concurrent-replacement"
    assert (tmp_path / "owned-moved.md").read_bytes() == b"safe report"
