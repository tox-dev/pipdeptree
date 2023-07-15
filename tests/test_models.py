from __future__ import annotations

from importlib.metadata import PackageNotFoundError
from itertools import chain
from typing import TYPE_CHECKING, Any, Callable, Iterator
from unittest.mock import Mock

import pytest

from pipdeptree._models import DistPackage, PackageDAG, ReqPackage, ReversedPackageDAG, guess_version

if TYPE_CHECKING:
    from pytest_mock import MockerFixture

    from tests.our_types import MockGraph


def sort_map_values(m: dict[str, Any]) -> dict[str, Any]:
    return {k: sorted(v) for k, v in m.items()}


def dag_to_dict(g: PackageDAG) -> dict[str, list[str]]:
    return {k.key: [v.key for v in vs] for k, vs in g._obj.items()}  # noqa: SLF001


def test_guess_version_setuptools(mocker: MockerFixture) -> None:
    mocker.patch("pipdeptree._models.version", side_effect=PackageNotFoundError)
    result = guess_version("setuptools")
    assert result == "?"


def test_package_dag_get_node_as_parent(example_dag: PackageDAG) -> None:
    node = example_dag.get_node_as_parent("b")
    assert node is not None
    assert node.key == "b"
    node = example_dag.get_node_as_parent("c")
    assert node is not None
    assert node.key == "c"


def test_package_dag_filter(example_dag: PackageDAG) -> None:
    # When both show_only and exclude are not specified, same tree
    assert example_dag.filter_nodes(None, None) is example_dag

    # when show_only is specified
    g1 = dag_to_dict(example_dag.filter_nodes({"a", "d"}, None))
    expected = {"a": ["b", "c"], "b": ["d"], "c": ["d", "e"], "d": ["e"], "e": []}
    assert expected == g1

    # when exclude is specified
    g2 = dag_to_dict(example_dag.filter_nodes(None, {"d"}))
    expected = {"a": ["b", "c"], "b": [], "c": ["e"], "e": [], "f": ["b"], "g": ["e", "f"]}
    assert expected == g2

    # when both show_only and exclude are specified
    g3 = dag_to_dict(example_dag.filter_nodes({"a", "g"}, {"d", "e"}))
    expected = {"a": ["b", "c"], "b": [], "c": [], "f": ["b"], "g": ["f"]}
    assert expected == g3

    # when conflicting values in show_only and exclude, AssertionError
    # is raised
    with pytest.raises(AssertionError):
        dag_to_dict(example_dag.filter_nodes({"d"}, {"D", "e"}))


@pytest.fixture(scope="session")
def t_fnmatch(mock_pkgs: Callable[[MockGraph], Iterator[Mock]]) -> Any:
    graph = {
        ("a.a", "1"): [("a.b", []), ("a.c", [])],
        ("a.b", "1"): [("a.c", [])],
        ("b.a", "1"): [("b.b", [])],
        ("b.b", "1"): [("a.b", [])],
    }
    return PackageDAG.from_pkgs(list(mock_pkgs(graph)))


def test_package_dag_filter_fnmatch_include_a(t_fnmatch: Any) -> None:
    # test include for a.*in the result we got only a.* nodes
    graph = dag_to_dict(t_fnmatch.filter_nodes({"a.*"}, None))
    assert graph == {"a.a": ["a.b", "a.c"], "a.b": ["a.c"]}


def test_package_dag_filter_fnmatch_include_b(t_fnmatch: Any) -> None:
    # test include for b.*, which has a.b and a.c in tree, but not a.a
    # in the result we got the b.* nodes plus the a.b node as child in the tree
    graph = dag_to_dict(t_fnmatch.filter_nodes({"b.*"}, None))
    assert graph == {"b.a": ["b.b"], "b.b": ["a.b"], "a.b": ["a.c"]}


def test_package_dag_filter_fnmatch_exclude_c(t_fnmatch: Any) -> None:
    # test exclude for b.* in the result we got only a.* nodes
    graph = dag_to_dict(t_fnmatch.filter_nodes(None, {"b.*"}))
    assert graph == {"a.a": ["a.b", "a.c"], "a.b": ["a.c"]}


def test_package_dag_filter_fnmatch_exclude_a(t_fnmatch: Any) -> None:
    # test exclude for a.* in the result we got only b.* nodes
    graph = dag_to_dict(t_fnmatch.filter_nodes(None, {"a.*"}))
    assert graph == {"b.a": ["b.b"], "b.b": []}


def test_package_dag_reverse(example_dag: PackageDAG) -> None:
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


def test_dist_package_render_as_root() -> None:
    foo = Mock(key="foo", project_name="foo", version="20.4.1")
    dp = DistPackage(foo)
    is_frozen = False
    assert dp.render_as_root(is_frozen) == "foo==20.4.1"


def test_dist_package_render_as_branch() -> None:
    foo = Mock(key="foo", project_name="foo", version="20.4.1")
    bar = Mock(key="bar", project_name="bar", version="4.1.0")
    bar_req = Mock(key="bar", project_name="bar", version="4.1.0", specs=[(">=", "4.0")])
    rp = ReqPackage(bar_req, dist=bar)
    dp = DistPackage(foo).as_parent_of(rp)
    is_frozen = False
    assert dp.render_as_branch(is_frozen) == "foo==20.4.1 [requires: bar>=4.0]"


def test_dist_package_as_parent_of() -> None:
    foo = Mock(key="foo", project_name="foo", version="20.4.1")
    dp = DistPackage(foo)
    assert dp.req is None

    bar = Mock(key="bar", project_name="bar", version="4.1.0")
    bar_req = Mock(key="bar", project_name="bar", version="4.1.0", specs=[(">=", "4.0")])
    rp = ReqPackage(bar_req, dist=bar)
    dp1 = dp.as_parent_of(rp)
    assert dp1._obj == dp._obj  # noqa: SLF001
    assert dp1.req is rp

    dp2 = dp.as_parent_of(None)
    assert dp2 is dp


def test_dist_package_as_dict() -> None:
    foo = Mock(key="foo", project_name="foo", version="1.3.2b1")
    dp = DistPackage(foo)
    result = dp.as_dict()
    expected = {"key": "foo", "package_name": "foo", "installed_version": "1.3.2b1"}
    assert expected == result


def test_req_package_render_as_root() -> None:
    bar = Mock(key="bar", project_name="bar", version="4.1.0")
    bar_req = Mock(key="bar", project_name="bar", version="4.1.0", specs=[(">=", "4.0")])
    rp = ReqPackage(bar_req, dist=bar)
    is_frozen = False
    assert rp.render_as_root(is_frozen) == "bar==4.1.0"


def test_req_package_render_as_branch() -> None:
    bar = Mock(key="bar", project_name="bar", version="4.1.0")
    bar_req = Mock(key="bar", project_name="bar", version="4.1.0", specs=[(">=", "4.0")])
    rp = ReqPackage(bar_req, dist=bar)
    is_frozen = False
    assert rp.render_as_branch(is_frozen) == "bar [required: >=4.0, installed: 4.1.0]"


def test_req_package_as_dict() -> None:
    bar = Mock(key="bar", project_name="bar", version="4.1.0")
    bar_req = Mock(key="bar", project_name="bar", version="4.1.0", specs=[(">=", "4.0")])
    rp = ReqPackage(bar_req, dist=bar)
    result = rp.as_dict()
    expected = {"key": "bar", "package_name": "bar", "installed_version": "4.1.0", "required_version": ">=4.0"}
    assert expected == result
