# Report JSON v1

Frozen/slotted `DiagnosticReport` is validated before either renderer. Stable JSON field/event order, UTF-8, `allow_nan=False`, trailing newline. No source filename/path, original text, dynamic check ID or arbitrary extension is exported. Complete [synthetic golden](../tests/golden/synthetic-report.json).

| Field | Type and semantics |
|---|---|
| `schema_version` | integer 1; bool is not an integer schema |
| `generator` | fixed name `WinAgent ReproPack`; version from `__version__`, currently `0.1.0rc2` |
| `source` | fixed type `user-selected log`; selected client enum, default `generic` |
| `summary.total_lines` | physical LF-separated lines, 0–50,000; empty/BOM-only =0 |
| `summary.matched_event_lines` | <=total lines; equals sum of event counts |
| `summary.unknown_timestamp_lines` | all lines lacking comparable aware ISO timestamps, including unmatched lines |
| `summary.timezone_unknown_lines` | subset with valid unzoned ISO prefix; no timezone inferred |
| `summary.ambiguous_event_lines` | multi-category lines counted once in highest-priority category |
| `events` | <=6 groups, fixed priority order; empty for no matches |
| `events[].type` | fixed six-value `EventType` enum |
| `events[].count` | complete positive primary count; repeated phrases on a line count once |
| `events[].first_observed_line`, `last_observed_line` | 1-based source-order bounds, independent of time order |
| `events[].line_numbers` | first min(count,20) observed lines, strictly increasing |
| `events[].first_seen`, `last_seen` | min/max aware instants, canonical ISO strings preserving selected offset; both null if any group member lacks comparable time |
| `events[].redacted_excerpts` | empty by default; <=3 canonical scrubbed fragments of <=200 characters each in source order; no arbitrary context |
| `doctor.included` | whether Doctor input was supplied |
| `doctor.schema_version` | 1 when included, otherwise null |
| `doctor.codex_version` | optional bounded `MAJOR.MINOR.PATCH[-prerelease][+build]` string; null if absent; supplied metadata, not independently verified |
| `doctor.overall_status` | optional `ok`/`warning`/`fail`; null if absent; not recomputed from counts |
| `doctor.check_counts` | fixed integer `ok`, `warning`, `fail` counters; always present, zeros when absent or empty |
| `warnings` | four fixed warnings about symptoms/root cause, sharing review, unknown private data and non-affiliation |
| `privacy.raw_log_embedded` | always false |
| `privacy.redacted_excerpts_included` | true iff fragments actually appear; false for zero matches even when opted in |
| `privacy.manual_review_required` | always true |

Doctor absent: included false, null metadata, zero counts. Supplied `{ "schemaVersion": 1, "checks": {} }`: included true, schema 1, null optional fields, zero counts. Input rules: [README](../README.md). Ignored extensions still must be valid JSON.

The current version contract uses core numeric `MAJOR.MINOR.PATCH` (each 0 or 1–9 digits, no leading zeros); optional `-alpha[.N]`, `-beta[.N]`, `-rc[.N]`, or `-dev[.N]`; and optional `+build.N`, with N 0 or 1–8 digits without leading zeros. Total <=64 ASCII characters. Arbitrary suffix labels—including names, tokens, IDs, and git-SHA-like build labels—are rejected. A provided invalid value yields exit 2, no output; a missing version yields null. Both renderer sinks enforce the same rule on programmatic models. Accepted numeric metadata is not authenticated and still requires review.

The synthetic golden fixture was updated to `0.0.0-dev.1+build.1` and the golden outputs checked against it.

Both formats derive from the same model with equivalent counts/lines/times/Doctor statistics. Markdown escapes dynamic metadata, labels unavailable times `unknown / timezone unknown`, and places notices at top and bottom. Final output <=64 KiB. No generated-at clock or source path is stored; stable bytes and options yield deterministic reports. Arbitrary programmatic model extensions are not a data-export API.
