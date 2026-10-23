"""Offline explicit-file analysis and exclusive report creation."""

import argparse
import sys
from collections.abc import Sequence
from typing import NoReturn

from winagent_repropack import __version__
from winagent_repropack.aggregation import analyze_log
from winagent_repropack.doctor import DoctorInputError, summarize_doctor
from winagent_repropack.io_utils import LogInputError
from winagent_repropack.models import ClientType
from winagent_repropack.output import OutputPathError, write_report
from winagent_repropack.reports import build_report, render_json, render_markdown


class _ArgumentParser(argparse.ArgumentParser):
    """Keep argument errors from reflecting user-supplied values or paths."""

    def error(self, message: str) -> NoReturn:
        self.print_usage(sys.stderr)
        self.exit(2, f"{self.prog}: error: invalid or missing arguments; use --help for usage.\n")


def build_parser() -> argparse.ArgumentParser:
    """Build the argument contract; constructing it performs no file access."""
    parser = _ArgumentParser(
        prog="repropack",
        description="Offline symptom report tool. Review every report before sharing.",
        allow_abbrev=False,
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    commands = parser.add_subparsers(dest="command", required=True)
    analyze = commands.add_parser(
        "analyze",
        help="Analyze selected local files and create a new report.",
        description="Offline analysis of one selected log and optional existing Doctor JSON.",
        allow_abbrev=False,
    )
    analyze.add_argument("--log", metavar="PATH", required=True, help="User-selected local log.")
    analyze.add_argument("--output", metavar="PATH", required=True, help="New local report path.")
    analyze.add_argument(
        "--doctor-json", metavar="PATH", help="Existing user-selected Doctor JSON."
    )
    analyze.add_argument("--format", choices=("markdown", "json"), default="markdown")
    analyze.add_argument(
        "--client", choices=("codex-cli", "codex-desktop", "generic"), default="generic"
    )
    analyze.add_argument(
        "--include-redacted-excerpts",
        action="store_true",
        help="Opt in to bounded canonical symptom fragments; arbitrary context is omitted.",
    )
    return parser


def _notice(message: str, *, error: bool = False) -> None:
    try:
        print(message, file=sys.stderr if error else sys.stdout)
    except OSError:
        pass


def main(argv: Sequence[str] | None = None) -> int:
    """Run the complete offline pipeline; never reflect dynamic exceptions/paths."""
    args = build_parser().parse_args(argv)
    try:
        analysis = analyze_log(args.log, include_excerpts=args.include_redacted_excerpts)
        doctor = summarize_doctor(args.doctor_json)
        report = build_report(analysis, doctor, client=ClientType(args.client))
        text = render_json(report) if args.format == "json" else render_markdown(report)
        inputs = (args.log, args.doctor_json) if args.doctor_json is not None else (args.log,)
        write_report(args.output, text, inputs=inputs)
    except (LogInputError, DoctorInputError):
        _notice("repropack: error: input was refused; no report was created.", error=True)
        return 2
    except OutputPathError:
        _notice(
            "repropack: error: output path was refused; existing files were not changed.",
            error=True,
        )
        return 3
    except (Exception, KeyboardInterrupt):
        _notice(
            "repropack: error: processing failed; review the selected output before retrying.",
            error=True,
        )
        return 5
    _notice(
        f"Report created; matched event lines: {report.summary.matched_event_lines}. "
        "MANUAL REVIEW REQUIRED before sharing."
    )
    return 0
