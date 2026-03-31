from __future__ import annotations

from textwrap import dedent
from typing import TYPE_CHECKING

from pipdeptree._cli import RenderContext
from pipdeptree._computed import ComputedValues
from pipdeptree._models.dag import PackageDAG
from pipdeptree._models.package import Package
from pipdeptree._render.json import render_json

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator
    from unittest.mock import Mock

    import pytest
    from pytest_mock import MockerFixture

    from tests.conftest import MockDistMaker
    from tests.our_types import MockGraph


def test_render_json(mock_pkgs: Callable[[MockGraph], Iterator[Mock]], capsys: pytest.CaptureFixture[str]) -> None:
    graph: MockGraph = {
        ("a", "1.2.3"): [("b", [(">=", "4.0.0")])],
        ("b", "4.5.6"): [],
    }
    expected_output = dedent("""\
     [
         {
             "package": {
                 "key": "a",
                 "package_name": "a",
                 "installed_version": "1.2.3"
             },
             "dependencies": [
                 {
                     "key": "b",
                     "package_name": "b",
                     "installed_version": "4.5.6",
                     "required_version": ">=4.0.0"
                 }
             ]
         },
         {
             "package": {
                 "key": "b",
                 "package_name": "b",
                 "installed_version": "4.5.6"
             },
             "dependencies": []
         }
     ]
    """)
    package_dag = PackageDAG.from_pkgs(list(mock_pkgs(graph)))

    render_json(package_dag)

    output = capsys.readouterr()
    assert output.out == expected_output


def test_render_json_with_extras(capsys: pytest.CaptureFixture[str], make_mock_dist: MockDistMaker) -> None:
    pkgs = [
        make_mock_dist("app", "1.0.0", requires=["foo[dev]"]),
        make_mock_dist("foo", "1.0.0", requires=["bar ; extra == 'dev'"], provides_extras=["dev"]),
        make_mock_dist("bar", "2.0.0"),
    ]
    dag = PackageDAG.from_pkgs(pkgs, include_extras=True)
    render_json(dag)
    output = capsys.readouterr().out
    assert '"extra": "dev"' in output


def test_render_json_with_metadata(
    mock_pkgs: Callable[[MockGraph], Iterator[Mock]],
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    graph: MockGraph = {("a", "1.0"): []}
    dag = PackageDAG.from_pkgs(list(mock_pkgs(graph)))
    monkeypatch.setattr(Package, "get_metadata_dict", lambda _, fields: dict.fromkeys(fields, "test"))
    render_json(dag, context=RenderContext(metadata=["license"]))
    output = capsys.readouterr().out
    assert '"metadata"' in output
    assert '"license": "test"' in output


def test_render_json_with_computed(
    mock_pkgs: Callable[[MockGraph], Iterator[Mock]],
    capsys: pytest.CaptureFixture[str],
    mocker: MockerFixture,
) -> None:
    graph: MockGraph = {("a", "1.0"): []}
    dag = PackageDAG.from_pkgs(list(mock_pkgs(graph)))
    mocker.patch("pipdeptree._computed.distribution")
    mocker.patch.object(ComputedValues, "_file_size", return_value=100)
    render_json(dag, context=RenderContext(computed=["size"]))
    output = capsys.readouterr().out
    assert '"computed"' in output
    assert '"size"' in output
