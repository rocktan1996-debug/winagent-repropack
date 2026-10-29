"""R4-02: source packaging excludes all untrusted local build records."""

import importlib.util
import zipfile
from pathlib import Path

import pytest

from winagent_repropack import __version__


@pytest.fixture(scope="module")
def packer():
    path = Path(__file__).resolve().parents[1] / "tools" / "package_release.py"
    spec = importlib.util.spec_from_file_location("release_packer", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_whitelist_cannot_include_internal_build_records(packer) -> None:
    root = Path(__file__).resolve().parents[1]
    paths = packer._entries(root)
    assert "LICENSE" in paths
    assert all(not name.startswith(("review/", "artifacts/", "docs/BUILD_LOG")) for name in paths)
    assert "tools/package_release.py" in paths


def test_archive_readback_excludes_spaced_windows_path(tmp_path: Path, packer) -> None:
    root = Path(__file__).resolve().parents[1]
    marker = "C:" + "\\" + "a folder with spaces" + "\\" + "Owner Secret Path" + "\\" + "build.txt"
    # Deliberately seed a canary under a historical evidence path. No wildcard includes it.
    # The release packer must take only public source and never scan/upload this content.
    evidence = root / "review" / "evidence" / "build.txt"
    evidence.parent.mkdir(parents=True, exist_ok=True)
    original = evidence.read_bytes() if evidence.exists() else None
    try:
        evidence.write_text(f"build failed at {marker}\n", encoding="utf-8")
        out = packer.make_packages(root, tmp_path / "dist")
        for name in (out["release_zip"], out["audit_zip"]):
            with zipfile.ZipFile(tmp_path / "dist" / name) as z:
                assert z.testzip() is None
                assert all(not p.startswith("review/") for p in z.namelist())
                assert "review/evidence/build.txt" not in z.namelist()
                assert all(marker.encode() not in z.read(p) for p in z.namelist())
    finally:
        if original is None:
            evidence.unlink(missing_ok=True)
        else:
            evidence.write_bytes(original)


def test_reject_machine_path_even_if_added_to_approved_document(
    tmp_path: Path, packer, monkeypatch
) -> None:
    # A public document with an absolute path must be stopped, not silently sanitized.
    document = tmp_path / "NOTE.md"
    document.write_text("Build from C:" + "\\" + "a folder with spaces" + "\\" + "user\n")
    monkeypatch.setattr(packer, "PUBLIC_FILES", ("NOTE.md",))
    monkeypatch.setattr(packer, "SOURCE_TREES", {})
    with pytest.raises(ValueError, match="Windows absolute path"):
        packer._entries(tmp_path)


def test_packaged_quickstart_includes_feedback_target(tmp_path: Path, packer) -> None:
    root = Path(__file__).resolve().parents[1]
    out = packer.make_packages(root, tmp_path / "dist")
    for name in (out["release_zip"], out["audit_zip"]):
        with zipfile.ZipFile(tmp_path / "dist" / name) as archive:
            quickstart = archive.read("docs/QUICKSTART_ZH.md").decode("utf-8")
            assert "(USER_FEEDBACK.md)" in quickstart
            expected_feedback = (root / "docs/USER_FEEDBACK.md").read_bytes()
            assert archive.read("docs/USER_FEEDBACK.md") == expected_feedback


def test_package_names_match_runtime_version(tmp_path: Path, packer) -> None:
    root = Path(__file__).resolve().parents[1]
    result = packer.make_packages(root, tmp_path / "dist")
    assert result["release_zip"] == f"WinAgent-ReproPack-v{__version__}-release-source.zip"
    assert result["audit_zip"] == f"WinAgent-ReproPack-v{__version__}-independent-audit.zip"
