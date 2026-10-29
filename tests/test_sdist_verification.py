"""Synthetic source archives must preserve required packaging inputs exactly."""

import importlib.util
import io
import tarfile
from pathlib import Path

import pytest


@pytest.fixture
def verifier(monkeypatch):
    tools = Path(__file__).resolve().parents[1] / "tools"
    monkeypatch.syspath_prepend(str(tools))
    spec = importlib.util.spec_from_file_location("sdist_verifier", tools / "verify_sdist.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "_entries", lambda root: {"required.txt": b"synthetic\n"})
    return module


@pytest.mark.parametrize(
    "case", ["valid", "missing", "changed", "size", "duplicate", "symlink", "extra-root"]
)
def test_sdist_public_input_integrity(tmp_path, verifier, case):
    archive = tmp_path / "synthetic.tar.gz"
    with tarfile.open(archive, "w:gz") as output:
        directory = tarfile.TarInfo("synthetic")
        directory.type = tarfile.DIRTYPE
        output.addfile(directory)
        if case != "missing":
            member = tarfile.TarInfo("synthetic/required.txt")
            content = b"different\n" if case == "changed" else b"synthetic\n"
            if case == "size":
                content += b"extra"
            member.size = len(content)
            if case == "symlink":
                member.type = tarfile.SYMTYPE
                member.linkname = "elsewhere"
                member.size = 0
                output.addfile(member)
            else:
                output.addfile(member, io.BytesIO(content))
            if case == "duplicate":
                output.addfile(member, io.BytesIO(content))
            if case == "extra-root":
                output.addfile(tarfile.TarInfo("elsewhere"))
    before = archive.read_bytes()
    if case == "valid":
        verifier.verify_sdist(archive, tmp_path)
    else:
        with pytest.raises(ValueError):
            verifier.verify_sdist(archive, tmp_path)
    assert archive.read_bytes() == before
