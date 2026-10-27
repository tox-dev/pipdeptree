"""Release wheels carry only the native libraries needed by their platform."""

from __future__ import annotations

from typing import TYPE_CHECKING
from zipfile import ZipFile

import pytest

from tools.check_release_wheels import main

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path


@pytest.fixture
def make_wheel(tmp_path: Path) -> Callable[[str, dict[str, bytes]], Path]:
    def create(name: str, members: dict[str, bytes]) -> Path:
        with ZipFile(tmp_path / name, "w") as archive:
            archive.writestr("pipdeptree/__init__.py", b"")
            archive.writestr("pipdeptree-1.dist-info/METADATA", "Name: pipdeptree\n")
            for member, content in members.items():
                archive.writestr(member, content)
        return tmp_path

    return create


@pytest.mark.parametrize(
    ("name", "extension", "libraries"),
    [
        pytest.param("pipdeptree-1-cp311-abi3-manylinux_2_28_x86_64.whl", "pipdeptree/_rust.abi3.so", {}, id="plain"),
        pytest.param("pipdeptree-1-cp311-abi3-macosx_11_0_arm64.whl", "pipdeptree/_rust.abi3.so", {}, id="macos"),
        pytest.param(
            "pipdeptree-1-cp311-abi3-musllinux_1_2_x86_64.whl",
            "pipdeptree/_rust.abi3.so",
            {"pipdeptree.libs/libgcc_s-0cd532bd.so.1": b"\x7fELF"},
            id="musllinux",
        ),
        pytest.param(
            "pipdeptree-1-pp311-pypy311_pp80-win_amd64.whl",
            "pipdeptree/_rust.pypy311-pp80-win_amd64.pyd",
            {"pipdeptree.libs/vcruntime140-052ad6a20d375957e82aa6a3c441ea54.dll": b"MZ"},
            id="windows-pypy",
        ),
    ],
)
def test_release_wheels_accept_expected_libraries(
    make_wheel: Callable[[str, dict[str, bytes]], Path],
    name: str,
    extension: str,
    libraries: dict[str, bytes],
) -> None:
    magic = b"\xcf\xfa\xed\xfe" if "macosx_" in name else b"MZ" if "win_" in name else b"\x7fELF"
    directory = make_wheel(name, {extension: magic, **libraries})

    assert main([str(directory)]) == 1


@pytest.mark.parametrize(
    ("name", "members", "error"),
    [
        pytest.param(
            "pipdeptree-1-cp311-abi3-manylinux_2_28_x86_64.whl", {}, "expected one Rust extension", id="no-extension"
        ),
        pytest.param(
            "pipdeptree-1-cp311-abi3-manylinux_2_28_x86_64.whl",
            {"pipdeptree/_rust.abi3.so": b"nope"},
            "invalid Rust extension",
            id="invalid-extension",
        ),
        pytest.param(
            "pipdeptree-1-cp311-abi3-manylinux_2_28_x86_64.whl",
            {"pipdeptree/_rust.abi3.so": b"\x7fELF", "pipdeptree.libs/libgcc_s-0cd532bd.so.1": b"\x7fELF"},
            "unexpected bundled libraries",
            id="unexpected-library",
        ),
        pytest.param(
            "pipdeptree-1-cp311-abi3-manylinux_2_28_x86_64.whl",
            {"pipdeptree/_rust.abi3.so": b"\x7fELF", "rogue/extra": b"data"},
            "unexpected wheel roots",
            id="unexpected-root",
        ),
        pytest.param(
            "pipdeptree-1-cp311-abi3-musllinux_1_2_x86_64.whl",
            {"pipdeptree/_rust.abi3.so": b"\x7fELF"},
            "unexpected bundled libraries",
            id="missing-library",
        ),
        pytest.param(
            "pipdeptree-1-cp311-abi3-musllinux_1_2_x86_64.whl",
            {
                "pipdeptree/_rust.abi3.so": b"\x7fELF",
                "pipdeptree.libs/libgcc_s-0cd532bd.so.1": b"\x7fELF",
                "pipdeptree.libs/extra.so": b"\x7fELF",
            },
            "unexpected bundled libraries",
            id="extra-library",
        ),
        pytest.param(
            "pipdeptree-1-cp311-abi3-musllinux_1_2_x86_64.whl",
            {"pipdeptree/_rust.abi3.so": b"\x7fELF", "pipdeptree.libs/libgcc_s-short.so.1": b"\x7fELF"},
            "invalid bundled library name",
            id="wrong-hash",
        ),
        pytest.param(
            "pipdeptree-1-pp311-pypy311_pp80-win_amd64.whl",
            {
                "pipdeptree/_rust.pypy311-pp80-win_amd64.pyd": b"MZ",
                "pipdeptree.libs/vcruntime140-052ad6a20d375957e82aa6a3c441ea54.dll": b"wrong",
            },
            "invalid bundled library",
            id="invalid-library",
        ),
    ],
)
def test_release_wheels_reject_unexpected_contents(
    make_wheel: Callable[[str, dict[str, bytes]], Path], name: str, members: dict[str, bytes], error: str
) -> None:
    directory = make_wheel(name, members)

    with pytest.raises(SystemExit, match=error):
        main([str(directory)])


def test_release_wheels_require_a_wheel(tmp_path: Path) -> None:
    with pytest.raises(SystemExit, match="no wheels"):
        main([str(tmp_path)])
