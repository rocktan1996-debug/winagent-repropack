"""Offline import of one explicitly selected, existing Doctor JSON file."""

import json
import math
import os
import re
from pathlib import Path

from winagent_repropack.io_utils import _check_components, _open_regular
from winagent_repropack.models import DoctorCheckCounts, DoctorSummary

MAX_DOCTOR_BYTES = 1_048_576
_CHUNK_BYTES = 64 * 1024
_STATUSES = ("ok", "warning", "fail")
# Fail closed on arbitrary build/prerelease strings: they may contain private data.
# A valid-looking version is untrusted input and is validated again at render time.
_NUMBER = r"(?:0|[1-9][0-9]{0,8})"
_PRERELEASE = r"(?:alpha|beta|rc|dev)(?:\.(?:0|[1-9][0-9]{0,7}))?"
_BUILD = r"build\.(?:0|[1-9][0-9]{0,7})"
_VERSION = re.compile(
    rf"(?=.{{1,64}}\Z){_NUMBER}\.{_NUMBER}\.{_NUMBER}"
    rf"(?:-{_PRERELEASE})?(?:\+{_BUILD})?",
    re.ASCII,
)


class DoctorInputError(ValueError):
    """A fixed safe refusal, without input text, paths, or chained diagnostics."""


def _read_doctor(path: str | Path) -> bytes:
    """Reuse conservative Phase 1 path checks, then enforce the JSON byte bound.

    Identity and metadata comparisons detect some concurrent changes; they do
    not provide an atomic snapshot. Files and ancestor directories must be stable.
    """
    try:
        descriptor = _open_regular(path)
        try:
            stream = os.fdopen(descriptor, "rb")
        except BaseException:
            os.close(descriptor)
            raise
        with stream:
            before = os.fstat(stream.fileno())
            if before.st_size > MAX_DOCTOR_BYTES:
                raise DoctorInputError("Doctor JSON exceeds the 1 MiB byte limit.")
            data = bytearray()
            while True:
                chunk = stream.read(min(_CHUNK_BYTES, MAX_DOCTOR_BYTES - len(data) + 1))
                if not chunk:
                    break
                data.extend(chunk)
                if len(data) > MAX_DOCTOR_BYTES:
                    raise DoctorInputError("Doctor JSON exceeds the 1 MiB byte limit.")
            after = os.fstat(stream.fileno())
            visible = _check_components(Path(os.path.abspath(path)))
            if (
                not os.path.samestat(before, after)
                or not os.path.samestat(visible, after)
                or (before.st_size, before.st_mtime_ns, before.st_ctime_ns)
                != (after.st_size, after.st_mtime_ns, after.st_ctime_ns)
                or len(data) != after.st_size
            ):
                raise DoctorInputError("Doctor JSON changed during reading; select a stable file.")
            return bytes(data)
    except (OSError, ValueError, TypeError) as error:
        # Re-raise safe importer errors. Raise the wrapper outside the handler
        # so even programmatic __context__ access cannot recover OS diagnostics.
        if isinstance(error, DoctorInputError):
            raise
    raise DoctorInputError("Doctor JSON could not be read as an ordinary local file.") from None


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise DoctorInputError("Doctor JSON must not contain duplicate keys.")
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    raise DoctorInputError("Doctor JSON must not contain non-finite constants.")


def _finite_float(value: str) -> float:
    number = float(value)
    if not math.isfinite(number):
        raise DoctorInputError("Doctor JSON must not contain non-finite constants.")
    return number


def _parse_doctor(data: bytes) -> DoctorSummary:
    invalid = False
    try:
        report = json.loads(
            data.decode("utf-8-sig"),
            object_pairs_hook=_unique_object,
            parse_constant=_reject_constant,
            parse_float=_finite_float,
        )
    except DoctorInputError:
        raise
    except (UnicodeError, ValueError, RecursionError, OverflowError):
        invalid = True
    if invalid:
        raise DoctorInputError(
            "Doctor JSON is not valid UTF-8 JSON within parser limits."
        ) from None
    if (
        not isinstance(report, dict)
        or type(report.get("schemaVersion")) is not int
        or report["schemaVersion"] != 1
        or not isinstance(report.get("checks"), dict)
    ):
        raise DoctorInputError("Doctor JSON requires schema version 1 and a checks object.")
    overall = report.get("overallStatus")
    if "overallStatus" in report and (not isinstance(overall, str) or overall not in _STATUSES):
        raise DoctorInputError("Doctor JSON has an invalid overall status.")
    version = report.get("codexVersion")
    if "codexVersion" in report and (
        not isinstance(version, str) or not _VERSION.fullmatch(version)
    ):
        raise DoctorInputError("Doctor JSON has an invalid version identifier.")
    counts = dict.fromkeys(_STATUSES, 0)
    for check in report["checks"].values():
        if not isinstance(check, dict):
            raise DoctorInputError("Doctor JSON checks require objects with a valid status.")
        status = check.get("status")
        if not isinstance(status, str) or status not in _STATUSES:
            raise DoctorInputError("Doctor JSON checks require objects with a valid status.")
        counts[status] += 1
    return DoctorSummary(True, 1, version, overall, DoctorCheckCounts(**counts))


def summarize_doctor(path: str | Path | None = None) -> DoctorSummary:
    """Return only fixed safe metadata, or a pure not-included model for None.

    No scanning, Doctor invocation, cache, output file, or raw-object retention.
    """
    if path is None:
        return DoctorSummary()
    return _parse_doctor(_read_doctor(path))
