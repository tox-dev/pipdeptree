from __future__ import annotations

import sys
from textwrap import dedent
from typing import TYPE_CHECKING

import pytest

from pipdeptree._render.graphviz import dump_graphviz, print_graphviz

if TYPE_CHECKING:
    from pathlib import Path

    from pytest_mock import MockerFixture

    from pipdeptree._models import PackageDAG


def test_render_dot(
    capsys: pytest.CaptureFixture[str],
    example_dag: PackageDAG,
    randomized_example_dag: PackageDAG,
) -> None:
    # Check both the sorted and randomized package tree produces the same sorted graphviz output.
    for package_tree in (example_dag, randomized_example_dag):
        output = dump_graphviz(package_tree, output_format="dot")
        print_graphviz(output)
        out, _ = capsys.readouterr()
        assert out == dedent(
            """\
            digraph {
            \ta -> b [label=">=2.0.0"]
            \ta -> c [label=">=5.7.1"]
            \ta [label="a\\n3.4.0"]
            \tb -> d [label=">=2.30,<2.42"]
            \tb [label="b\\n2.3.1"]
            \tc -> d [label=">=2.30"]
            \tc -> e [label=">=0.12.1"]
            \tc [label="c\\n5.10.0"]
            \td -> e [label=">=0.9.0"]
            \td [label="d\\n2.35"]
            \te [label="e\\n0.12.1"]
            \tf -> b [label=">=2.1.0"]
            \tf [label="f\\n3.1"]
            \tg -> e [label=">=0.9.0"]
            \tg -> f [label=">=3.0.0"]
            \tg [label="g\\n6.8.3rc1"]
            }

            """,
        )


def test_render_pdf(tmp_path: Path, mocker: MockerFixture, example_dag: PackageDAG) -> None:
    output = dump_graphviz(example_dag, output_format="pdf")
    res = tmp_path / "file"
    with pytest.raises(OSError, match="Bad file"):  # noqa: PT012, SIM117 # because we reopen the file
        with res.open("wb") as buf:
            mocker.patch.object(sys, "stdout", buf)
            print_graphviz(output)
    assert res.read_bytes()[:4] == b"%PDF"


def test_render_svg(capsys: pytest.CaptureFixture[str], example_dag: PackageDAG) -> None:
    output = dump_graphviz(example_dag, output_format="svg")
    print_graphviz(output)
    out, _ = capsys.readouterr()
    assert out.startswith("<?xml")
    assert "<svg" in out
    assert out.strip().endswith("</svg>")
