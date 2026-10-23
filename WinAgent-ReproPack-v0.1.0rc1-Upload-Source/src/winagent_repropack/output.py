"""Exclusive local output creation with conservative identity-checked cleanup."""

import os
import stat
from pathlib import Path

from winagent_repropack.reports import MAX_REPORT_BYTES


class OutputPathError(ValueError):
    """Fixed safe refusal before creating an output file (CLI exit 3)."""


def _local_path(path: str | Path) -> Path:
    value = os.fspath(path)
    if (
        not isinstance(value, str)
        or not value
        or value.startswith(("\\\\", "//"))
        or "\x00" in value
    ):
        raise OutputPathError("Select an ordinary local output path.")
    candidate = Path(value)
    if ".." in candidate.parts:
        raise OutputPathError("Parent traversal in output paths is not supported.")
    if os.name == "nt":
        if candidate.drive and not candidate.root:
            raise OutputPathError("Drive-relative output paths are not supported.")
        if any(
            Path(part).is_reserved()
            or part.endswith((".", " "))
            or any(char in part for char in ':<>"|?*')
            for part in candidate.parts
            if part != candidate.anchor
        ) or (not candidate.drive and ":" in value):
            raise OutputPathError("Special output paths are not supported.")
    return Path(os.path.abspath(candidate))


def _parents(path: Path) -> tuple[tuple[Path, os.stat_result], ...]:
    result = []
    for component in reversed(path.parents):
        info = component.lstat()
        if (
            not stat.S_ISDIR(info.st_mode)
            or stat.S_ISLNK(info.st_mode)
            or getattr(info, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT
        ):
            raise OutputPathError("Output ancestors must be stable ordinary local directories.")
        result.append((component, info))
    return tuple(result)


def _parents_unchanged(path: Path, before: tuple[tuple[Path, os.stat_result], ...]) -> bool:
    after = _parents(path)
    return len(after) == len(before) and all(
        left == right and os.path.samestat(old, new)
        for (left, old), (right, new) in zip(before, after, strict=True)
    )


def _remove_owned(
    path: Path, created: os.stat_result | None, parents: tuple[tuple[Path, os.stat_result], ...]
) -> None:
    """Never unlink an existing/replaced/unidentifiable target or unsafe ancestor.

    These stdlib checks are not atomic against a hostile concurrent directory
    writer. Use stable directories. If ownership cannot be confirmed, leave the
    selected target untouched and let the fixed exit-5 message request review.
    """
    if created is None:
        return
    try:
        if not _parents_unchanged(path, parents):
            return
        visible = path.lstat()
        if (
            stat.S_ISREG(visible.st_mode)
            and not stat.S_ISLNK(visible.st_mode)
            and not getattr(visible, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT
            and os.path.samestat(created, visible)
        ):
            path.unlink()
    except (OSError, ValueError):
        # Cleanup must not replace the original failure or expose OS diagnostics.
        pass


def write_report(path: str | Path, text: str, *, inputs: tuple[str | Path, ...]) -> None:
    """Create only a new target, after complete reading/rendering by the caller.

    Opening refusals map to exit 3. Once created, write/fsync/identity failures
    propagate to the CLI's fixed exit 5 after best-effort owned-file cleanup.
    No staging file, overwrite, directory creation, cache or background work.
    """
    data = text.encode("utf-8")
    if len(data) > MAX_REPORT_BYTES:
        raise ValueError("Report exceeds the output byte limit.")
    descriptor = None
    try:
        target = _local_path(path)
        for source in inputs:
            if os.path.normcase(str(_local_path(source))) == os.path.normcase(str(target)):
                raise OutputPathError("Output must differ from selected inputs.")
        parents = _parents(target)
        try:
            target.lstat()
        except FileNotFoundError:
            pass
        else:
            # All existing types, including input hardlink aliases, are refused.
            raise OutputPathError("Output already exists; select a new path.")
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0)
        flags |= getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(target, flags, 0o600)
    except (OSError, ValueError, TypeError):
        pass
    if descriptor is None:
        raise OutputPathError(
            "Output path was refused; select a new ordinary local target."
        ) from None
    created = None
    try:
        created = os.fstat(descriptor)
        if not stat.S_ISREG(created.st_mode) or not _parents_unchanged(target, parents):
            raise OSError("Output changed during creation.")
        position = 0
        while position < len(data):
            count = os.write(descriptor, data[position:])
            if count <= 0:
                raise OSError("Output write did not complete.")
            position += count
        os.fsync(descriptor)
        opened = os.fstat(descriptor)
        visible = target.lstat()
        if (
            not _parents_unchanged(target, parents)
            or not os.path.samestat(created, visible)
            or not os.path.samestat(created, opened)
            or opened.st_size != len(data)
            or stat.S_ISLNK(visible.st_mode)
            or getattr(visible, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT
        ):
            raise OSError("Output changed during writing.")
        os.close(descriptor)
        descriptor = None
    except BaseException:
        if descriptor is not None:
            try:
                os.close(descriptor)
            except OSError:
                pass
        _remove_owned(target, created, parents)
        raise
