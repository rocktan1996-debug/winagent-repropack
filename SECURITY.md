# Security policy

WinAgent ReproPack is an independent offline tool, not affiliated with or endorsed by OpenAI.

**MANUAL REVIEW REQUIRED.** Never share real logs, access tokens, paths, proprietary data, Doctor diagnostics or generated reports before personally inspecting them. This tool does not guarantee that every secret or sensitive detail is detected. Default output contains counts, line numbers, timestamps and narrowly validated Doctor version metadata; even these can be sensitive. The optional excerpts are fixed canonical symptom fragments, not arbitrary raw log context.

## Supported versions

The current public version is the [v0.1.0rc2 pre-release](https://github.com/rocktan1996-debug/winagent-repropack/releases/tag/v0.1.0rc2). Security fixes will be evaluated for affected supported releases. No response time is guaranteed.

## Reporting a vulnerability privately

GitHub Private Vulnerability Reporting (PVR) is enabled for this public repository (confirmed by the repository owner in GitHub settings). Use the repository's **Security → Report a vulnerability** workflow to report security concerns privately. Do **not** put vulnerability details, credentials or real user data in public Issues. If the private reporting workflow becomes unavailable, do not disclose sensitive information publicly; request a private contact method from the maintainer. No response time is guaranteed.

Send only a minimal synthetic reproduction, the affected release, impact and suggested remediation. Never submit real personal diagnostics.

## Implementation constraints

The runtime has no third-party dependencies, network, subprocess, telemetry, automatic Doctor, upload or ambient-directory scanning. It processes explicitly selected stable local files; read bounds, strict JSON, fixed-output summaries, canonical excerpts and `O_EXCL` report creation limit exposure. Malformed inputs reject the whole operation. Error messages must not echo private input or underlying exception chains.

File identity/path checks are not atomic and cannot guarantee safety against hostile concurrent directory writers, same-inode modifications or remote mounts. Existing files are not overwritten; after certain write failures, an unidentifiable newly selected output may remain and must be reviewed manually. See `docs/04_SECURITY.md`.

The Doctor `codexVersion` import and both renderers accept only `MAJOR.MINOR.PATCH`, optionally a narrow `-alpha|beta|rc|dev[.N]` and `+build.N`. Freeform build metadata and arbitrary suffix labels are refused, instead of being silently copied into reports. This is not a guarantee that allowed numeric metadata is non-sensitive.
