"""Build minimal source and independent-review ZIPs with an explicit source whitelist.

Does not include the developer's review/evidence, machine build logs, Git metadata,
user logs, or any ambient files. Runs offline and never overwrites prior packages.
"""

from __future__ import annotations

import hashlib
import json
import re
import stat
import sys
import zipfile
from pathlib import Path, PurePosixPath

PUBLIC_FILES = (
    ".github/workflows/ci.yml",
    ".gitignore",
    "CHANGELOG.md",
    "CONTRIBUTING.md",
    "LICENSE",
    "MANIFEST.in",
    "README.md",
    "SECURITY.md",
    "docs/03_CLI_CONTRACT.md",
    "docs/04_SECURITY.md",
    "docs/QUICKSTART_ZH.md",
    "docs/REPORT_SCHEMA_V1.md",
    "examples/synthetic-doctor-v1.json",
    "examples/synthetic-doctor.json",
    "examples/synthetic.log",
    "pyproject.toml",
    "tools/package_release.py",
)

# Only these trees can contribute files, and only the expected extensions.
SOURCE_TREES = {
    "src/winagent_repropack": (".py",),
    "tests": (".py",),
    "tests/golden": (".md", ".json"),
}

FORBIDDEN_SEGMENTS = {".git", ".venv", ".tmp", ".cache", "artifacts", "review", "evidence"}

# Scan human-facing public docs, not intentionally adversarial synthetic tests.
DOC_EXTENSIONS = {".md", ".yml", ".toml", ".in"}
WIN_MACHINE_PATH = re.compile(r"(?i)(?<![a-z0-9])[a-z]:[\\/](?:[^\r\n]+)")


def _entries(root: Path) -> dict[str, bytes]:
    paths = {root / name for name in PUBLIC_FILES}
    for folder, extensions in SOURCE_TREES.items():
        paths.update(path for path in (root / folder).rglob("*") if path.suffix in extensions)
    result = {}
    for path in sorted(paths, key=lambda entry: str(entry.relative_to(root))):
        relative = path.relative_to(root).as_posix()
        parts = PurePosixPath(relative).parts
        if (
            not parts
            or any(part in FORBIDDEN_SEGMENTS or part.startswith(".venv-") for part in parts)
            or not path.is_file()
            or path.is_symlink()
            or not stat.S_ISREG(path.lstat().st_mode)
        ):
            raise ValueError(f"Invalid or missing public source file: {relative}")
        content = path.read_bytes()
        # Public human-facing documentation may not contain private absolute Windows paths.
        # Synthetic tests intentionally contain fake adversarial Windows paths.
        if relative.endswith(tuple(DOC_EXTENSIONS)) and WIN_MACHINE_PATH.search(
            content.decode("utf-8-sig")
        ):
            raise ValueError(f"Windows absolute path found in public documentation: {relative}")
        result[relative] = content
    return result


def _write_zip(dest: Path, files: dict[str, bytes]) -> None:
    if dest.exists():
        raise FileExistsError(f"Package already exists: {dest.name}")
    try:
        with dest.open("xb") as raw:
            with zipfile.ZipFile(raw, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as z:
                for name, data in sorted(files.items()):
                    info = zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
                    info.compress_type = zipfile.ZIP_DEFLATED
                    info.external_attr = 0o100644 << 16
                    z.writestr(info, data, compress_type=zipfile.ZIP_DEFLATED)
        with zipfile.ZipFile(dest) as z:
            if z.testzip() is not None or sorted(z.namelist()) != sorted(files):
                raise ValueError("Archive integrity check failed")
            for name, data in files.items():
                if z.read(name) != data:
                    raise ValueError("Archive readback mismatch")
    except BaseException:
        dest.unlink(missing_ok=True)
        raise


def make_packages(source: Path, output: Path) -> dict[str, object]:
    """Only selected code/docs/examples can enter either package."""
    base = _entries(source)
    if "LICENSE" not in base:
        raise ValueError("Final license is missing")
    output.mkdir(parents=True, exist_ok=True)
    release = output / "WinAgent-ReproPack-v0.1.0rc1-release-source.zip"
    audit = output / "WinAgent-ReproPack-v0.1.0rc1-independent-audit.zip"
    manifest = {
        "scope": "explicit public source whitelist; no developer evidence or private data",
        "entries": {
            name: {"sha256": hashlib.sha256(data).hexdigest(), "size": len(data)}
            for name, data in sorted(base.items())
        },
    }
    review_files = {
        **base,
        "audit/SOURCE_SHA256.json": (
            json.dumps(manifest, indent=2, ensure_ascii=True) + "\n"
        ).encode(),
        "audit/README.md": (
            "# Independent source review\n\n"
            "This archive contains the identical public source files and an independent "
            "SHA-256 manifest. It deliberately **does not** include any review/evidence "
            "build logs, local workspace paths, user diagnostics, raw files, or personal data.\n"
            "Remote GitHub Actions / Windows 11 execution is not asserted. "
            "Review code and test it in a trusted local environment before publication.\n"
        ).encode(),
    }
    _write_zip(release, base)
    _write_zip(audit, review_files)
    result = {
        "release_zip": release.name,
        "release_sha256": hashlib.sha256(release.read_bytes()).hexdigest(),
        "release_entries": len(base),
        "audit_zip": audit.name,
        "audit_sha256": hashlib.sha256(audit.read_bytes()).hexdigest(),
        "audit_entries": len(review_files),
        "excludes_internal_build_evidence": True,
    }
    (output / "archive-integrity.json").write_text(
        json.dumps(result, indent=2) + "\n", encoding="utf-8"
    )
    return result


if __name__ == "__main__":
    project_root = Path(__file__).resolve().parents[1]
    target = (
        Path(sys.argv[1]) if len(sys.argv) > 1 else project_root / "artifacts" / "release-review"
    )
    print(json.dumps(make_packages(project_root, target), indent=2))
