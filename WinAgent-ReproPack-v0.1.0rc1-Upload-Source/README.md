# WinAgent ReproPack

**0.1.0rc1 — locally audited source candidate; external release checks pending.** Independent project, not affiliated with or endorsed by OpenAI. Not yet published.

Turn one explicitly selected log and optional existing Doctor JSON into an editable Markdown issue draft or JSON v1 report. Runtime dependencies are empty: analysis uses only the Python standard library. No log discovery, automatic Doctor, network/LLM calls, subprocesses, telemetry, uploads or issue creation.

**MANUAL REVIEW REQUIRED before sharing.** Symptoms do not establish root cause. Count/time/version metadata can also be private. No universal privacy guarantee is made.

## Install locally

From this project directory in PowerShell, with an existing Python 3.11+ installation:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --cache-dir .cache/pip -e '.[dev]'
.\.venv\Scripts\repropack.exe --help
.\.venv\Scripts\repropack.exe --version
```

Version prints `repropack 0.1.0rc1`. No activation or PATH change is needed. Installation downloads development/build dependencies; analysis is offline. An existing audited local wheel can be installed with `python -m pip install --no-index --no-deps PATH_TO_WHEEL`. This RC has not been published to PyPI.

## Quickstart with synthetic data

Use new output names: existing files are always refused. These commands were executed locally; see the synthetic examples below.

```powershell
New-Item -ItemType Directory -Force artifacts/readme-demo | Out-Null
.\.venv\Scripts\repropack.exe analyze --log examples/synthetic.log --doctor-json examples/synthetic-doctor-v1.json --output artifacts/readme-demo/issue.md
.\.venv\Scripts\repropack.exe analyze --log examples/synthetic.log --doctor-json examples/synthetic-doctor-v1.json --output artifacts/readme-demo/report.json --format json
.\.venv\Scripts\repropack.exe analyze --log examples/synthetic.log --output artifacts/readme-demo/fragments.md --client codex-cli --include-redacted-excerpts
```

Each prints:

```text
Report created; matched event lines: 6. MANUAL REVIEW REQUIRED before sharing.
```

The fixture has 9 lines, 6 matched lines in 5 categories and 1 ambiguous line counted once. Doctor has 2 `ok`, 1 `warning`, 1 `fail` checks. Exact [JSON](tests/golden/synthetic-report.json) and [Markdown](tests/golden/synthetic-report.md) goldens are synthetic. Zero events also succeed.

For your own data, replace `--log` with a file you chose and `--output` with a new path in an existing stable local directory. Add `--doctor-json` only if you already have a file you chose to import. No login or credentials are needed. Review the whole report, fill reproduction placeholders and share manually if appropriate.

## CLI

```text
repropack analyze --log PATH --output PATH
  [--doctor-json PATH] [--format markdown|json]
  [--client codex-cli|codex-desktop|generic]
  [--include-redacted-excerpts]
