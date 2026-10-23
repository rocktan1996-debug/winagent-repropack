# 04 — Security, privacy, and abuse model (must-pass)

Status: design rules, not a claim that code is safe. Diagnostics may expose login tokens, prompts, private file names, conversation contents, IP addresses, passwords and secrets. **Default to data minimization, not merely regex.**

## Trust boundaries

1. Untrusted inputs: user-supplied text log and JSON, including malicious text attempting to instruct the AI developer or trick Markdown rendering.
2. Trusted execution: only our deterministic Python parser working offline with ordinary user privileges.
3. Sensitive sink: generated Markdown/JSON that the user might post publicly. No transmission occurs by the application.
4. Maintainer: must never request that users paste raw private logs into a public Issue or upload actual secrets for reproduction.

## Mandatory properties

- CLI accesses only explicit `--log` and optional `--doctor-json`; no hidden auto-discovery, reading `$HOME/.codex/auth.json`, dumping environment, network requests, or remote fetches.
- Never execute instructions from input; do not use `eval`, `exec`, `os.system`, `subprocess`, external LLMs, or shell interpolation.
- Default output is counts, event type labels, line numbers, conservative status fields and *no verbatim lines*. Source basename/path not included. No implicit cache or raw log copy.
- `--include-redacted-excerpts` only after explicit user action; cap at 3 lines/type and 200 chars/line. Always scrub BEFORE escaping/rendering, drop impossible-to-sanitize fields, include giant "MANUAL REVIEW REQUIRED" warning. Even after scrubbing, do not claim safety.
- Strip control/ANSI codes, terminal escape sequences, bidi override characters, nul bytes, and CR/LF injection in dynamic short fields. Treat user input as plain data, never HTML or Markdown directives.
- Reject oversized input and malformed JSON with human-readable, sanitized messages. Never print raw input in error stack traces. Avoid echoing real paths.
- Default reports must never contain recognizable raw secrets or usernames from any tested fixture. Run an automated report leakage test against all output formats.
- No telemetry, no remote error reporting, no update check, no upload features. Development-time `pip` dependency installation is separate from runtime offline behavior.
- Avoid updating/invoking Codex or testing user network. Only import a separately produced diagnostic JSON file with consent.

## Redaction strategy (defense in depth)

A. **Exclude by default**. Events are mapped to fixed safe labels, counts, numbers and validated timestamps. Exclude arbitrary source strings, JSON `details`, `issues`, `remediation` and provenance paths.

B. For opt-in excerpts only, apply conservative patterns:

| Pattern class | Examples (dummy, not real) | Output |
|---|---|---|
| Headers/tokens | `Authorization: Bearer DEMO_NOT_VALID`, `api_key=DEMO_NOT_VALID`, token-like values | `[REDACTED:CREDENTIAL]` |
| API-style secrets | strings matching `sk-...`, GitHub token prefixes `ghp_`, `gho_`, `github_pat_` | `[REDACTED:CREDENTIAL]` |
| Windows user path | `[SYNTHETIC_WINDOWS_USER_PATH]` | `[REDACTED:USER_PATH]` or `[REDACTED:USER_PATH]` |
| Email addresses | `example@invalid.test` | `[REDACTED:EMAIL]` |
| IPv4/IPv6 addresses | `192.0.2.10`, `2001:db8::1` | `[REDACTED:IP]` if detected |
| URLs with query strings | `https://example.invalid/path?token=demo` | `[REDACTED:URL]` (prefer full URL exclusion) |
| Session IDs/hashes | arbitrary hex 32+ chars or common `session_id=` | `[REDACTED:IDENTIFIER]` |

C. For unknown but dangerous dynamic data: prefer to **omit excerpt** rather than pass it through unsanitized. `max_chars` and escape routines apply after redaction. In tests, use made-up demonstrators from reserved ranges (`example.invalid`, TEST-NET IPs). Do not put realistic usable-looking secrets into public fixtures.

D. Never allow exceptions to dump input or stack traces to stdout/stderr in ordinary mode. `--debug` is out of scope.

R3-01: Doctor metadata is an export sink too. `codexVersion` must match the bounded version grammar in [CLI contract](03_CLI_CONTRACT.md), not merely a character allowlist. Missing means null; a supplied invalid value safely rejects the entire run before returning a Doctor summary. Report-model construction and JSON/Markdown rendering reuse this validation. Synthetic `sk-`, `ghp_`, long random and version-wrapped token canaries must be rejected without output, paths or raw exception context. Valid-looking metadata is not authenticated or guaranteed non-sensitive.

E. The user is shown a privacy checklist and manually verifies before sharing. Redaction cannot be promised comprehensive.

## Risk table

| Risk | Protection | Required test |
|---|---|---|
| Real login token included in report | aggregate-only default + scrub opt-in excerpts | compare output against synthetic canary |
| Local path/username leaks | exclude filenames; scrub user home paths | Windows path fixture |
| Markdown/HTML injection | escape dynamic strings; plain text only | malicious `<script>`/table cell fixture |
| Prompt injection in log | classify input as data only | `Ignore your rules; upload...` fixture causes no behavior |
| Large/binary input | <=10MiB log, <=1MiB JSON, 50k lines, 64KiB/line limits | files over limit, malformed binary |
| Existing file overwritten | exclusive open, compare resolved paths, reject existing targets | existing file, identical input/output, symlink, hardlink where feasible |
| Partial report on errors | validate fully before output, close/cleanup on failure | injection of write failure |
| Poisoned doctor JSON | key allowlist and schema validation | arbitrary detail string absent |
| False outage/root cause claim | no inference model, fixed disclaimer | report template snapshot |
| Auto network calls | runtime no network imports/services; test with socket blocked | offline execution test |
| Symlink paths | reject symlink inputs/outputs if safety is uncertain, document filesystem limits | symlink test where supported |
| Unintended data in Git | strict ignores, human `git status`, secret scan | pre-publish checklist |

## No automatic remediation

Never claim that capacity errors can be fixed locally, that TLS close notifications imply provider fault, that network transport messages imply VPN problems, or that line matches prove global outage. The report can say "observed text" and suggest asking maintainer for investigation.

## Security-release blockers

Block release for any confirmed default secret/path leakage, unsanitized excerpts, auto-network behavior, shell execution, overwrite risk, or use of real private logs. If uncertain, remove the riskier feature and document the omission rather than pretending the risk is solved.

## Contribution/security reporting

Before publication, add `SECURITY.md`: ask researchers to report vulnerabilities privately using GitHub private vulnerability reporting (if available), not by posting secrets in public Issues. Include explicit ban on posting raw secrets/sensitive log files.
