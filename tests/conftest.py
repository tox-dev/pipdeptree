from __future__ import annotations

from random import shuffle
from typing import TYPE_CHECKING, Callable, Iterator
from unittest.mock import Mock

import pytest

from pipdeptree._models import PackageDAG

if TYPE_CHECKING:
    from tests.our_types import MockGraph


@pytest.fixture(scope="session")
def mock_pkgs() -> Callable[[MockGraph], Iterator[Mock]]:
    def func(simple_graph: MockGraph) -> Iterator[Mock]:
        for node, children in simple_graph.items():
            nk, nv = node
            m = Mock(key=nk.lower(), project_name=nk, version=nv)
            as_req = Mock(key=nk, project_name=nk, specs=[("==", nv)])
            m.as_requirement = Mock(return_value=as_req)
            reqs = []
            for ck, cv in children:
                r = Mock(key=ck, project_name=ck, specs=cv)
                reqs.append(r)
            m.requires = Mock(return_value=reqs)
            yield m

    return func


@pytest.fixture()
def example_dag(mock_pkgs: Callable[[MockGraph], Iterator[Mock]]) -> PackageDAG:
    packages: MockGraph = {
        ("a", "3.4.0"): [("b", [(">=", "2.0.0")]), ("c", [(">=", "5.7.1")])],
        ("b", "2.3.1"): [("d", [(">=", "2.30"), ("<", "2.42")])],
        ("c", "5.10.0"): [("d", [(">=", "2.30")]), ("e", [(">=", "0.12.1")])],
        ("d", "2.35"): [("e", [(">=", "0.9.0")])],
        ("e", "0.12.1"): [],
        ("f", "3.1"): [("b", [(">=", "2.1.0")])],
        ("g", "6.8.3rc1"): [("e", [(">=", "0.9.0")]), ("f", [(">=", "3.0.0")])],
    }
    return PackageDAG.from_pkgs(list(mock_pkgs(packages)))


@pytest.fixture()
def randomized_example_dag(example_dag: PackageDAG) -> PackageDAG:
    """Returns a copy of the package tree fixture with dependencies in randomized order."""
    # Extract the dependency graph from the package tree and randomize it.
    randomized_graph = {}
    randomized_nodes = list(example_dag._obj.keys())  # noqa: SLF001
    shuffle(randomized_nodes)
    for node in randomized_nodes:
        edges = example_dag._obj[node].copy()  # noqa: SLF001
        shuffle(edges)
        randomized_graph[node] = edges
    assert set(randomized_graph) == set(example_dag._obj)  # noqa: SLF001

    # Create a randomized package tree.
    randomized_dag = PackageDAG(randomized_graph)
    assert len(example_dag) == len(randomized_dag)
    return randomized_dag