```

Defaults: Markdown, generic client, no Doctor, no excerpts. Help/version return 0. Errors are fixed messages without source paths, content or tracebacks.

| Exit | Meaning |
|---:|---|
| 0 | Report created, including zero events |
| 2 | Invalid arguments/input/encoding/bounds/Doctor schema; no report |
| 3 | Unsafe, existing or conflicting output; existing bytes unchanged |
| 5 | Unexpected processing/write failure; inspect selected output before retrying |

## What is retained

Default reports contain fixed categories, complete counts, line bounds, up to 20 line numbers/category, comparable times, fixed warnings and allowlisted Doctor statistics. No original log lines, source names/paths, dynamic check IDs or freeform diagnostic text.

Opt-in excerpts are **canonical symptom fragments**, selected from a fixed allowlist after control cleanup and known-sensitive-pattern redaction. Arbitrary context is discarded. At most 3/category, each at most 200 characters after redaction, in source order; duplicates are possible. Credentials, URL queries, email/IP/home paths, long IDs, ANSI, bidi and controls have synthetic regression coverage. Unknown secrets are not universally detectable; manual review remains required. The scrubber is not a general-purpose privacy filter for arbitrary text.

One line receives one primary category, in order: `remote_compact_failure`, `stream_disconnect`, `capacity`, `http_503`, `reconnect_loop`, `timeout`. Multiple matches increment ambiguity. Numeric `timeout=30` / `timeout: 30` assignments, including `30s`, `30ms` and decimal values, do not count as failure tokens. Unit matching is case-insensitive and permits whitespace: `ns`, `us`, `µs`, `ms`, `msec(s)`, `millisecond(s)`, `s`, `sec(s)`, `second(s)`, `m`, `min(s)`, `minute(s)`, `h`, `hr(s)`, `hour(s)`. Each configuration token is excluded individually; a separate `timeout` with failure context or `timed out` still matches on the same line. Detection is heuristic and can misclassify unsupported text.

## Boundaries and limitations

- Log: <=10 MiB, <=50,000 physical LF-separated lines, <=64 KiB/raw line. Byte limits include BOM and CR/LF. An unterminated nonempty final line counts; empty/BOM-only =0 lines. Strict UTF-8 with optional initial BOM; invalid bytes rejected, never replaced or guessed.
- Doctor: <=1 MiB including BOM/whitespace; strict UTF-8/JSON. Duplicate keys and non-finite constants refused at every depth. Requires integer `schemaVersion=1`, `checks` object/map, and every check status `ok`, `warning` or `fail`. Optional `overallStatus` and `codexVersion` strictly validated when present; null refused. Versions use the bounded three-part grammar below. Unknown fields parsed then discarded. Omitted input differs from supplied empty checks.
- Time: ISO first column with seconds, optional 1–3 fraction digits, explicit `Z`/numeric offset for comparison. No inferred timezone. Group bounds null if any member lacks comparable time; observed line order independent. Unknown timestamp count includes unmatched lines.
- Output: UTF-8, <=64 KiB, fully rendered before exclusive `O_EXCL` creation. Parent must exist. Refuses existing files, input aliases, links/reparse ancestors, UNC/device/Windows special paths and `..`. Creation failure =3; failure after creation =5 with best-effort identity-checked cleanup. Replaced/unidentifiable files are left untouched, so a failure may leave an output for manual review.
- Checks are **not an atomic filesystem snapshot**. Use stable ordinary local files/directories without hostile concurrent writers. Remote mounts cannot be reliably detected. No guarantee against adversarial directory replacement or same-inode mutation. No overwrite/force/retry switch.

Exact fields: [report schema](docs/REPORT_SCHEMA_V1.md). [中文快速开始](docs/QUICKSTART_ZH.md).

Doctor versions use a deliberately restrictive ASCII format: `MAJOR.MINOR.PATCH` (each 0 or 1–9 digits without leading zeros), optional `-alpha[.N]`, `-beta[.N]`, `-rc[.N]` or `-dev[.N]`, and optional `+build.N`; `N` is a nonnegative integer of at most eight digits without leading zeros. Entire value <=64 bytes. Examples: `0.123.0`, `1.2.3-rc.1+build.2`. **Arbitrary prerelease and build labels are rejected**: this avoids copying names, identifiers or secrets from untrusted Doctor JSON into reports. This is a narrow supported subset, not a general-purpose semantic-version parser. Missing `codexVersion` becomes null; invalid supplied versions reject input (exit 2, no output). Renderers recheck the same format. Even permitted numeric metadata should be manually reviewed.

## Development and verification

```powershell
.\.venv\Scripts\python.exe -m pytest -q --cov=winagent_repropack --cov-branch --cov-report=term-missing --cov-fail-under=85 --basetemp=.tmp/pytest-local -o cache_dir=.cache/pytest
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m build --outdir artifacts/dist
```

Use a fresh pytest base directory containing no user data: pytest manages it. Previous Windows local testing has incomplete Python 3.12 and symlink coverage. GitHub Actions is configured for Windows/Ubuntu × Python 3.11/3.12 but has not run on a remote repository. Windows 11 has not been verified. Do not claim those tests passed until actual evidence is available.

## FAQ

**Why no raw excerpt?** Unknown business secrets can survive pattern redaction. Fixed fragments retain the observed symptom variant without arbitrary context.

**Why are time bounds null?** Missing/unzoned/invalid times make group-wide bounds unreliable. Observed line bounds remain.

**Why refuse an existing report?** Select a new name. The tool never replaces old reports.

**Does this prove an outage or fix a client?** No. Only text matches and supplied metadata are reported; reproduction/expected/actual/attempted-fix placeholders remain for the user.

[CONTRIBUTING](CONTRIBUTING.md), [SECURITY](SECURITY.md), [CHANGELOG](CHANGELOG.md). This source distribution includes an MIT `LICENSE`. For private vulnerability reports, enable GitHub private vulnerability reporting on the published repository before inviting external users; see [SECURITY](SECURITY.md). Remote CI and publication are not yet verified, and external OSS-program eligibility is not established.
