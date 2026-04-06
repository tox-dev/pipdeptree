from __future__ import annotations

from textwrap import dedent, indent
from typing import TYPE_CHECKING

from pipdeptree._cli import RenderContext
from pipdeptree._models import PackageDAG
from pipdeptree._models.package import Package
from pipdeptree._render.mermaid import render_mermaid

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator
    from unittest.mock import Mock

    import pytest

    from tests.our_types import MockGraph


def test_render_mermaid(
    example_dag: PackageDAG, randomized_example_dag: PackageDAG, capsys: pytest.CaptureFixture[str]
) -> None:
    """Check both the sorted and randomized package tree produces the same sorted Mermaid output.

    Rendering a reverse dependency tree should produce the same set of nodes. Edges should have the same version spec
    label, but be resorted after swapping node positions.

    `See how this renders <https://mermaid.ink/img/pako:eNp9kcluwjAURX_FeutgeUhCErWs-IN21boL4yFEzYAyqKWIf-9LCISyqFf2ufe-QT6BaayDDHzZfJm9bnvyulU1wWNK3XVb50lVdF1R56Tr2-bTrazu0NfqY0aii1O_K9BK1ZKGlCn4uNAd0h1SQSXlN2qQGqQR5ezObBHbizm6QYfQIWSUi7sSHrGf2i0sR5Yji2lCZWsWQZPViijYPAs69cPnhuwetIiux1qTZubpl5xkwZOgoZgNdl7karhON4nuQRzTf3N2yaW3geaYX2L8cdj8n9xNk3dLegigcm2lC4v_exqdCvq9q5yCDK_WeT2UvQJVn9Gqh755OdYGsr4dXADDwerebQudt7qCzOuyQ3rQ9VvTVFcTPiE7wTdkgkVUSiHjlLOERUkYB3AcMeXrhKUp53GYcJ6KcwA_UwVGo_MvVqym_A?type=png)](https://mermaid.live/edit#pako:eNp9kcluwjAURX_FeutgeUhCErWs-IN21boL4yFEzYAyqKWIf-9LCISyqFf2ufe-QT6BaayDDHzZfJm9bnvyulU1wWNK3XVb50lVdF1R56Tr2-bTrazu0NfqY0aii1O_K9BK1ZKGlCn4uNAd0h1SQSXlN2qQGqQR5ezObBHbizm6QYfQIWSUi7sSHrGf2i0sR5Yji2lCZWsWQZPViijYPAs69cPnhuwetIiux1qTZubpl5xkwZOgoZgNdl7karhON4nuQRzTf3N2yaW3geaYX2L8cdj8n9xNk3dLegigcm2lC4v_exqdCvq9q5yCDK_WeT2UvQJVn9Gqh755OdYGsr4dXADDwerebQudt7qCzOuyQ3rQ9VvTVFcTPiE7wTdkgkVUSiHjlLOERUkYB3AcMeXrhKUp53GYcJ6KcwA_UwVGo_MvVqym_A>`_.

    """

    nodes = dedent(
        """\
        flowchart TD
            classDef missing stroke-dasharray: 5
            a["a<br/>3.4.0"]
            b["b<br/>2.3.1"]
            c["c<br/>5.10.0"]
            d["d<br/>2.35"]
            e["e<br/>0.12.1"]
            f["f<br/>3.1"]
            g["g<br/>6.8.3rc1"]
        """,
    )
    dependency_edges = indent(
        dedent(
            """\
            a -- ">=2.0.0" --> b
            a -- ">=5.7.1" --> c
            b -- ">=2.30,<2.42" --> d
            c -- ">=0.12.1" --> e
            c -- ">=2.30" --> d
            d -- ">=0.9.0" --> e
            f -- ">=2.1.0" --> b
            g -- ">=0.9.0" --> e
            g -- ">=3.0.0" --> f
        """,
        ),
        " " * 4,
    ).rstrip()
    reverse_dependency_edges = indent(
        dedent(
            """\
            b -- ">=2.0.0" --> a
            b -- ">=2.1.0" --> f
            c -- ">=5.7.1" --> a
            d -- ">=2.30" --> c
            d -- ">=2.30,<2.42" --> b
            e -- ">=0.12.1" --> c
            e -- ">=0.9.0" --> d
            e -- ">=0.9.0" --> g
            f -- ">=3.0.0" --> g
        """,
        ),
        " " * 4,
    ).rstrip()

    for package_tree in (example_dag, randomized_example_dag):
        render_mermaid(package_tree)
        output = capsys.readouterr()
        assert output.out.rstrip() == nodes + dependency_edges

        render_mermaid(package_tree.reverse())
        output = capsys.readouterr()
        assert output.out.rstrip() == nodes + reverse_dependency_edges


def test_mermaid_reserved_ids(
    mock_pkgs: Callable[[MockGraph], Iterator[Mock]], capsys: pytest.CaptureFixture[str]
) -> None:
    graph = {("click", "3.4.0"): [("click-extra", [(">=", "2.0.0")])]}
    package_tree = PackageDAG.from_pkgs(list(mock_pkgs(graph)))

    render_mermaid(package_tree)

    output = capsys.readouterr()
    assert (
        output.out.rstrip()
        == dedent(
            """\
        flowchart TD
            classDef missing stroke-dasharray: 5
            click-extra["click-extra<br/>(missing)"]:::missing
            click_0["click<br/>3.4.0"]
            click_0 -.-> click-extra
        """,
        ).rstrip()
    )


def test_mermaid_with_metadata(
    mock_pkgs: Callable[[MockGraph], Iterator[Mock]],
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    graph: MockGraph = {("a", "1.0"): [("b", [(">=", "1.0")])], ("b", "1.0"): []}
    dag = PackageDAG.from_pkgs(list(mock_pkgs(graph)))
    monkeypatch.setattr(Package, "licenses", lambda _: "(MIT)")
    ctx = RenderContext(metadata=["license"])
    render_mermaid(dag, context=ctx)
    output = capsys.readouterr().out
    assert "MIT License" in output


def test_mermaid_reversed_with_metadata(
    mock_pkgs: Callable[[MockGraph], Iterator[Mock]],
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    graph: MockGraph = {("a", "1.0"): [("b", [(">=", "1.0")])], ("b", "1.0"): []}
    dag = PackageDAG.from_pkgs(list(mock_pkgs(graph)))
    monkeypatch.setattr(Package, "licenses", lambda _: "(MIT)")
    ctx = RenderContext(metadata=["license"])
    render_mermaid(dag.reverse(), context=ctx)
    output = capsys.readouterr().out
    assert "MIT License" in output
