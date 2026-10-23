# Changelog

## 0.1.0rc1 — 2026-10-23 Final privacy hardening (unpublished source candidate)

- R4-01: strict allowlist for Doctor version prerelease and build labels; arbitrary metadata now safely refused by importer and renderers.
- R4-02: release packaging excludes internal build evidence and machine-specific absolute paths; added archive-level validation.
- Added adversarial end-to-end regression tests and updated synthetic golden files.
- Included completed MIT license notice with the connected GitHub account as public copyright identifier; private vulnerability reporting must be enabled and verified on the repository before public launch.

## 0.1.0rc1 — 2026-10-23 R3 audit repairs (unpublished)

- R3-01: replaced the freeform Doctor version character allowlist with a bounded three-part numeric version grammar and short prerelease/build identifiers; rejected token prefixes and unsupported metadata before model/report output. Report builder/renderers share the validation. Missing version remains null; invalid supplied version returns safe exit 2 without a report.
- R3-02: excluded numeric timeout configuration tokens with time units, decimal values and common unit spellings, while preserving separate real timeout evidence on the same line and all five higher category priorities.
- Added independent red/green, input/model/CLI/privacy/Markdown/JSON regressions. Tightened three historical fixture values to match the documented version contract without removing their privacy assertions. Existing golden bytes are unchanged.
- Updated security/schema/CLI documentation and re-audit evidence. Current environment limitations, skips and publication blockers are recorded in `REVIEW_HANDOFF.md`; historical platform passes are not current results. Version remains `0.1.0rc1` by owner instruction.

## 0.1.0rc1 — 2026-10-22 (unpublished)

- Completed offline Markdown and JSON v1 CLI reports, optional strict Doctor v1 import, client selection and zero-event success.
- Added typed immutable validated models, top/bottom manual-review notices and human-authored reproduction placeholders.
- Added opt-in canonical fragments, control/known-secret cleanup and bounded sampling; defaults retain no log text or source paths.
- Added exclusive output creation, alias/link/reparse refusal, fixed 0/2/3/5 outcomes and conservative identity-checked failure cleanup.
- Preserved strict timestamp/bounds/timeout/Doctor regressions. Fixed descriptor ownership if log stream wrapping fails and eliminated hidden raw exception context from safe refusals.
- Replaced obsolete CLI-placeholder expectations with actual success/refusal checks, preserving privacy/input-byte invariants.
- Added adversarial integration/golden tests, packaging and documentation. Historical local results are in private review handoffs; no public release is claimed.

## 0.1.0.dev0 — local history

Phase 0 provided the skeleton, Phase 1 bounded aggregation, Phase 2 strict Doctor summaries and R1-01 timeout fix. Dated developer evidence remains in private build logs. These versions were not published.
