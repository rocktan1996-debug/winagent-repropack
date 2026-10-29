# 03 — CLI and normalized schema contract

Implemented in source candidate `0.1.0rc2`. The CI matrix covers Windows and Ubuntu with Python 3.11/3.12; consult the release notes for exact-commit results. Windows 11 has not been separately validated.

## CLI examples

```powershell
repropack --help
repropack --version
repropack analyze --log .\examples\synthetic.log --output .\example-issue.md
repropack analyze --log .\examples\synthetic.log --doctor-json .\examples\synthetic-doctor.json --output .\example-report.json --format json
repropack analyze --log .\examples\synthetic.log --output .\with-excerpts.md --include-redacted-excerpts
```

Subcommand `analyze` requires `--log PATH` (one local file) and `--output PATH`; optional `--doctor-json PATH`, `--format {markdown,json}` default `markdown`, `--client {codex-cli,codex-desktop,generic}` default `generic`, `--include-redacted-excerpts` default **false**. No flags for uploading, auto-doctor, background monitoring or auto-GitHub submission.

## Exit codes and output

| Code | Meaning | Side effects |
|---:|---|---|
| 0 | report successfully created, including zero matched events | only selected output file |
| 2 | argument, input, size, encoding or JSON/schema error | no report created |
| 3 | unsafe/conflicting output path or file already exists | do not modify existing files |
| 5 | unexpected internal processing error | no raw log/credential echo; avoid partial report |

Stdout uses fixed text, event count and review reminder, with no path/filename. Stderr is fixed and sanitized. Help/version work offline. The owner's current privacy requirement supersedes the original output-path echo suggestion.

## Classifier mapping (one primary classification per input line)

Priority is top-down; never double-count one line as two primary events. Case-insensitive unless the pattern demands exact tokens. Basic regex matching is enough; not all possible client variants are covered.

| Priority | event_type | Match examples (case-insensitive) |
|---:|---|---|
| 1 | `remote_compact_failure` | `Error running remote compact task` |
| 2 | `stream_disconnect` | `stream disconnected before completion`, `peer closed connection without sending TLS close_notify`, `error decoding response body` |
| 3 | `capacity` | `Selected model is at capacity`, `server_overloaded` |
| 4 | `http_503` | standalone HTTP 503 / `status code: 503` / `503 Service Unavailable` |
| 5 | `reconnect_loop` | `Reconnecting 5/5`, or `Reconnecting 3/5` (integer counter tokens required; decimal counters such as `3/5.0` do not match) |
| 6 | `timeout` | `timed out`, `timeout` with concrete failure context |

If both `server_overloaded` and `HTTP 503` appear on one line, classify as `capacity` and note as ambiguous; do not inflate two categories. Explicit tests decide precedence. `unknown`/unmatched lines contribute to `total_lines` but not to event counts. Match labels indicate **observed text** only.

R1-01 (Phase 2): a `timeout` token immediately followed by a numeric `=` or `:`
assignment is configuration evidence and is excluded from timeout matching.
Other timeout tokens on the same line remain eligible with the existing failure
context; `timed out` remains a failure phrase. The regular expressions recognize
only some known symptoms and are not root-cause diagnosis. This is not a claim
that every possible log format is free of false positives or false negatives.

## Timestamp policy

- Accept ISO 8601 prefixes with `Z`, `+08:00`, `-07:00` (with optional milliseconds), and, separately, unzoned ISO local times. Non-ISO dates are out of scope.
- `first_seen`/`last_seen` contain only comparable offset-aware timestamps, and are null if any event in that group lacks a comparable timestamp; `first_observed_line`/`last_observed_line` refer to input order independently of time.
- For local/unzoned strings, present `timezone unknown` in narrative; do not assume Manila/Beijing/user system timezone.

## Report JSON v1 (illustrative shape, not sample of real users)

```json
{
  "schema_version": 1,
  "generator": {"name": "WinAgent ReproPack", "version": "0.1.0rc2"},
  "source": {"type": "user-selected log", "client": "generic"},
  "summary": {"total_lines": 1, "matched_event_lines": 1, "unknown_timestamp_lines": 0,
              "ambiguous_event_lines": 0, "timezone_unknown_lines": 0},
  "events": [
    {"type": "stream_disconnect", "count": 1, "first_observed_line": 1, "last_observed_line": 1,
     "first_seen": "2026-10-22T01:00:00+08:00", "last_seen": "2026-10-22T01:00:00+08:00", "line_numbers": [1], "redacted_excerpts": []}
  ],
  "doctor": {"included": false, "schema_version": null, "codex_version": null,
             "overall_status": null, "check_counts": {"ok": 0, "warning": 0, "fail": 0}},
  "warnings": ["Symptoms do not establish root cause.", "Review output before sharing.",
               "Unknown private information may remain; manual review required.",
               "Independent project; not affiliated with or endorsed by OpenAI."],
  "privacy": {"raw_log_embedded": false, "redacted_excerpts_included": false, "manual_review_required": true}
}
```

