"""The maintainer demo must reject output drift, not silently update goldens."""

import importlib.util
import subprocess
from pathlib import Path

import pytest


@pytest.fixture(scope="module")
def verifier():
    path = Path(__file__).resolve().parents[1] / "tools" / "verify_wheel_demo.py"
    spec = importlib.util.spec_from_file_location("wheel_demo", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_demo_accepts_platform_newlines(tmp_path: Path, verifier) -> None:
    output, golden = tmp_path / "report.md", tmp_path / "golden.md"
    output.write_bytes(b"synthetic\n")
    golden.write_bytes(b"synthetic\r\n")
    verifier.verify_report(output, golden)


def test_demo_rejects_drift_without_rewriting_golden(tmp_path: Path, verifier) -> None:
    output, golden = tmp_path / "report.json", tmp_path / "golden.json"
    output.write_bytes(b'{"matched_event_lines": 0}\n')
    expected = b'{"matched_event_lines": 6}\n'
    golden.write_bytes(expected)
    with pytest.raises(RuntimeError, match="differs from the checked-in golden"):
        verifier.verify_report(output, golden)
    assert golden.read_bytes() == expected


def test_demo_requires_existing_wheel(tmp_path: Path, verifier) -> None:
    with pytest.raises(RuntimeError, match="existing built .whl"):
        verifier.verify_wheel(tmp_path / "missing.whl", tmp_path)


def test_demo_selects_single_wheel_without_hardcoded_version(tmp_path: Path, verifier) -> None:
    wheel = tmp_path / "winagent_repropack-9.9.9-py3-none-any.whl"
    wheel.touch()
    assert verifier.select_wheel(tmp_path) == wheel


@pytest.mark.parametrize("count", [0, 2])
def test_demo_refuses_missing_or_ambiguous_wheels(tmp_path: Path, verifier, count: int) -> None:
    for version in range(count):
        (tmp_path / f"winagent_repropack-0.0.{version}-py3-none-any.whl").touch()
    with pytest.raises(RuntimeError, match="exactly one ReproPack wheel"):
        verifier.select_wheel(tmp_path)


@pytest.mark.parametrize("failure", [None, "entrypoint", "overwrite", "input-mutation"])
def test_demo_checks_installed_behavior(tmp_path: Path, verifier, monkeypatch, failure) -> None:
    root, work = tmp_path / "source", tmp_path / "work"
    (root / "examples").mkdir(parents=True)
    (root / "tests" / "golden").mkdir(parents=True)
    work.mkdir()
    log = root / "examples" / "synthetic.log"
    log.write_bytes(b"HTTP 503\n")
    (root / "examples" / "synthetic-doctor-v1.json").write_bytes(b"{}")
    for suffix in ("md", "json"):
        (root / "tests" / "golden" / f"synthetic-report.{suffix}").write_bytes(b"synthetic\n")

    def run(command, cwd):
        assert cwd == work
        if "analyze" not in command:
            code = 1 if failure == "entrypoint" and "-I" not in command else 0
            return subprocess.CompletedProcess(command, code, "synthetic help/version\n", "")
        output = Path(command[command.index("--output") + 1])
        if output.exists():
            if failure == "overwrite":
                output.write_bytes(b"changed")
            if failure == "input-mutation":
                log.write_bytes(b"changed")
            return subprocess.CompletedProcess(command, 3, "", "existing output")
        output.write_bytes(b"synthetic\n")
        return subprocess.CompletedProcess(command, 0, verifier.SUCCESS + "\n", "")

    monkeypatch.setattr(verifier, "_run", run)
    if failure:
        with pytest.raises(RuntimeError):
            verifier.verify_demo(tmp_path / "bin" / "python", root, work)
    else:
        verifier.verify_demo(tmp_path / "bin" / "python", root, work)
