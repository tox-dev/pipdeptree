from __future__ import annotations

from textwrap import dedent, indent
from typing import TYPE_CHECKING, Callable, Iterator

from pipdeptree._models import PackageDAG
from pipdeptree._render.mermaid import render_mermaid

if TYPE_CHECKING:
    from unittest.mock import Mock

    from tests.our_types import MockGraph


def test_render_mermaid(example_dag: PackageDAG, randomized_example_dag: PackageDAG) -> None:
    """Check both the sorted and randomized package tree produces the same sorted Mermaid output.

    Rendering a reverse dependency tree should produce the same set of nodes. Edges should have
    the same version spec label, but be resorted after swapping node positions.

    `See how this renders
    <https://mermaid.ink/img/pako:eNp9kcluwjAURX_FeutgeUhCErWs-IN21boL4yFEzYAyqKWIf-9LCISyqFf2ufe-QT6BaayDDHzZfJm9bnvyulU1wWNK3XVb50lVdF1R56Tr2-bTrazu0NfqY0aii1O_K9BK1ZKGlCn4uNAd0h1SQSXlN2qQGqQR5ezObBHbizm6QYfQIWSUi7sSHrGf2i0sR5Yji2lCZWsWQZPViijYPAs69cPnhuwetIiux1qTZubpl5xkwZOgoZgNdl7karhON4nuQRzTf3N2yaW3geaYX2L8cdj8n9xNk3dLegigcm2lC4v_exqdCvq9q5yCDK_WeT2UvQJVn9Gqh755OdYGsr4dXADDwerebQudt7qCzOuyQ3rQ9VvTVFcTPiE7wTdkgkVUSiHjlLOERUkYB3AcMeXrhKUp53GYcJ6KcwA_UwVGo_MvVqym_A?type=png)](https://mermaid.live/edit#pako:eNp9kcluwjAURX_FeutgeUhCErWs-IN21boL4yFEzYAyqKWIf-9LCISyqFf2ufe-QT6BaayDDHzZfJm9bnvyulU1wWNK3XVb50lVdF1R56Tr2-bTrazu0NfqY0aii1O_K9BK1ZKGlCn4uNAd0h1SQSXlN2qQGqQR5ezObBHbizm6QYfQIWSUi7sSHrGf2i0sR5Yji2lCZWsWQZPViijYPAs69cPnhuwetIiux1qTZubpl5xkwZOgoZgNdl7karhON4nuQRzTf3N2yaW3geaYX2L8cdj8n9xNk3dLegigcm2lC4v_exqdCvq9q5yCDK_WeT2UvQJVn9Gqh755OdYGsr4dXADDwerebQudt7qCzOuyQ3rQ9VvTVFcTPiE7wTdkgkVUSiHjlLOERUkYB3AcMeXrhKUp53GYcJ6KcwA_UwVGo_MvVqym_A>`_.
    """

    nodes = dedent(
        """\
        flowchart TD
            classDef missing stroke-dasharray: 5
            a["a\\n3.4.0"]
            b["b\\n2.3.1"]
            c["c\\n5.10.0"]
            d["d\\n2.35"]
            e["e\\n0.12.1"]
            f["f\\n3.1"]
            g["g\\n6.8.3rc1"]
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
        output = render_mermaid(package_tree)
        assert output.rstrip() == nodes + dependency_edges
        reversed_output = render_mermaid(package_tree.reverse())
        assert reversed_output.rstrip() == nodes + reverse_dependency_edges


def test_mermaid_reserved_ids(mock_pkgs: Callable[[MockGraph], Iterator[Mock]]) -> None:
    graph = {("click", "3.4.0"): [("click-extra", [(">=", "2.0.0")])]}
    package_tree = PackageDAG.from_pkgs(list(mock_pkgs(graph)))
    output = render_mermaid(package_tree)
    assert output == dedent(
        """\
        flowchart TD
            classDef missing stroke-dasharray: 5
            click-extra["click-extra\\n(missing)"]:::missing
            click_0["click\\n3.4.0"]
            click_0 -.-> click-extra
        """,
    )
