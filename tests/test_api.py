from __future__ import annotations

import json
import sys
from typing import TYPE_CHECKING, cast

import pytest

import pipdeptree

if TYPE_CHECKING:
    from collections.abc import Callable, Container
    from pathlib import Path
    from typing import Protocol

    class MimeBundle(Protocol):
        def _repr_mimebundle_(
            self,
            include: Container[str] | None = None,
            exclude: Container[str] | None = None,
        ) -> dict[str, str]: ...


@pytest.mark.parametrize(
    ("output_format", "expected"),
    [
        pytest.param("json", '"package_name": "pipdeptree"', id="json"),
        pytest.param("json-tree", '"dependencies"', id="json-tree"),
        pytest.param("mermaid", "flowchart TD", id="mermaid"),
        pytest.param("dot", "digraph {", id="graphviz"),
    ],
)
def test_render_formats(output_format: str, expected: str) -> None:
    assert expected in pipdeptree.render(packages="pipdeptree", output_format=output_format)


def test_render_text_notebook_bundle() -> None:
    result = pipdeptree.render(packages="pipdeptree", depth=0)

    display = cast("MimeBundle", result)
    bundle = display._repr_mimebundle_()

    assert (
        isinstance(result, str),
        result.strip(),
        set(bundle),
        bundle["text/plain"],
        display._repr_mimebundle_(include={"text/plain"}),
    ) == (
        True,
        f"pipdeptree=={pipdeptree.__version__}",
        {"text/vnd.mermaid", "text/html", "text/plain"},
        result,
        {"text/plain": result},
    )


def test_render_text_notebook_bundle_respects_exclude() -> None:
    display = cast("MimeBundle", pipdeptree.render(packages="pipdeptree", depth=0))

    assert "text/html" not in display._repr_mimebundle_(exclude={"text/html"})


def test_render_text_notebook_bundle_is_repeatable() -> None:
    display = cast("MimeBundle", pipdeptree.render(packages="pipdeptree", depth=0))

    assert display._repr_mimebundle_() == display._repr_mimebundle_()


@pytest.mark.parametrize(
    ("output_format", "expected"),
    [
        pytest.param("json", '"total_packages"', id="json"),
        pytest.param("rich", "environment summary", id="rich"),
    ],
)
def test_render_summary_formats(output_format: str, expected: str) -> None:
    result = pipdeptree.render(summary=True, output_format=output_format)

    assert (type(result), expected in result) == (str, True)


def test_render_summary_notebook_bundle() -> None:
    result = pipdeptree.render(summary=True)

    display = cast("MimeBundle", result)
    bundle = display._repr_mimebundle_()

    assert (
        result.startswith("total packages:"),
        set(bundle),
        bundle["text/html"].startswith("<table>\n<tr><th>metric</th><th>value</th></tr>"),
        "<tr><td>total packages</td><td>" in bundle["text/html"],
        display._repr_mimebundle_(include={"text/plain"}),
    ) == (True, {"text/html", "text/plain"}, True, True, {"text/plain": result})


def test_render_summary_notebook_bundle_respects_exclude() -> None:
    display = cast("MimeBundle", pipdeptree.render(summary=True))

    assert "text/html" not in display._repr_mimebundle_(exclude={"text/html"})


@pytest.mark.parametrize("extras", [pytest.param(True, id="bool"), pytest.param("explicit", id="named")])
def test_render_explicit_extras(extras: bool | str) -> None:
    result = pipdeptree.render(
        packages="pipdeptree[test]",
        depth=1,
        extras=extras,
        encoding="ascii",
    )

    assert "\n  - covdefaults" in result


def test_render_reverse() -> None:
    result = pipdeptree.render(packages="nab-index", extras="active", reverse=True, depth=1)

    assert "pipdeptree==" in result


def test_render_environment_selection() -> None:
    local = pipdeptree.render(packages="pipdeptree", local_only=True, depth=0)
    user = pipdeptree.render(packages="pipdeptree", user_only=True, depth=0)

    assert (local.strip(), user.strip()) == (f"pipdeptree=={pipdeptree.__version__}", "")


def test_render_excludes_package() -> None:
    result = pipdeptree.render(exclude="pipdeptree")

    assert (bool(result), "pipdeptree==" in result) == (True, False)


def test_render_empty_filter() -> None:
    assert not pipdeptree.render(packages="package-that-does-not-exist")


def test_render_empty_filter_with_graph_warning(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = tmp_path / "root-1.dist-info"
    root.mkdir()
    (root / "METADATA").write_text("Name: root\nVersion: 1\nRequires-Dist: child>=2\n")
    child = tmp_path / "child-1.dist-info"
    child.mkdir()
    (child / "METADATA").write_text("Name: child\nVersion: 1\n")
    monkeypatch.setattr(sys, "path", [str(tmp_path)])

    assert not pipdeptree.render(packages="package-that-does-not-exist", warn="suppress")


@pytest.mark.parametrize(
    ("call", "expected"),
    [
        pytest.param(
            lambda: pipdeptree.render(summary=True, output_format="mermaid"), "summary output_format", id="summary"
        ),
        pytest.param(lambda: pipdeptree.render(output_format="xml"), "unknown output_format", id="unknown"),
        pytest.param(lambda: pipdeptree.render(output_format="png"), "binary Graphviz formats", id="binary"),
        pytest.param(lambda: pipdeptree.render(warn="unknown"), "invalid value", id="native"),
        pytest.param(
            lambda: pipdeptree.render(python="/does/not/exist"), "Failed to query custom interpreter", id="python"
        ),
    ],
)
def test_render_rejects_invalid_options(call: Callable[[], str], expected: str) -> None:
    with pytest.raises(ValueError, match=expected):
        call()


def test_render_summary_json_is_valid() -> None:
    assert json.loads(pipdeptree.render(summary=True, output_format="json"))["total_packages"] > 0
