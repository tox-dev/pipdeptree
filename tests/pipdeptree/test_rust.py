from __future__ import annotations

import ast
from importlib import reload
from pathlib import Path
from typing import TYPE_CHECKING, Final

import pytest

import pipdeptree
import pipdeptree._rust as rust  # ruff:ignore[import-private-name]  # paired test exercises the native boundary
from pipdeptree import version

if TYPE_CHECKING:
    from pytest_mock import MockerFixture

_STUB: Final[Path] = Path(pipdeptree.__file__).parent / "_rust.pyi"


def _stub_signatures() -> dict[str, list[str]]:
    tree = ast.parse(_STUB.read_text(encoding="utf-8"))
    return {
        node.name: [arg.arg for arg in (*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs)]
        for node in tree.body
        if isinstance(node, ast.FunctionDef)
    }


def test_rust_stub_lists_every_extension_function() -> None:
    runtime = {name for name in dir(rust) if callable(getattr(rust, name)) and not name.startswith("_")}
    assert set(_stub_exports()) == runtime == set(_stub_signatures())


def _stub_exports() -> list[str]:
    body = ast.parse(_STUB.read_text(encoding="utf-8")).body
    (assign,) = [node for node in body if isinstance(node, ast.Assign)]
    return list(ast.literal_eval(assign.value))


@pytest.mark.parametrize("name", _stub_signatures())
def test_rust_stub_signature_matches_runtime(name: str) -> None:
    assert _stub_signatures()[name] == _runtime_params(getattr(rust, name).__text_signature__)


def _runtime_params(signature: str) -> list[str]:
    inner = signature.strip().removeprefix("(").removesuffix(")")
    parts = [part.strip() for part in inner.split(",") if part.strip() and part.strip() != "*"]
    return [part.lstrip("*").split("=", 1)[0].split(":", 1)[0].strip() for part in parts]


@pytest.mark.parametrize(
    ("release", "expected"),
    [
        pytest.param("4.1.0", (4, 1, 0), id="final"),
        pytest.param("4.1.0b1", (4, 1, "0b1"), id="beta"),
        pytest.param("4.1.0rc1.dev3", (4, 1, "0rc1", "dev3"), id="dev"),
    ],
)
def test_version_tuple(mocker: MockerFixture, release: str, expected: tuple[int | str, ...]) -> None:
    mocker.patch.object(rust, "version", return_value=release, autospec=True)
    try:
        assert reload(version).version_tuple == expected
    finally:
        mocker.stopall()
        reload(version)