Actual counts depend on input. Schema invariants are tested. Line numbers cap at 20/group; counts remain complete. Excerpts are canonical allowlisted fragments capped at 3/type and 200 characters after scrubbing, only with opt-in; arbitrary context is dropped. Exact fields: `REPORT_SCHEMA_V1.md`.

## Doctor JSON import

Phase 2 decision (2026-10-22): `schemaVersion` and `checks` are required;
`overallStatus` and `codexVersion` are optional but strictly validated when present
(including refusal of null). This preserves the minimum shape below. Only integer
1 is supported; JSON true is not integer 1. Version identifiers must follow the narrow numeric/prerelease/build allowlist below. Every check must have status `ok`, `warning`, or `fail`.
The module API returns a frozen, slotted `DoctorSummary` with a frozen
`DoctorCheckCounts(ok, warning, fail)`; no check IDs or raw object are retained.
`summarize_doctor(None)` means not included; an imported empty checks map means
included with zero counts. The CLI integrates this importer when `--doctor-json` is explicitly supplied.

Strict UTF-8 (optional BOM), duplicate-key refusal at every depth, non-finite JSON
constant refusal and safe nesting/number parse errors apply to the entire input,
including ignored extensions. The 1 MiB limit counts original bytes, including
BOM and whitespace; over-limit input is rejected in full. Ordinary local file
checks reuse Phase 1 and add read-completion identity/metadata checks; these are
not an atomic snapshot guarantee. All import errors are fixed messages.

Accepted minimum shape is a JSON object with integer `schemaVersion=1` and a `checks` **object/map**, keyed by check ID (NOT an array). Each check must be an object with status `ok`, `warning` or `fail`. Unknown fields and dynamic check identifiers are parsed then discarded. Output keeps only optional validated `codexVersion`, optional `overallStatus` enum and fixed check-status counts. **Never export `details`, `issues`, `remediation` or the entire Doctor object.** This is the supported import contract; no live Doctor is invoked or verified.

Current Doctor version grammar: `MAJOR.MINOR.PATCH[-pre][+build.N]`, <=64 ASCII characters. Core numbers are 0 or 1–9 digits without leading zeros (at most nine digits). `pre` is exactly `alpha`, `beta`, `rc` or `dev`, optionally followed by `.N`; `N` is a nonnegative integer (at most eight digits, no leading zeros). `build` always requires `.N`. Example: `0.123.0`, `1.2.3-rc.1+build.2`. This narrow allowlist rejects arbitrary build/prerelease labels (including personal names, IDs and secret-looking text) rather than echoing them. Versions are untrusted metadata, not authenticated upstream strings. Missing `codexVersion` yields null; supplied null/invalid input fails with safe exit 2, no output or summary. The importer and both renderers share the same guard. The example fixture uses `0.0.0-dev.1+build.1`.

Timeout matching excludes each numeric `timeout=` / `timeout:` assignment individually, including decimal values and optional case-insensitive units listed in [README](../README.md). A separate real `timeout` failure token, `timeout exceeded`, or `timed out` still counts, including on a configuration line. The other five categories retain their order. Unknown units/text may still be misclassified; these are symptom heuristics.

If schemaVersion unsupported or required fields malformed, return code 2 and no output; list actual supported versions in README after verification. If the user did not provide Doctor data, report remains valid (`included=false`).

## Markdown report structure

```text
# Diagnostic issue report (review before sharing)
Environment: client as explicitly selected, Codex version only if doctor JSON supplied
Observed symptom summary: events/counts/line numbers
Timeline: comparable timestamps where available; otherwise 'unknown timezone'
Optional sanitized excerpts: absent by default
Steps to reproduce: [USER TO FILL]
Expected behavior: [USER TO FILL]
Actual behavior: [USER TO FILL]
What I tried: [USER TO FILL]
Limits: symptom matches only, not a verified diagnosis
Privacy checklist: check remaining names, paths, URLs, secrets, proprietary details
```

The generator must not invent reproduction steps, fixes, severity, user plan, global status or upstream root causes. No auto-posting. At least one prominent privacy warning at top and bottom.
