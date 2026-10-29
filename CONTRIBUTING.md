# Contributing

The current source version is `0.1.0rc2`, intended for a GitHub pre-release, not a stable or PyPI release. See [GitHub releases](https://github.com/rocktan1996-debug/winagent-repropack/releases) for published artifacts and their exact-commit CI evidence. Windows 11 has not been separately validated. Changes should continue to be tested and reviewed.

Use an existing Python 3.11+ interpreter and project-local venv. Install `.[dev]` using a project-local pip cache as in [README](README.md). Run pytest with coverage >=85%, Ruff and pip check; build sdist/wheel and smoke-test clean wheel installation for packaging changes. Use a fresh project-local pytest base directory. For PRs, include commands, exit codes, skipped tests and platform details in the PR description; never attach raw machine logs.

Keep runtime dependencies empty and analysis offline. No network, shell/subprocess, automatic Doctor, directory discovery, telemetry or upload. Read only explicit inputs. Use frozen typed models, deterministic ordering, fixed errors and bounded reads/output. Never weaken no-overwrite or privacy tests to make a feature pass.

Use synthetic fixtures only: reserved `example.invalid`, documentation IP ranges and explicitly invalid tokens. Never attach real user logs, Doctor output, account data, local home paths or credentials. Sanitized reports still need manual review. Follow [SECURITY](SECURITY.md) for vulnerability handling.

Explain concrete triggers and resulting behavior; add meaningful regressions and synchronize renderers/schema docs. Goldens must remain fabricated and be checked against independent invariants. Do not claim unrun CI/platforms passed. Historical phase evidence and owner-local management files remain local and are excluded from public artifacts.
