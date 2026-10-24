"""Verify a built wheel in a clean venv using bundled synthetic inputs only.

Maintainer/CI tooling, not product analysis: launches local Python/pip processes.
The wheel install is offline (--no-index --no-deps); no data is uploaded.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import tempfile
import venv
from pathlib import Path

SUCCESS = "Report created; matched event lines: 6. MANUAL REVIEW REQUIRED before sharing."


def _run(command: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command, cwd=cwd, text=True, capture_output=True, check=False, timeout=120
    )


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def verify_report(output: Path, golden: Path) -> None:
    """Compare text without depending on checkout/platform newline conventions."""
    _require(
        output.read_text(encoding="utf-8") == golden.read_text(encoding="utf-8"),
        f"Synthetic {output.suffix} report differs from the checked-in golden",
    )


def verify_demo(python: Path, root: Path, work: Path) -> None:
    log = root / "examples" / "synthetic.log"
    doctor = root / "examples" / "synthetic-doctor-v1.json"
    before = (log.read_bytes(), doctor.read_bytes())
    prefix = [str(python), "-I", "-m", "winagent_repropack"]
    console = python.parent / ("repropack.exe" if sys.platform == "win32" else "repropack")
    for option in ("--help", "--version"):
        run = _run([*prefix, option], work)
        _require(run.returncode == 0 and not run.stderr, f"Installed CLI {option} failed")
        entrypoint = _run([str(console), option], work)
        _require(
            entrypoint.returncode == 0
            and not entrypoint.stderr
            and entrypoint.stdout == run.stdout,
            f"Installed console entrypoint {option} differs from module CLI",
        )
    for format_name, suffix in (("markdown", "md"), ("json", "json")):
        output = work / f"synthetic-report.{suffix}"
        command = [
            *prefix, "analyze", "--log", str(log), "--doctor-json", str(doctor),
            "--format", format_name, "--output", str(output),
        ]
        run = _run(command, work)
        _require(run.returncode == 0, f"Installed CLI {format_name} generation failed")
        _require(run.stdout.strip() == SUCCESS and not run.stderr, "Unexpected CLI status output")
        verify_report(output, root / "tests" / "golden" / output.name)
        original = output.read_bytes()
        repeat = _run(command, work)
        _require(repeat.returncode == 3, "Existing output was not refused with exit code 3")
        _require(output.read_bytes() == original, "Existing output changed on repeated invocation")
        _require((log.read_bytes(), doctor.read_bytes()) == before, "Synthetic inputs changed")


def verify_wheel(wheel: Path, root: Path) -> None:
    _require(wheel.is_file() and wheel.suffix == ".whl", "Select an existing built .whl file")
    with tempfile.TemporaryDirectory(prefix="repropack-wheel-demo-") as temporary:
        work = Path(temporary)
        environment = work / "venv"
        venv.EnvBuilder(with_pip=True).create(environment)
        python = environment / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
        install = _run([
            str(python), "-I", "-m", "pip", "install", "--disable-pip-version-check",
            "--no-cache-dir", "--no-index", "--no-deps", str(wheel.resolve()),
        ], work)
        _require(install.returncode == 0, "Offline wheel installation failed")
        verify_demo(python, root, work)


def select_wheel(directory: Path) -> Path:
    wheels = sorted(directory.glob("winagent_repropack-*.whl"))
    _require(len(wheels) == 1, "Wheel directory must contain exactly one ReproPack wheel")
    return wheels[0]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    selection = parser.add_mutually_exclusive_group(required=True)
    selection.add_argument("--wheel", type=Path, help="Locally built wheel to verify")
    selection.add_argument(
        "--wheel-dir", type=Path, help="Directory with exactly one ReproPack wheel"
    )
    args = parser.parse_args()
    try:
        wheel = args.wheel if args.wheel is not None else select_wheel(args.wheel_dir)
        verify_wheel(wheel, Path(__file__).resolve().parents[1])
    except (OSError, RuntimeError, subprocess.SubprocessError) as error:
        parser.exit(1, f"Synthetic wheel demo failed: {error}\n")
    print("PASS: clean offline wheel install; help/version; Markdown/JSON goldens; "
          "no-overwrite; unchanged synthetic inputs. No real user data was used.")


if __name__ == "__main__":
    main()
