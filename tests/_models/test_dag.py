from __future__ import annotations

from itertools import chain
from typing import TYPE_CHECKING, Any, Callable, Iterator

import pytest

from pipdeptree._models import DistPackage, PackageDAG, ReqPackage, ReversedPackageDAG

if TYPE_CHECKING:
    from unittest.mock import Mock

    from tests.our_types import MockGraph


def test_package_dag_get_node_as_parent(example_dag: PackageDAG) -> None:
    node = example_dag.get_node_as_parent("b")
    assert node is not None
    assert node.key == "b"
    node = example_dag.get_node_as_parent("c")
    assert node is not None
    assert node.key == "c"


@pytest.fixture(scope="session")
def t_fnmatch(mock_pkgs: Callable[[MockGraph], Iterator[Mock]]) -> PackageDAG:
    graph: MockGraph = {
        ("a-a", "1"): [("a-b", []), ("a-c", [])],
        ("a-b", "1"): [("a-c", [])],
        ("b-a", "1"): [("b-b", [])],
        ("b-b", "1"): [("a-b", [])],
    }
    return PackageDAG.from_pkgs(list(mock_pkgs(graph)))


def dag_to_dict(g: PackageDAG) -> dict[str, list[str]]:
    return {k.key: [v.key for v in vs] for k, vs in g._obj.items()}  # noqa: SLF001


def test_package_dag_filter_fnmatch_include_a(t_fnmatch: PackageDAG) -> None:
    # test include for a-*in the result we got only a-* nodes
    graph = dag_to_dict(t_fnmatch.filter_nodes(["a-*"], None))
    assert graph == {"a-a": ["a-b", "a-c"], "a-b": ["a-c"]}


def test_package_dag_filter_fnmatch_include_b(t_fnmatch: PackageDAG) -> None:
    # test include for b-*, which has a-b and a-c in tree, but not a-a
    # in the result we got the b-* nodes plus the a-b node as child in the tree
    graph = dag_to_dict(t_fnmatch.filter_nodes(["b-*"], None))
    assert graph == {"b-a": ["b-b"], "b-b": ["a-b"], "a-b": ["a-c"]}


def test_package_dag_filter_fnmatch_exclude_c(t_fnmatch: PackageDAG) -> None:
    # test exclude for b-* in the result we got only a-* nodes
    graph = dag_to_dict(t_fnmatch.filter_nodes(None, {"b-*"}))
    assert graph == {"a-a": ["a-b", "a-c"], "a-b": ["a-c"]}


def test_package_dag_filter_fnmatch_exclude_a(t_fnmatch: PackageDAG) -> None:
    # test exclude for a-* in the result we got only b-* nodes
    graph = dag_to_dict(t_fnmatch.filter_nodes(None, {"a-*"}))
    assert graph == {"b-a": ["b-b"], "b-b": []}


def test_package_dag_filter_include_exclude_both_used(t_fnmatch: PackageDAG) -> None:
    with pytest.raises(AssertionError):
        t_fnmatch.filter_nodes(["a-a", "a-b"], {"a-b"})


def test_package_dag_filter_nonexistent_packages(t_fnmatch: PackageDAG) -> None:
    with pytest.raises(ValueError, match="No packages matched using the following patterns: x, y, z"):
        t_fnmatch.filter_nodes(["x", "y", "z"], None)


def test_package_dag_filter_packages_uses_pep503normalize(
    mock_pkgs: Callable[[MockGraph], Iterator[Mock]],
) -> None:
    graph: MockGraph = {
        ("Pie.Pie", "1"): [],
    }
    pkgs = PackageDAG.from_pkgs(list(mock_pkgs(graph)))
    pkgs = pkgs.filter_nodes(["Pie.Pie"], None)
    assert len(pkgs) == 1
    assert pkgs.get_node_as_parent("pie-pie") is not None

    pkgs = pkgs.filter_nodes(None, {"Pie.Pie"})
    assert len(pkgs) == 0


def test_package_dag_reverse(example_dag: PackageDAG) -> None:
    def sort_map_values(m: dict[str, Any]) -> dict[str, Any]:
        return {k: sorted(v) for k, v in m.items()}

    t1 = example_dag.reverse()
    expected = {"a": [], "b": ["a", "f"], "c": ["a"], "d": ["b", "c"], "e": ["c", "d", "g"], "f": ["g"], "g": []}
    assert isinstance(t1, ReversedPackageDAG)
    assert sort_map_values(expected) == sort_map_values(dag_to_dict(t1))
    assert all(isinstance(k, ReqPackage) for k in t1)
    assert all(isinstance(v, DistPackage) for v in chain.from_iterable(t1.values()))

    # testing reversal of ReversedPackageDAG instance
    expected = {"a": ["b", "c"], "b": ["d"], "c": ["d", "e"], "d": ["e"], "e": [], "f": ["b"], "g": ["e", "f"]}
    t2 = t1.reverse()
    assert isinstance(t2, PackageDAG)
    assert sort_map_values(expected) == sort_map_values(dag_to_dict(t2))
    assert all(isinstance(k, DistPackage) for k in t2)
    assert all(isinstance(v, ReqPackage) for v in chain.from_iterable(t2.values()))


def test_package_dag_from_pkgs(mock_pkgs: Callable[[MockGraph], Iterator[Mock]]) -> None:
    # when pip's _vendor.packaging.requirements.Requirement's requires() gives a lowercased package name but the actual
    # package name in PyPI is mixed case, expect the mixed case version

    graph: dict[tuple[str, str], list[tuple[str, list[tuple[str, str]]]]] = {
        ("examplePy", "1.2.3"): [("hellopy", [(">=", "2.0.0")])],
        ("HelloPy", "2.2.0"): [],
    }
    package_dag = PackageDAG.from_pkgs(list(mock_pkgs(graph)))
    parent_key = "examplepy"
    c = package_dag.get_children(parent_key)
    assert len(c) == 1
    assert c[0].project_name == "HelloPy"


def test_package_dag_from_pkgs_uses_pep503normalize(mock_pkgs: Callable[[MockGraph], Iterator[Mock]]) -> None:
    # ensure that requirement gets matched with a dists even when it's key needs pep503 normalization to match

    graph: dict[tuple[str, str], list[tuple[str, list[tuple[str, str]]]]] = {
        ("parent-package", "1.2.3"): [("flufl.lock", [(">=", "2.0.0")])],
        ("flufl-lock", "2.2.0"): [],
    }
    package_dag = PackageDAG.from_pkgs(list(mock_pkgs(graph)))
    parent_key = "parent-package"
    c = package_dag.get_children(parent_key)
    assert c[0].dist
    assert c[0].key == "flufl-lock"


def test_package_from_pkgs_given_invalid_requirements(
    mock_pkgs: Callable[[MockGraph], Iterator[Mock]], capfd: pytest.CaptureFixture[str]
) -> None:
    graph: dict[tuple[str, str], list[tuple[str, list[tuple[str, str]]]]] = {
        ("a-package", "1.2.3"): [("BAD**requirement", [(">=", "2.0.0")])],
    }
    package_dag = PackageDAG.from_pkgs(list(mock_pkgs(graph)))
    assert len(package_dag) == 1
    out, err = capfd.readouterr()
    assert not out
    assert err == (
        "Warning!!! Invalid requirement strings found for the following distributions:\na-package\n  "
        'Skipping "BAD**requirement>=2.0.0"\n------------------------------------------------------------------------\n'
    )
