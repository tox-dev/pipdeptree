"""Validate bundled native libraries in release wheels."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import TYPE_CHECKING
from zipfile import ZipFile

if TYPE_CHECKING:
    from collections.abc import Sequence


def main(argv: Sequence[str] | None = None) -> int:
    """Reject unreviewed libraries before trusted publishing uploads the wheels."""
    parser = argparse.ArgumentParser(description="validate release wheel libraries")
    parser.add_argument("directory", type=Path)
    directory = parser.parse_args(argv).directory
    wheels = sorted(directory.glob("*.whl"))
    if not wheels:
        msg = f"no wheels in {directory}"
        raise SystemExit(msg)
    for wheel in wheels:
        _check_wheel(wheel)
    return len(wheels)


def _check_wheel(wheel: Path) -> None:
    with ZipFile(wheel) as archive:
        members = archive.namelist()
        roots = {name.split("/", 1)[0] for name in members}
        metadata = {root for root in roots if root.startswith("pipdeptree-") and root.endswith(".dist-info")}
        libraries = [name for name in members if name.startswith("pipdeptree.libs/") and not name.endswith("/")]
        if len(metadata) != 1 or roots != {"pipdeptree", *metadata} | ({"pipdeptree.libs"} if libraries else set()):
            msg = f"unexpected wheel roots in {wheel.name}: {sorted(roots)}"
            raise SystemExit(msg)
        extensions = [
            name for name in members if name.startswith("pipdeptree/_rust.") and name.endswith((".so", ".pyd"))
        ]
        if len(extensions) != 1:
            msg = f"expected one Rust extension in {wheel.name}"
            raise SystemExit(msg)
        magic = b"\xcf\xfa\xed\xfe" if "macosx_" in wheel.name else b"MZ" if "win_" in wheel.name else b"\x7fELF"
        with archive.open(extensions[0]) as stream:
            if not stream.read(4).startswith(magic):
                msg = f"invalid Rust extension in {wheel.name}"
                raise SystemExit(msg)
        if "musllinux_" in wheel.name:
            prefix, suffix, magic, digest_length = "pipdeptree.libs/libgcc_s-", ".so.1", b"\x7fELF", 8
        elif "-pp311-pypy311_pp80-win_amd64.whl" in wheel.name:
            prefix, suffix, magic, digest_length = "pipdeptree.libs/vcruntime140-", ".dll", b"MZ", 32
        elif libraries:
            msg = f"unexpected bundled libraries in {wheel.name}: {libraries}"
            raise SystemExit(msg)
        else:
            return
        if len(libraries) != 1 or not libraries[0].startswith(prefix) or not libraries[0].endswith(suffix):
            msg = f"unexpected bundled libraries in {wheel.name}: {libraries}"
            raise SystemExit(msg)
        digest = libraries[0][len(prefix) : -len(suffix)]
        if len(digest) != digest_length or any(char not in "0123456789abcdef" for char in digest):
            msg = f"invalid bundled library name in {wheel.name}: {libraries[0]}"
            raise SystemExit(msg)
        with archive.open(libraries[0]) as stream:
            if not stream.read(4).startswith(magic):
                msg = f"invalid bundled library in {wheel.name}: {libraries[0]}"
                raise SystemExit(msg)


if __name__ == "__main__":
    main()


__all__ = [
    "main",
]
