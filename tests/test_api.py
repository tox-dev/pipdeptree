from __future__ import annotations

import json
import py_compile
import re
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
        pytest.param("cyclonedx-json", '"bomFormat": "CycloneDX"', id="cyclonedx-json"),
        pytest.param("json-tree", '"dependencies"', id="json-tree"),
        pytest.param("mermaid", "flowchart TD", id="mermaid"),
        pytest.param("dot", "digraph {", id="graphviz"),
    ],
)
def test_render_formats(output_format: str, expected: str) -> None:
    assert expected in pipdeptree.render(packages="pipdeptree", output_format=output_format)


@pytest.mark.parametrize("output_format", ["text", "json", "json-tree", "cyclonedx-json", "mermaid", "dot"])
@pytest.mark.parametrize("module_kind", ["source", "package", "bytecode"])
def test_render_ignores_module_versions(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    output_format: str,
    module_kind: str,
) -> None:
    metadata = tmp_path / "root-1.dist-info"
    metadata.mkdir()
    (metadata / "METADATA").write_text("Name: root\nVersion: 1\nRequires-Dist: fallbackdemo>=2\n")
    marker = tmp_path / "imported"
    source = tmp_path / "fallbackdemo.py"
    if module_kind == "package":
        package = tmp_path / "fallbackdemo"
        package.mkdir()
        source = package / "__init__.py"
    source.write_text(
        f"from pathlib import Path\nPath({str(marker)!r}).write_text('imported')\n__version__ = '9.8.7.6'\n"
    )
    if module_kind == "bytecode":
        py_compile.compile(str(source), cfile=str(tmp_path / "fallbackdemo.pyc"), doraise=True)
        source.unlink()
    monkeypatch.setattr(sys, "path", [str(tmp_path)])

    result = pipdeptree.render(output_format=output_format)

    assert not marker.exists()
    assert "9.8.7.6" not in result
    assert "fallbackdemo" in result
    if output_format == "text":
        assert "installed: ?" in result
        with pytest.raises(ValueError, match="fallbackdemo"):
            pipdeptree.render(warn="fail")
        assert not marker.exists()


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


def test_render_summary_notebook_bundle_keeps_license_line_separator(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    metadata = tmp_path / "demo-1.dist-info"
    metadata.mkdir()
    (metadata / "METADATA").write_text(
        "Name: demo\nVersion: 1\nLicense-Expression: MIT\u2028copyleft licenses: no\n", encoding="utf-8"
    )
    monkeypatch.setattr(sys, "path", [str(tmp_path)])

    html = cast("MimeBundle", pipdeptree.render(summary=True))._repr_mimebundle_()["text/html"]

    assert re.findall(r"<tr><td>(.*?)</td><td>(.*?)</td></tr>", html) == [
        ("total packages", "1"),
        ("direct dependencies", "1"),
        ("transitive dependencies", "0"),
        ("max depth", "1"),
        ("cyclic dependencies", "0"),
        ("missing dependencies", "0"),
        ("conflicting dependencies", "0 (0 edges)"),
        ("licenses", "(MIT\u2028copyleft licenses: no): 1"),
        ("unknown licenses", "0"),
        ("copyleft licenses", "no"),
        ("min requires-python", "n/a"),
        ("total size", "0 B"),
    ]


def test_render_summary_notebook_bundle_respects_exclude() -> None:
    display = cast("MimeBundle", pipdeptree.render(summary=True))

    assert "text/html" not in display._repr_mimebundle_(exclude={"text/html"})


@pytest.mark.parametrize("extras", [pytest.param(True, id="bool"), pytest.param("explicit", id="named")])
def test_render_explicit_extras(extras: bool | str, package_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "path", [str(package_path)])

    result = pipdeptree.render(packages="root[feature]", depth=1, extras=extras, encoding="ascii")

    assert "\n  - optional [required: Any, installed: 1, extra: feature]" in result


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


def test_render_suppress_writes_warnings(
    conflicting_documentation_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(sys, "path", [str(conflicting_documentation_path)])

    rendered = pipdeptree.render(warn="suppress")

    assert ("Jinja2==2.11.2" in rendered, "dependency problems found" in capsys.readouterr().err) == (True, True)


def test_render_fail_raises_on_problems(conflicting_documentation_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "path", [str(conflicting_documentation_path)])

    with pytest.raises(ValueError, match="dependency problems found"):
        pipdeptree.render(warn="fail")


def test_render_extras_disabled_by_default(package_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "path", [str(package_path)])

    assert ("optional" in pipdeptree.render(packages="root", extras=False)) is False


@pytest.mark.parametrize(
    ("call", "expected"),
    [
        pytest.param(
            lambda: pipdeptree.render(summary=True, output_format="mermaid"), "summary output_format", id="summary"
        ),
        pytest.param(lambda: pipdeptree.render(output_format="xml"), "unknown output_format", id="unknown"),
        pytest.param(lambda: pipdeptree.render(output_format="png"), "Graphviz png output needs", id="graphviz"),
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


def test_render_raises_on_trees_past_the_nesting_limit(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    for position in range(202):
        dist_info = tmp_path / f"p{position:05}-1.dist-info"
        dist_info.mkdir()
        requires = f"Requires-Dist: p{position + 1:05}\n" if position < 201 else ""
        (dist_info / "METADATA").write_text(f"Name: p{position:05}\nVersion: 1\n{requires}")
    monkeypatch.setattr(sys, "path", [str(tmp_path)])

    with pytest.raises(ValueError, match="nests deeper than 200 levels"):
        pipdeptree.render(output_format="json-tree")
