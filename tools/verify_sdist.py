"""Check that a built source distribution preserves the public packaging inputs.

For locally built CI artifacts, not untrusted archive validation. Checks required
inputs only; additional members are not audited. Reads without extraction or execution.
"""

from __future__ import annotations

import argparse
import tarfile
from pathlib import Path

from package_release import _entries


def verify_sdist(archive: Path, root: Path) -> None:
    expected = _entries(root)
    with tarfile.open(archive, "r:gz") as source:
        members = source.getmembers()
        prefixes = {member.name.split("/", 1)[0] for member in members}
        if len(prefixes) != 1:
            raise ValueError("Source distribution must have exactly one top-level directory")
        prefix = prefixes.pop()
        for name, content in expected.items():
            matches = [member for member in members if member.name == f"{prefix}/{name}"]
            if len(matches) != 1 or not matches[0].isfile():
                raise ValueError(f"Missing, duplicate or non-regular public source: {name}")
            member = matches[0]
            if member.size != len(content):
                raise ValueError(f"Source distribution content differs: {name}")
            stream = source.extractfile(member)
            if stream is None or stream.read(len(content) + 1) != content:
                raise ValueError(f"Source distribution content differs: {name}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path, help="Directory with one built ReproPack sdist")
    args = parser.parse_args()
    try:
        archives = sorted(args.directory.glob("winagent_repropack-*.tar.gz"))
        if len(archives) != 1:
            raise ValueError("Select a directory containing exactly one ReproPack sdist")
        verify_sdist(archives[0], Path(__file__).resolve().parents[1])
    except (OSError, ValueError, tarfile.TarError) as error:
        parser.exit(1, f"Source distribution verification failed: {error}\n")
    print("PASS: sdist contains identical public packaging inputs; no extraction or execution.")


if __name__ == "__main__":
    main()
