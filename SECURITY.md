# Security policy

WinAgent ReproPack is an independent offline tool, not affiliated with or endorsed by OpenAI.

**MANUAL REVIEW REQUIRED.** Never share real logs, access tokens, paths, proprietary data, Doctor diagnostics or generated reports before personally inspecting them. This tool does not guarantee that every secret or sensitive detail is detected. Default output contains counts, line numbers, timestamps and narrowly validated Doctor version metadata; even these can be sensitive. The optional excerpts are fixed canonical symptom fragments, not arbitrary raw log context.

## Supported versions

Security fixes will be targeted at the most recent public release when one exists. The current `0.1.0rc1` source candidate is not yet publicly released.

## Reporting a vulnerability privately

**When the repository is made public, its owner must immediately enable GitHub Private Vulnerability Reporting (PVR), before inviting external users:** Settings → Security and quality → Advanced Security → Private vulnerability reporting. GitHub currently offers PVR for public repositories. Once enabled, use the repository's **Security → Report a vulnerability** workflow. Do **not** put a vulnerability exploit, credentials, or real user data into public GitHub Issues.

PVR availability/enablement has **not been verified** for this repository. Until it is available, refrain from public disclosure of sensitive details. This document does not claim a working private channel or promise any response time.

Send only a minimal synthetic reproduction, the affected release, impact and suggested remediation. Never submit real personal diagnostics.

## Implementation constraints

The runtime has no third-party dependencies, network, subprocess, telemetry, automatic Doctor, upload or ambient-directory scanning. It processes explicitly selected stable local files; read bounds, strict JSON, fixed-output summaries, canonical excerpts and `O_EXCL` report creation limit exposure. Malformed inputs reject the whole operation. Error messages must not echo private input or underlying exception chains.

File identity/path checks are not atomic and cannot guarantee safety against hostile concurrent directory writers, same-inode modifications or remote mounts. Existing files are not overwritten; after certain write failures, an unidentifiable newly selected output may remain and must be reviewed manually. See `docs/04_SECURITY.md`.

The Doctor `codexVersion` import and both renderers accept only `MAJOR.MINOR.PATCH`, optionally a narrow `-alpha|beta|rc|dev[.N]` and `+build.N`. Freeform build metadata and arbitrary suffix labels are refused, instead of being silently copied into reports. This is not a guarantee that allowed numeric metadata is non-sensitive.
