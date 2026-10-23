"""Argument contract and RC behavior; placeholder assertions replaced, safety retained."""

import json
from importlib.metadata import version
from pathlib import Path

import pytest

from winagent_repropack import __version__
from winagent_repropack.cli import build_parser, main


@pytest.mark.parametrize("args", [["--help"], ["analyze", "--help"]])
def test_help(args: list[str], capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as error:
        main(args)
    assert error.value.code == 0
    output = capsys.readouterr()
    assert "usage: repropack" in output.out
    assert "offline" in " ".join(output.out.lower().split())
    assert output.err == ""
    if args[0] == "analyze":
        for option in (
            "--log",
            "--output",
            "--doctor-json",
            "--format",
            "--client",
            "--include-redacted-excerpts",
        ):
            assert option in output.out


def test_version(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as error:
        main(["--version"])
    assert error.value.code == 0
    output = capsys.readouterr()
    assert output.out.strip() == f"repropack {__version__}"
    assert version("winagent-repropack") == __version__
    assert output.err == ""


@pytest.mark.parametrize(
    "args",
    [
        [],
        ["analyze"],
        ["analyze", "--log", "synthetic.log"],
        ["analyze", "--output", "synthetic.md"],
        ["analyze", "--log"],
        ["analyze", "--log", "synthetic.log", "--output"],
        ["analyze", "--log", "synthetic.log", "--output", "synthetic.md", "--doctor-json"],
    ],
)
def test_required_arguments(args: list[str], capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as error:
        main(args)
    assert error.value.code == 2
    output = capsys.readouterr()
    assert output.out == ""
    assert "invalid or missing arguments" in output.err
    assert "Traceback" not in output.err


@pytest.mark.parametrize(
    "args",
    [
        ["SYNTHETIC_PRIVATE_SUBCOMMAND"],
        ["--SYNTHETIC_PRIVATE_OPTION"],
        ["analyze", "--format", "SYNTHETIC_PRIVATE_FORMAT"],
        ["analyze", "--client", "SYNTHETIC_PRIVATE_CLIENT"],
        ["analyze", "--SYNTHETIC_PRIVATE_OPTION"],
        ["analyze", "SYNTHETIC_PRIVATE_POSITIONAL"],
        ["analyze", "--lo", "SYNTHETIC_PRIVATE_PATH"],
    ],
)
def test_errors_do_not_echo_values(args: list[str], capsys: pytest.CaptureFixture[str]) -> None:
    if args[0] == "analyze":
        args = ["analyze", "--log", "synthetic.log", "--output", "synthetic.md", *args[1:]]
    with pytest.raises(SystemExit) as error:
        main(args)
    assert error.value.code == 2
    output = capsys.readouterr()
    assert output.out == ""
    assert "invalid or missing arguments" in output.err
    assert "SYNTHETIC_PRIVATE" not in output.err


def test_argument_defaults() -> None:
    args = build_parser().parse_args(["analyze", "--log", "synthetic.log", "--output", "new.md"])
    assert args.command == "analyze"
    assert args.format == "markdown"
    assert args.client == "generic"
    assert args.doctor_json is None
    assert args.include_redacted_excerpts is False


@pytest.mark.parametrize("report_format", ["markdown", "json"])
@pytest.mark.parametrize("client", ["codex-cli", "codex-desktop", "generic"])
def test_optional_arguments(report_format: str, client: str) -> None:
    args = build_parser().parse_args(
        [
            "analyze",
            "--log",
            "synthetic.log",
            "--output",
            "new.md",
            "--doctor-json",
            "synthetic-doctor.json",
            "--format",
            report_format,
            "--client",
            client,
            "--include-redacted-excerpts",
        ]
    )
    assert args.format == report_format
    assert args.client == client
    assert args.doctor_json == "synthetic-doctor.json"
    assert args.include_redacted_excerpts is True


@pytest.mark.parametrize("output_kind", ["new", "existing", "input", "missing-parent"])
def test_analysis_preserves_inputs_and_existing_outputs(
    output_kind: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    log = tmp_path / "SYNTHETIC_PRIVATE.log"
    doctor = tmp_path / "SYNTHETIC_PRIVATE.json"
    existing = tmp_path / "SYNTHETIC_PRIVATE.md"
    originals = {
        log: b"SYNTHETIC_LOG_CANARY\n",
        doctor: b'{"schemaVersion":1,"checks":{},"ignored":"SYNTHETIC_DOCTOR_CANARY"}',
        existing: b"SYNTHETIC_EXISTING_OUTPUT_CANARY",
    }
    for path, content in originals.items():
        path.write_bytes(content)
    output = {
        "new": tmp_path / "new.md",
        "existing": existing,
        "input": log,
        "missing-parent": tmp_path / "absent" / "new.md",
    }[output_kind]

    result = main(
        [
            "analyze",
            "--log",
            str(log),
            "--output",
            str(output),
            "--doctor-json",
            str(doctor),
            "--include-redacted-excerpts",
            "--format",
            "json",
        ]
    )
    assert result == (0 if output_kind == "new" else 3)
    captured = capsys.readouterr()
    assert "SYNTHETIC_" not in captured.out + captured.err
    assert str(tmp_path) not in captured.out + captured.err
    assert {path: path.read_bytes() for path in originals} == originals
    if output_kind == "new":
        report = json.loads(output.read_text(encoding="utf-8"))
        assert report["summary"]["matched_event_lines"] == 0
        assert report["doctor"]["included"] is True
        assert "SYNTHETIC_" not in output.read_text(encoding="utf-8")
        assert "MANUAL REVIEW REQUIRED" in captured.out
    elif output_kind == "missing-parent":
        assert not output.exists()


def test_nonexistent_inputs_are_not_opened(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert (
        main(
            ["analyze", "--log", str(tmp_path / "absent.log"), "--output", str(tmp_path / "new.md")]
        )
        == 2
    )
    captured = capsys.readouterr()
    assert "input was refused" in captured.err
    assert str(tmp_path) not in captured.err
    assert not (tmp_path / "new.md").exists()
