from __future__ import annotations

from typing import TYPE_CHECKING, Callable, Iterator

import pytest

from pipdeptree._models.dag import PackageDAG
from pipdeptree._render.json_tree import render_json_tree

if TYPE_CHECKING:
    from unittest.mock import Mock

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
) -> None:
    graph: dict[tuple[str, str], list[tuple[str, list[tuple[str, str]]]]] = {
        ("a", "1.2.3"): [("b", [version_spec_tuple])],
        ("b", "2.2.0"): [],
    }
    package_dag = PackageDAG.from_pkgs(list(mock_pkgs(graph)))
    json_tree_str = render_json_tree(package_dag)
    assert json_tree_str.find(expected_version_spec) != -1
