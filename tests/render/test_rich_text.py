from __future__ import annotations

import sys
from typing import TYPE_CHECKING

import pytest

from pipdeptree._cli import RenderContext
from pipdeptree._models import PackageDAG
from pipdeptree._models.package import Package
from pipdeptree._render.rich_text import render_rich_text

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator
    from unittest.mock import Mock

    from pytest_mock import MockerFixture

    from tests.conftest import MockDistMaker
    from tests.our_types import MockGraph


def test_render_rich_text_missing_import(mocker: MockerFixture, example_dag: PackageDAG) -> None:
    mocker.patch.dict(sys.modules, {"rich": None, "rich.console": None, "rich.tree": None})
    with pytest.raises(SystemExit) as exc_info:
        render_rich_text(example_dag, max_depth=float("inf"))
    assert exc_info.value.code == 1


@pytest.mark.parametrize(
    ("list_all", "expected"),
    [
        pytest.param(True, ["a==3.4.0", "b==2.3.1", "c==5.10.0", "required:", "installed:"], id="list-all"),
        pytest.param(False, ["a==3.4.0", "g==6.8.3rc1"], id="not-list-all"),
    ],
)
def test_render_rich_text_list_all(
    example_dag: PackageDAG, capsys: pytest.CaptureFixture[str], list_all: bool, expected: list[str]
) -> None:
    pytest.importorskip("rich")
    render_rich_text(example_dag, max_depth=float("inf"), list_all=list_all)
    output = capsys.readouterr().out
    for item in expected:
        assert item in output


@pytest.mark.parametrize(
    "max_depth",
    [
        pytest.param(0, id="depth-0"),
        pytest.param(2, id="depth-2"),
    ],
)
def test_render_rich_text_with_max_depth(
    example_dag: PackageDAG, capsys: pytest.CaptureFixture[str], max_depth: int
) -> None:
    pytest.importorskip("rich")
    render_rich_text(example_dag, max_depth=max_depth)
    output = capsys.readouterr().out
    assert "a==3.4.0" in output


def test_render_rich_text_with_license_info(
    mock_pkgs: Callable[[MockGraph], Iterator[Mock]],
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pytest.importorskip("rich")
    graph: MockGraph = {
        ("a", "3.4.0"): [("c", [("==", "1.0.0")])],
        ("b", "2.3.1"): [],
        ("c", "1.0.0"): [],
    }
    dag = PackageDAG.from_pkgs(list(mock_pkgs(graph)))
    monkeypatch.setattr(Package, "licenses", lambda _: "(TEST)")

    render_rich_text(dag, max_depth=float("inf"), context=RenderContext(metadata=["license"]))
    output = capsys.readouterr().out
    assert "a==3.4.0" in output
    assert "(TEST License)" in output


def test_render_rich_text_with_extras(capsys: pytest.CaptureFixture[str], make_mock_dist: MockDistMaker) -> None:
    pytest.importorskip("rich")
    pkgs = [
        make_mock_dist("jira", "2.0.0", requires=["oauthlib[signedtoken]>=1.0.0"]),
        make_mock_dist(
            "oauthlib",
            "3.0.0",
            requires=["cryptography ; extra == 'signedtoken'"],
            provides_extras=["signedtoken"],
        ),
        make_mock_dist("cryptography", "2.7"),
    ]
    dag = PackageDAG.from_pkgs(pkgs, include_extras=True)
    render_rich_text(dag, max_depth=float("inf"))
    output = capsys.readouterr().out
    expected = ["jira==2.0.0", "oauthlib==3.0.0", "[extra: signedtoken]", "cryptography==2.7"]
    for item in expected:
        assert item in output


def test_render_rich_text_reversed(
    mock_pkgs: Callable[[MockGraph], Iterator[Mock]], capsys: pytest.CaptureFixture[str]
) -> None:
    pytest.importorskip("rich")
    graph: MockGraph = {
        ("a", "3.4.0"): [("b", [("==", "2.3.1")]), ("c", [("==", "1.0.0")])],
        ("b", "2.3.1"): [("c", [("==", "1.0.0")])],
        ("c", "1.0.0"): [],
    }
    dag = PackageDAG.from_pkgs(list(mock_pkgs(graph)))
    reversed_dag = dag.reverse()
    render_rich_text(reversed_dag, max_depth=float("inf"))
    output = capsys.readouterr().out
    expected = ["a==3.4.0", "b==2.3.1", "c==1.0.0", "[requires:"]
    for item in expected:
        assert item in output


def test_render_rich_text_with_circular_deps(
    mock_pkgs: Callable[[MockGraph], Iterator[Mock]], capsys: pytest.CaptureFixture[str]
) -> None:
    pytest.importorskip("rich")
    graph: MockGraph = {
        ("a", "1.0.0"): [("b", [(">=", "1.0.0")])],
        ("b", "1.0.0"): [("a", [(">=", "1.0.0")])],
    }
    dag = PackageDAG.from_pkgs(list(mock_pkgs(graph)))
    render_rich_text(dag, max_depth=float("inf"))
    output = capsys.readouterr().out
    expected = ["a==1.0.0", "b==1.0.0"]
    for item in expected:
        assert item in output


@pytest.mark.parametrize(
    ("graph", "expected"),
    [
        pytest.param(
            {("a", "1.0.0"): [("missing", [(">=", "1.0.0")])]},
            ["✗", "missing", "?"],
            id="missing",
        ),
        pytest.param(
            {
                ("a", "1.0.0"): [("b", [(">=", "2.0.0")])],
                ("b", "1.0.0"): [],
            },
            ["⚠", "b", ">=2.0.0", "1.0.0"],
            id="conflicting",
        ),
        pytest.param(
            {
                ("a", "1.0.0"): [("b", [(">=", "1.0.0"), ("<", "2.0.0")])],
                ("b", "1.5.0"): [],
            },
            ["b", ">=1.0.0,<2.0.0", "1.5.0"],
            id="satisfied",
        ),
    ],
)
def test_render_rich_text_dependency_status(
    mock_pkgs: Callable[[MockGraph], Iterator[Mock]],
    capsys: pytest.CaptureFixture[str],
    graph: MockGraph,
    expected: list[str],
) -> None:
    pytest.importorskip("rich")
    dag = PackageDAG.from_pkgs(list(mock_pkgs(graph)))
    render_rich_text(dag, max_depth=float("inf"))
    output = capsys.readouterr().out
    for item in expected:
        assert item in output
