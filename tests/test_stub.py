from __future__ import annotations

import ast
from pathlib import Path

import pytest

import pipdeptree
from pipdeptree import _rust

_STUB = Path(pipdeptree.__file__).parent / "_rust.pyi"


def _stub_signatures() -> dict[str, list[str]]:
    tree = ast.parse(_STUB.read_text(encoding="utf-8"))
    return {
        node.name: [arg.arg for arg in (*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs)]
        for node in tree.body
        if isinstance(node, ast.FunctionDef)
    }


def _stub_exports() -> list[str]:
    body = ast.parse(_STUB.read_text(encoding="utf-8")).body
    (assign,) = [node for node in body if isinstance(node, ast.Assign)]
    return list(ast.literal_eval(assign.value))


def _runtime_params(signature: str) -> list[str]:
    inner = signature.strip().removeprefix("(").removesuffix(")")
    parts = [part.strip() for part in inner.split(",") if part.strip() and part.strip() != "*"]
    return [part.lstrip("*").split("=", 1)[0].split(":", 1)[0].strip() for part in parts]


def test_rust_stub_lists_every_extension_function() -> None:
    runtime = {name for name in dir(_rust) if callable(getattr(_rust, name)) and not name.startswith("_")}
    assert set(_stub_exports()) == runtime == set(_stub_signatures())


@pytest.mark.parametrize("name", _stub_signatures())
def test_rust_stub_signature_matches_runtime(name: str) -> None:
    assert _stub_signatures()[name] == _runtime_params(getattr(_rust, name).__text_signature__)
