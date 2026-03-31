from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest

from pipdeptree._cli import RenderContext
from pipdeptree._models.dag import PackageDAG
from pipdeptree._models.package import Package
from pipdeptree._render.json_tree import render_json_tree

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator
    from unittest.mock import Mock

    from pytest_mock import MockerFixture

    from tests.our_types import MockGraph


@pytest.mark.parametrize(
    ("version_spec_tuple", "expected_version_spec"),
    [
        pytest.param((), "Any"),
        pytest.param((">=", "2.0.0"), ">=2.0.0"),
    ],
)
def test_json_tree_given_req_package_with_version_spec(
    mock_pkgs: Callable[[MockGraph], Iterator[Mock]],
    version_spec_tuple: tuple[str, str],
    expected_version_spec: str,
    capsys: pytest.CaptureFixture[str],
) -> None:
    graph: MockGraph = {
        ("a", "1.2.3"): [("b", [version_spec_tuple])],
        ("b", "2.2.0"): [],
    }
    package_dag = PackageDAG.from_pkgs(list(mock_pkgs(graph)))

    render_json_tree(package_dag)

    captured = capsys.readouterr()
    assert captured.out.find(expected_version_spec) != -1


def test_json_tree_with_metadata(
    mock_pkgs: Callable[[MockGraph], Iterator[Mock]],
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    graph: MockGraph = {("a", "1.0"): []}
    dag = PackageDAG.from_pkgs(list(mock_pkgs(graph)))
    monkeypatch.setattr(Package, "get_metadata_dict", lambda _, fields: dict.fromkeys(fields, "test"))
    render_json_tree(dag, context=RenderContext(metadata=["license"]))
    output = capsys.readouterr().out
    assert '"metadata"' in output
    assert '"license": "test"' in output


def test_json_tree_with_computed(
    mock_pkgs: Callable[[MockGraph], Iterator[Mock]],
    capsys: pytest.CaptureFixture[str],
    mocker: MockerFixture,
) -> None:
    graph: MockGraph = {("a", "1.0"): []}
    dag = PackageDAG.from_pkgs(list(mock_pkgs(graph)))
    mocker.patch("pipdeptree._computed.distribution", return_value=MagicMock(files=None))
    render_json_tree(dag, context=RenderContext(computed=["size"]))
    output = capsys.readouterr().out
    assert '"computed"' in output
    assert '"size": "0 B"' in output
