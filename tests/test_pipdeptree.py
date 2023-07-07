from __future__ import annotations

import platform
import random
import subprocess
import sys
from itertools import chain
from pathlib import Path
from textwrap import dedent, indent
from typing import TYPE_CHECKING, Any
from unittest import mock

import pytest
import virtualenv

from pipdeptree import (
    DistPackage,
    PackageDAG,
    ReqPackage,
    ReversedPackageDAG,
    conflicting_deps,
    cyclic_deps,
    dump_graphviz,
    get_parser,
    main,
    print_graphviz,
    render_conflicts_text,
    render_cycles_text,
    render_mermaid,
    render_text,
)

if TYPE_CHECKING:
    from pytest_mock import MockerFixture

# Tests for DAG classes


def mock_pkgs(simple_graph):
    for node, children in simple_graph.items():
        nk, nv = node
        m = mock.Mock(key=nk.lower(), project_name=nk, version=nv)
        as_req = mock.Mock(key=nk, project_name=nk, specs=[("==", nv)])
        m.as_requirement = mock.Mock(return_value=as_req)
        reqs = []
        for child in children:
            ck, cv = child
            r = mock.Mock(key=ck, project_name=ck, specs=cv)
            reqs.append(r)
        m.requires = mock.Mock(return_value=reqs)
        yield m


def mock_package_dag(simple_graph):
    pkgs = list(mock_pkgs(simple_graph))
    return PackageDAG.from_pkgs(pkgs)


# util for comparing tree contents with a simple graph
def dag_to_dict(g):
    return {k.key: [v.key for v in vs] for k, vs in g._obj.items()}  # noqa: SLF001


def sort_map_values(m):
    return {k: sorted(v) for k, v in m.items()}


t = mock_package_dag(
    {
        ("a", "3.4.0"): [("b", [(">=", "2.0.0")]), ("c", [(">=", "5.7.1")])],
        ("b", "2.3.1"): [("d", [(">=", "2.30"), ("<", "2.42")])],
        ("c", "5.10.0"): [("d", [(">=", "2.30")]), ("e", [(">=", "0.12.1")])],
        ("d", "2.35"): [("e", [(">=", "0.9.0")])],
        ("e", "0.12.1"): [],
        ("f", "3.1"): [("b", [(">=", "2.1.0")])],
        ("g", "6.8.3rc1"): [("e", [(">=", "0.9.0")]), ("f", [(">=", "3.0.0")])],
    },
)


def test_package_dag_get_node_as_parent():
    assert t.get_node_as_parent("b").key == "b"
    assert t.get_node_as_parent("c").key == "c"


def test_package_dag_filter():
    # When both show_only and exclude are not specified, same tree
    assert t.filter_nodes(None, None) is t

    # when show_only is specified
    g1 = dag_to_dict(t.filter_nodes({"a", "d"}, None))
    expected = {"a": ["b", "c"], "b": ["d"], "c": ["d", "e"], "d": ["e"], "e": []}
    assert expected == g1

    # when exclude is specified
    g2 = dag_to_dict(t.filter_nodes(None, ["d"]))
    expected = {"a": ["b", "c"], "b": [], "c": ["e"], "e": [], "f": ["b"], "g": ["e", "f"]}
    assert expected == g2

    # when both show_only and exclude are specified
    g3 = dag_to_dict(t.filter_nodes({"a", "g"}, {"d", "e"}))
    expected = {"a": ["b", "c"], "b": [], "c": [], "f": ["b"], "g": ["f"]}
    assert expected == g3

    # when conflicting values in show_only and exclude, AssertionError
    # is raised
    with pytest.raises(AssertionError):
        dag_to_dict(t.filter_nodes({"d"}, {"D", "e"}))


@pytest.fixture(scope="session")
def t_fnmatch() -> Any:
    return mock_package_dag(
        {
            ("a.a", "1"): [("a.b", []), ("a.c", [])],
            ("a.b", "1"): [("a.c", [])],
            ("b.a", "1"): [("b.b", [])],
            ("b.b", "1"): [("a.b", [])],
        },
    )


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


def test_package_dag_reverse():
    t1 = t.reverse()
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


def test_package_dag_from_pkgs():
    # when pip's _vendor.packaging.requirements.Requirement's requires() gives a lowercased package name but the actual
    # package name in PyPI is mixed case, expect the mixed case version
    graph = {
        ("examplePy", "1.2.3"): [("hellopy", [(">=", "2.0.0")])],
        ("HelloPy", "2.2.0"): [],
    }
    t = mock_package_dag(graph)
    parent_key = "examplepy"
    c = t.get_children(parent_key)
    assert len(c) == 1
    assert c[0].project_name == "HelloPy"


# Tests for Package classes
#
# Note: For all render methods, we are only testing for frozen=False
# as mocks with frozen=True are a lot more complicated


def test_dist_package_render_as_root():
    foo = mock.Mock(key="foo", project_name="foo", version="20.4.1")
    dp = DistPackage(foo)
    is_frozen = False
    assert dp.render_as_root(is_frozen) == "foo==20.4.1"


def test_dist_package_render_as_branch():
    foo = mock.Mock(key="foo", project_name="foo", version="20.4.1")
    bar = mock.Mock(key="bar", project_name="bar", version="4.1.0")
    bar_req = mock.Mock(key="bar", project_name="bar", version="4.1.0", specs=[(">=", "4.0")])
    rp = ReqPackage(bar_req, dist=bar)
    dp = DistPackage(foo).as_parent_of(rp)
    is_frozen = False
    assert dp.render_as_branch(is_frozen) == "foo==20.4.1 [requires: bar>=4.0]"


def test_dist_package_as_parent_of():
    foo = mock.Mock(key="foo", project_name="foo", version="20.4.1")
    dp = DistPackage(foo)
    assert dp.req is None

    bar = mock.Mock(key="bar", project_name="bar", version="4.1.0")
    bar_req = mock.Mock(key="bar", project_name="bar", version="4.1.0", specs=[(">=", "4.0")])
    rp = ReqPackage(bar_req, dist=bar)
    dp1 = dp.as_parent_of(rp)
    assert dp1._obj == dp._obj  # noqa: SLF001
    assert dp1.req is rp

    dp2 = dp.as_parent_of(None)
    assert dp2 is dp


def test_dist_package_as_dict():
    foo = mock.Mock(key="foo", project_name="foo", version="1.3.2b1")
    dp = DistPackage(foo)
    result = dp.as_dict()
    expected = {"key": "foo", "package_name": "foo", "installed_version": "1.3.2b1"}
    assert expected == result


def test_req_package_render_as_root():
    bar = mock.Mock(key="bar", project_name="bar", version="4.1.0")
    bar_req = mock.Mock(key="bar", project_name="bar", version="4.1.0", specs=[(">=", "4.0")])
    rp = ReqPackage(bar_req, dist=bar)
    is_frozen = False
    assert rp.render_as_root(is_frozen) == "bar==4.1.0"


def test_req_package_render_as_branch():
    bar = mock.Mock(key="bar", project_name="bar", version="4.1.0")
    bar_req = mock.Mock(key="bar", project_name="bar", version="4.1.0", specs=[(">=", "4.0")])
    rp = ReqPackage(bar_req, dist=bar)
    is_frozen = False
    assert rp.render_as_branch(is_frozen) == "bar [required: >=4.0, installed: 4.1.0]"


def test_req_package_as_dict():
    bar = mock.Mock(key="bar", project_name="bar", version="4.1.0")
    bar_req = mock.Mock(key="bar", project_name="bar", version="4.1.0", specs=[(">=", "4.0")])
    rp = ReqPackage(bar_req, dist=bar)
    result = rp.as_dict()
    expected = {"key": "bar", "package_name": "bar", "installed_version": "4.1.0", "required_version": ">=4.0"}
    assert expected == result


# Tests for render_text


class MockStdout:
    """
    A wrapper to stdout that mocks the `encoding` attribute (to have `render_text()` render with unicode/non-unicode)
    and `write()` (so that `print()` calls can write to stdout).
    """

    def __init__(self, encoding) -> None:
        self.stdout = sys.stdout
        self.encoding = encoding

    def encoding(self):
        return self.encoding

    def write(self, text):
        self.stdout.write(text)


@pytest.mark.parametrize(
    ("list_all", "reverse", "unicode", "expected_output"),
    [
        (
            True,
            False,
            True,
            [
                "a==3.4.0",
                "├── b [required: >=2.0.0, installed: 2.3.1]",
                "│   └── d [required: >=2.30,<2.42, installed: 2.35]",
                "│       └── e [required: >=0.9.0, installed: 0.12.1]",
                "└── c [required: >=5.7.1, installed: 5.10.0]",
                "    ├── d [required: >=2.30, installed: 2.35]",
                "    │   └── e [required: >=0.9.0, installed: 0.12.1]",
                "    └── e [required: >=0.12.1, installed: 0.12.1]",
                "b==2.3.1",
                "└── d [required: >=2.30,<2.42, installed: 2.35]",
                "    └── e [required: >=0.9.0, installed: 0.12.1]",
                "c==5.10.0",
                "├── d [required: >=2.30, installed: 2.35]",
                "│   └── e [required: >=0.9.0, installed: 0.12.1]",
                "└── e [required: >=0.12.1, installed: 0.12.1]",
                "d==2.35",
                "└── e [required: >=0.9.0, installed: 0.12.1]",
                "e==0.12.1",
                "f==3.1",
                "└── b [required: >=2.1.0, installed: 2.3.1]",
                "    └── d [required: >=2.30,<2.42, installed: 2.35]",
                "        └── e [required: >=0.9.0, installed: 0.12.1]",
                "g==6.8.3rc1",
                "├── e [required: >=0.9.0, installed: 0.12.1]",
                "└── f [required: >=3.0.0, installed: 3.1]",
                "    └── b [required: >=2.1.0, installed: 2.3.1]",
                "        └── d [required: >=2.30,<2.42, installed: 2.35]",
                "            └── e [required: >=0.9.0, installed: 0.12.1]",
            ],
        ),
        (
            True,
            True,
            True,
            [
                "a==3.4.0",
                "b==2.3.1",
                "├── a==3.4.0 [requires: b>=2.0.0]",
                "└── f==3.1 [requires: b>=2.1.0]",
                "    └── g==6.8.3rc1 [requires: f>=3.0.0]",
                "c==5.10.0",
                "└── a==3.4.0 [requires: c>=5.7.1]",
                "d==2.35",
                "├── b==2.3.1 [requires: d>=2.30,<2.42]",
                "│   ├── a==3.4.0 [requires: b>=2.0.0]",
                "│   └── f==3.1 [requires: b>=2.1.0]",
                "│       └── g==6.8.3rc1 [requires: f>=3.0.0]",
                "└── c==5.10.0 [requires: d>=2.30]",
                "    └── a==3.4.0 [requires: c>=5.7.1]",
                "e==0.12.1",
                "├── c==5.10.0 [requires: e>=0.12.1]",
                "│   └── a==3.4.0 [requires: c>=5.7.1]",
                "├── d==2.35 [requires: e>=0.9.0]",
                "│   ├── b==2.3.1 [requires: d>=2.30,<2.42]",
                "│   │   ├── a==3.4.0 [requires: b>=2.0.0]",
                "│   │   └── f==3.1 [requires: b>=2.1.0]",
                "│   │       └── g==6.8.3rc1 [requires: f>=3.0.0]",
                "│   └── c==5.10.0 [requires: d>=2.30]",
                "│       └── a==3.4.0 [requires: c>=5.7.1]",
                "└── g==6.8.3rc1 [requires: e>=0.9.0]",
                "f==3.1",
                "└── g==6.8.3rc1 [requires: f>=3.0.0]",
                "g==6.8.3rc1",
            ],
        ),
        (
            False,
            False,
            True,
            [
                "a==3.4.0",
                "├── b [required: >=2.0.0, installed: 2.3.1]",
                "│   └── d [required: >=2.30,<2.42, installed: 2.35]",
                "│       └── e [required: >=0.9.0, installed: 0.12.1]",
                "└── c [required: >=5.7.1, installed: 5.10.0]",
                "    ├── d [required: >=2.30, installed: 2.35]",
                "    │   └── e [required: >=0.9.0, installed: 0.12.1]",
                "    └── e [required: >=0.12.1, installed: 0.12.1]",
                "g==6.8.3rc1",
                "├── e [required: >=0.9.0, installed: 0.12.1]",
                "└── f [required: >=3.0.0, installed: 3.1]",
                "    └── b [required: >=2.1.0, installed: 2.3.1]",
                "        └── d [required: >=2.30,<2.42, installed: 2.35]",
                "            └── e [required: >=0.9.0, installed: 0.12.1]",
            ],
        ),
        (
            False,
            True,
            True,
            [
                "e==0.12.1",
                "├── c==5.10.0 [requires: e>=0.12.1]",
                "│   └── a==3.4.0 [requires: c>=5.7.1]",
                "├── d==2.35 [requires: e>=0.9.0]",
                "│   ├── b==2.3.1 [requires: d>=2.30,<2.42]",
                "│   │   ├── a==3.4.0 [requires: b>=2.0.0]",
                "│   │   └── f==3.1 [requires: b>=2.1.0]",
                "│   │       └── g==6.8.3rc1 [requires: f>=3.0.0]",
                "│   └── c==5.10.0 [requires: d>=2.30]",
                "│       └── a==3.4.0 [requires: c>=5.7.1]",
                "└── g==6.8.3rc1 [requires: e>=0.9.0]",
            ],
        ),
        (
            True,
            False,
            False,
            [
                "a==3.4.0",
                "  - b [required: >=2.0.0, installed: 2.3.1]",
                "    - d [required: >=2.30,<2.42, installed: 2.35]",
                "      - e [required: >=0.9.0, installed: 0.12.1]",
                "  - c [required: >=5.7.1, installed: 5.10.0]",
                "    - d [required: >=2.30, installed: 2.35]",
                "      - e [required: >=0.9.0, installed: 0.12.1]",
                "    - e [required: >=0.12.1, installed: 0.12.1]",
                "b==2.3.1",
                "  - d [required: >=2.30,<2.42, installed: 2.35]",
                "    - e [required: >=0.9.0, installed: 0.12.1]",
                "c==5.10.0",
                "  - d [required: >=2.30, installed: 2.35]",
                "    - e [required: >=0.9.0, installed: 0.12.1]",
                "  - e [required: >=0.12.1, installed: 0.12.1]",
                "d==2.35",
                "  - e [required: >=0.9.0, installed: 0.12.1]",
                "e==0.12.1",
                "f==3.1",
                "  - b [required: >=2.1.0, installed: 2.3.1]",
                "    - d [required: >=2.30,<2.42, installed: 2.35]",
                "      - e [required: >=0.9.0, installed: 0.12.1]",
                "g==6.8.3rc1",
                "  - e [required: >=0.9.0, installed: 0.12.1]",
                "  - f [required: >=3.0.0, installed: 3.1]",
                "    - b [required: >=2.1.0, installed: 2.3.1]",
                "      - d [required: >=2.30,<2.42, installed: 2.35]",
                "        - e [required: >=0.9.0, installed: 0.12.1]",
            ],
        ),
        (
            True,
            True,
            False,
            [
                "a==3.4.0",
                "b==2.3.1",
                "  - a==3.4.0 [requires: b>=2.0.0]",
                "  - f==3.1 [requires: b>=2.1.0]",
                "    - g==6.8.3rc1 [requires: f>=3.0.0]",
                "c==5.10.0",
                "  - a==3.4.0 [requires: c>=5.7.1]",
                "d==2.35",
                "  - b==2.3.1 [requires: d>=2.30,<2.42]",
                "    - a==3.4.0 [requires: b>=2.0.0]",
                "    - f==3.1 [requires: b>=2.1.0]",
                "      - g==6.8.3rc1 [requires: f>=3.0.0]",
                "  - c==5.10.0 [requires: d>=2.30]",
                "    - a==3.4.0 [requires: c>=5.7.1]",
                "e==0.12.1",
                "  - c==5.10.0 [requires: e>=0.12.1]",
                "    - a==3.4.0 [requires: c>=5.7.1]",
                "  - d==2.35 [requires: e>=0.9.0]",
                "    - b==2.3.1 [requires: d>=2.30,<2.42]",
                "      - a==3.4.0 [requires: b>=2.0.0]",
                "      - f==3.1 [requires: b>=2.1.0]",
                "        - g==6.8.3rc1 [requires: f>=3.0.0]",
                "    - c==5.10.0 [requires: d>=2.30]",
                "      - a==3.4.0 [requires: c>=5.7.1]",
                "  - g==6.8.3rc1 [requires: e>=0.9.0]",
                "f==3.1",
                "  - g==6.8.3rc1 [requires: f>=3.0.0]",
                "g==6.8.3rc1",
            ],
        ),
        (
            False,
            False,
            False,
            [
                "a==3.4.0",
                "  - b [required: >=2.0.0, installed: 2.3.1]",
                "    - d [required: >=2.30,<2.42, installed: 2.35]",
                "      - e [required: >=0.9.0, installed: 0.12.1]",
                "  - c [required: >=5.7.1, installed: 5.10.0]",
                "    - d [required: >=2.30, installed: 2.35]",
                "      - e [required: >=0.9.0, installed: 0.12.1]",
                "    - e [required: >=0.12.1, installed: 0.12.1]",
                "g==6.8.3rc1",
                "  - e [required: >=0.9.0, installed: 0.12.1]",
                "  - f [required: >=3.0.0, installed: 3.1]",
                "    - b [required: >=2.1.0, installed: 2.3.1]",
                "      - d [required: >=2.30,<2.42, installed: 2.35]",
                "        - e [required: >=0.9.0, installed: 0.12.1]",
            ],
        ),
        (
            False,
            True,
            False,
            [
                "e==0.12.1",
                "  - c==5.10.0 [requires: e>=0.12.1]",
                "    - a==3.4.0 [requires: c>=5.7.1]",
                "  - d==2.35 [requires: e>=0.9.0]",
                "    - b==2.3.1 [requires: d>=2.30,<2.42]",
                "      - a==3.4.0 [requires: b>=2.0.0]",
                "      - f==3.1 [requires: b>=2.1.0]",
                "        - g==6.8.3rc1 [requires: f>=3.0.0]",
                "    - c==5.10.0 [requires: d>=2.30]",
                "      - a==3.4.0 [requires: c>=5.7.1]",
                "  - g==6.8.3rc1 [requires: e>=0.9.0]",
            ],
        ),
    ],
)
def test_render_text(capsys, list_all, reverse, unicode, expected_output):
    tree = t.reverse() if reverse else t
    encoding = "utf-8" if unicode else "ascii"
    render_text(tree, float("inf"), encoding, list_all=list_all, frozen=False)
    captured = capsys.readouterr()
    assert "\n".join(expected_output).strip() == captured.out.strip()


@pytest.mark.parametrize(
    ("unicode", "level", "expected_output"),
    [
        (
            True,
            0,
            [
                "a==3.4.0",
                "b==2.3.1",
                "c==5.10.0",
                "d==2.35",
                "e==0.12.1",
                "f==3.1",
                "g==6.8.3rc1",
            ],
        ),
        (
            False,
            0,
            [
                "a==3.4.0",
                "b==2.3.1",
                "c==5.10.0",
                "d==2.35",
                "e==0.12.1",
                "f==3.1",
                "g==6.8.3rc1",
            ],
        ),
        (
            True,
            2,
            [
                "a==3.4.0",
                "├── b [required: >=2.0.0, installed: 2.3.1]",
                "│   └── d [required: >=2.30,<2.42, installed: 2.35]",
                "└── c [required: >=5.7.1, installed: 5.10.0]",
                "    ├── d [required: >=2.30, installed: 2.35]",
                "    └── e [required: >=0.12.1, installed: 0.12.1]",
                "b==2.3.1",
                "└── d [required: >=2.30,<2.42, installed: 2.35]",
                "    └── e [required: >=0.9.0, installed: 0.12.1]",
                "c==5.10.0",
                "├── d [required: >=2.30, installed: 2.35]",
                "│   └── e [required: >=0.9.0, installed: 0.12.1]",
                "└── e [required: >=0.12.1, installed: 0.12.1]",
                "d==2.35",
                "└── e [required: >=0.9.0, installed: 0.12.1]",
                "e==0.12.1",
                "f==3.1",
                "└── b [required: >=2.1.0, installed: 2.3.1]",
                "    └── d [required: >=2.30,<2.42, installed: 2.35]",
                "g==6.8.3rc1",
                "├── e [required: >=0.9.0, installed: 0.12.1]",
                "└── f [required: >=3.0.0, installed: 3.1]",
                "    └── b [required: >=2.1.0, installed: 2.3.1]",
            ],
        ),
        (
            False,
            2,
            [
                "a==3.4.0",
                "  - b [required: >=2.0.0, installed: 2.3.1]",
                "    - d [required: >=2.30,<2.42, installed: 2.35]",
                "  - c [required: >=5.7.1, installed: 5.10.0]",
                "    - d [required: >=2.30, installed: 2.35]",
                "    - e [required: >=0.12.1, installed: 0.12.1]",
                "b==2.3.1",
                "  - d [required: >=2.30,<2.42, installed: 2.35]",
                "    - e [required: >=0.9.0, installed: 0.12.1]",
                "c==5.10.0",
                "  - d [required: >=2.30, installed: 2.35]",
                "    - e [required: >=0.9.0, installed: 0.12.1]",
                "  - e [required: >=0.12.1, installed: 0.12.1]",
                "d==2.35",
                "  - e [required: >=0.9.0, installed: 0.12.1]",
                "e==0.12.1",
                "f==3.1",
                "  - b [required: >=2.1.0, installed: 2.3.1]",
                "    - d [required: >=2.30,<2.42, installed: 2.35]",
                "g==6.8.3rc1",
                "  - e [required: >=0.9.0, installed: 0.12.1]",
                "  - f [required: >=3.0.0, installed: 3.1]",
                "    - b [required: >=2.1.0, installed: 2.3.1]",
            ],
        ),
    ],
)
def test_render_text_given_depth(capsys, unicode, level, expected_output):
    render_text(t, level, encoding="utf-8" if unicode else "ascii")
    captured = capsys.readouterr()
    assert "\n".join(expected_output).strip() == captured.out.strip()


@pytest.mark.parametrize(
    ("level", "encoding", "expected_output"),
    [
        (
            0,
            "utf-8",
            [
                "a==3.4.0",
                "b==2.3.1",
                "c==5.10.0",
                "d==2.35",
                "e==0.12.1",
                "f==3.1",
                "g==6.8.3rc1",
            ],
        ),
        (
            0,
            "utf-8",
            [
                "a==3.4.0",
                "b==2.3.1",
                "c==5.10.0",
                "d==2.35",
                "e==0.12.1",
                "f==3.1",
                "g==6.8.3rc1",
            ],
        ),
        (
            2,
            "utf-8",
            [
                "a==3.4.0",
                "├── b [required: >=2.0.0, installed: 2.3.1]",
                "│   └── d [required: >=2.30,<2.42, installed: 2.35]",
                "└── c [required: >=5.7.1, installed: 5.10.0]",
                "    ├── d [required: >=2.30, installed: 2.35]",
                "    └── e [required: >=0.12.1, installed: 0.12.1]",
                "b==2.3.1",
                "└── d [required: >=2.30,<2.42, installed: 2.35]",
                "    └── e [required: >=0.9.0, installed: 0.12.1]",
                "c==5.10.0",
                "├── d [required: >=2.30, installed: 2.35]",
                "│   └── e [required: >=0.9.0, installed: 0.12.1]",
                "└── e [required: >=0.12.1, installed: 0.12.1]",
                "d==2.35",
                "└── e [required: >=0.9.0, installed: 0.12.1]",
                "e==0.12.1",
                "f==3.1",
                "└── b [required: >=2.1.0, installed: 2.3.1]",
                "    └── d [required: >=2.30,<2.42, installed: 2.35]",
                "g==6.8.3rc1",
                "├── e [required: >=0.9.0, installed: 0.12.1]",
                "└── f [required: >=3.0.0, installed: 3.1]",
                "    └── b [required: >=2.1.0, installed: 2.3.1]",
            ],
        ),
        (
            2,
            "ascii",
            [
                "a==3.4.0",
                "  - b [required: >=2.0.0, installed: 2.3.1]",
                "    - d [required: >=2.30,<2.42, installed: 2.35]",
                "  - c [required: >=5.7.1, installed: 5.10.0]",
                "    - d [required: >=2.30, installed: 2.35]",
                "    - e [required: >=0.12.1, installed: 0.12.1]",
                "b==2.3.1",
                "  - d [required: >=2.30,<2.42, installed: 2.35]",
                "    - e [required: >=0.9.0, installed: 0.12.1]",
                "c==5.10.0",
                "  - d [required: >=2.30, installed: 2.35]",
                "    - e [required: >=0.9.0, installed: 0.12.1]",
                "  - e [required: >=0.12.1, installed: 0.12.1]",
                "d==2.35",
                "  - e [required: >=0.9.0, installed: 0.12.1]",
                "e==0.12.1",
                "f==3.1",
                "  - b [required: >=2.1.0, installed: 2.3.1]",
                "    - d [required: >=2.30,<2.42, installed: 2.35]",
                "g==6.8.3rc1",
                "  - e [required: >=0.9.0, installed: 0.12.1]",
                "  - f [required: >=3.0.0, installed: 3.1]",
                "    - b [required: >=2.1.0, installed: 2.3.1]",
            ],
        ),
        (
            2,
            "utf-8",
            [
                "a==3.4.0",
                "├── b [required: >=2.0.0, installed: 2.3.1]",
                "│   └── d [required: >=2.30,<2.42, installed: 2.35]",
                "└── c [required: >=5.7.1, installed: 5.10.0]",
                "    ├── d [required: >=2.30, installed: 2.35]",
                "    └── e [required: >=0.12.1, installed: 0.12.1]",
                "b==2.3.1",
                "└── d [required: >=2.30,<2.42, installed: 2.35]",
                "    └── e [required: >=0.9.0, installed: 0.12.1]",
                "c==5.10.0",
                "├── d [required: >=2.30, installed: 2.35]",
                "│   └── e [required: >=0.9.0, installed: 0.12.1]",
                "└── e [required: >=0.12.1, installed: 0.12.1]",
                "d==2.35",
                "└── e [required: >=0.9.0, installed: 0.12.1]",
                "e==0.12.1",
                "f==3.1",
                "└── b [required: >=2.1.0, installed: 2.3.1]",
                "    └── d [required: >=2.30,<2.42, installed: 2.35]",
                "g==6.8.3rc1",
                "├── e [required: >=0.9.0, installed: 0.12.1]",
                "└── f [required: >=3.0.0, installed: 3.1]",
                "    └── b [required: >=2.1.0, installed: 2.3.1]",
            ],
        ),
        (
            2,
            "ascii",
            [
                "a==3.4.0",
                "  - b [required: >=2.0.0, installed: 2.3.1]",
                "    - d [required: >=2.30,<2.42, installed: 2.35]",
                "  - c [required: >=5.7.1, installed: 5.10.0]",
                "    - d [required: >=2.30, installed: 2.35]",
                "    - e [required: >=0.12.1, installed: 0.12.1]",
                "b==2.3.1",
                "  - d [required: >=2.30,<2.42, installed: 2.35]",
                "    - e [required: >=0.9.0, installed: 0.12.1]",
                "c==5.10.0",
                "  - d [required: >=2.30, installed: 2.35]",
                "    - e [required: >=0.9.0, installed: 0.12.1]",
                "  - e [required: >=0.12.1, installed: 0.12.1]",
                "d==2.35",
                "  - e [required: >=0.9.0, installed: 0.12.1]",
                "e==0.12.1",
                "f==3.1",
                "  - b [required: >=2.1.0, installed: 2.3.1]",
                "    - d [required: >=2.30,<2.42, installed: 2.35]",
                "g==6.8.3rc1",
                "  - e [required: >=0.9.0, installed: 0.12.1]",
                "  - f [required: >=3.0.0, installed: 3.1]",
                "    - b [required: >=2.1.0, installed: 2.3.1]",
            ],
        ),
    ],
)
def test_render_text_encoding(capsys, level, encoding, expected_output):
    render_text(t, level, encoding, True, False)
    captured = capsys.readouterr()
    assert "\n".join(expected_output).strip() == captured.out.strip()


# Tests for graph outputs


def randomized_dag_copy(t):
    """Returns a copy of the package tree fixture with dependencies in randomized order."""
    # Extract the dependency graph from the package tree and randomize it.
    randomized_graph = {}
    randomized_nodes = list(t._obj.keys())  # noqa: SLF001
    random.shuffle(randomized_nodes)
    for node in randomized_nodes:
        edges = t._obj[node]  # noqa: SLF001
        random.shuffle(edges)
        randomized_graph[node] = edges
    assert set(randomized_graph) == set(t._obj)  # noqa: SLF001

    # Create a randomized package tree.
    randomized_dag = PackageDAG(randomized_graph)
    assert len(t) == len(randomized_dag)
    return randomized_dag


def test_render_mermaid():
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

    for package_tree in (t, randomized_dag_copy(t)):
        output = render_mermaid(package_tree)
        assert output.rstrip() == nodes + dependency_edges
        reversed_output = render_mermaid(package_tree.reverse())
        assert reversed_output.rstrip() == nodes + reverse_dependency_edges


def test_mermaid_reserved_ids():
    package_tree = mock_package_dag(
        {
            ("click", "3.4.0"): [("click-extra", [(">=", "2.0.0")])],
        },
    )
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


def test_render_dot(capsys):
    # Check both the sorted and randomized package tree produces the same sorted
    # graphviz output.
    for package_tree in (t, randomized_dag_copy(t)):
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


def test_render_pdf(tmp_path: Path, mocker: MockerFixture) -> None:
    output = dump_graphviz(t, output_format="pdf")
    res = tmp_path / "file"
    with pytest.raises(OSError, match="Bad file"):  # noqa: PT012, SIM117 # because we reopen the file
        with res.open("wb") as buf:
            mocker.patch.object(sys, "stdout", buf)
            print_graphviz(output)
    assert res.read_bytes()[:4] == b"%PDF"


def test_render_svg(capsys):
    output = dump_graphviz(t, output_format="svg")
    print_graphviz(output)
    out, _ = capsys.readouterr()
    assert out.startswith("<?xml")
    assert "<svg" in out
    assert out.strip().endswith("</svg>")


# Test for conflicting deps


@pytest.mark.parametrize(
    ("mpkgs", "expected_keys", "expected_output"),
    [
        (
            {("a", "1.0.1"): [("b", [(">=", "2.3.0")])], ("b", "1.9.1"): []},
            {"a": ["b"]},
            [
                "Warning!!! Possibly conflicting dependencies found:",
                "* a==1.0.1",
                " - b [required: >=2.3.0, installed: 1.9.1]",
            ],
        ),
        (
            {("a", "1.0.1"): [("c", [(">=", "9.4.1")])], ("b", "2.3.0"): [("c", [(">=", "7.0")])], ("c", "8.0.1"): []},
            {"a": ["c"]},
            [
                "Warning!!! Possibly conflicting dependencies found:",
                "* a==1.0.1",
                " - c [required: >=9.4.1, installed: 8.0.1]",
            ],
        ),
        (
            {("a", "1.0.1"): [("c", [(">=", "9.4.1")])], ("b", "2.3.0"): [("c", [(">=", "9.4.0")])]},
            {"a": ["c"], "b": ["c"]},
            [
                "Warning!!! Possibly conflicting dependencies found:",
                "* a==1.0.1",
                " - c [required: >=9.4.1, installed: ?]",
                "* b==2.3.0",
                " - c [required: >=9.4.0, installed: ?]",
            ],
        ),
        (
            {("a", "1.0.1"): [("c", [(">=", "9.4.1")])], ("b", "2.3.0"): [("c", [(">=", "7.0")])], ("c", "9.4.1"): []},
            {},
            [],
        ),
    ],
)
def test_conflicting_deps(capsys, mpkgs, expected_keys, expected_output):
    tree = mock_package_dag(mpkgs)
    result = conflicting_deps(tree)
    result_keys = {k.key: [v.key for v in vs] for k, vs in result.items()}
    assert expected_keys == result_keys
    render_conflicts_text(result)
    captured = capsys.readouterr()
    assert "\n".join(expected_output).strip() == captured.err.strip()


# Tests for cyclic deps


@pytest.mark.parametrize(
    ("mpkgs", "expected_keys", "expected_output"),
    [
        (
            {
                ("a", "1.0.1"): [("b", [(">=", "2.0.0")])],
                ("b", "2.3.0"): [("a", [(">=", "1.0.1")])],
                ("c", "4.5.0"): [("d", [("==", "2.0")])],
                ("d", "2.0"): [],
            },
            [("a", "b", "a"), ("b", "a", "b")],
            ["Warning!! Cyclic dependencies found:", "* b => a => b", "* a => b => a"],
        ),
        (  # if a dependency isn't installed, cannot verify cycles
            {
                ("a", "1.0.1"): [("b", [(">=", "2.0.0")])],
            },
            [],
            [],  # no output expected
        ),
    ],
)
def test_cyclic_deps(capsys, mpkgs, expected_keys, expected_output):
    tree = mock_package_dag(mpkgs)
    result = cyclic_deps(tree)
    result_keys = [(a.key, b.key, c.key) for (a, b, c) in result]
    assert sorted(expected_keys) == sorted(result_keys)
    render_cycles_text(result)
    captured = capsys.readouterr()
    assert "\n".join(expected_output).strip() == captured.err.strip()


# Tests for the argparse parser


def test_parser_default():
    parser = get_parser()
    args = parser.parse_args([])
    assert not args.json
    assert args.output_format is None


def test_parser_j():
    parser = get_parser()
    args = parser.parse_args(["-j"])
    assert args.json
    assert args.output_format is None


def test_parser_json():
    parser = get_parser()
    args = parser.parse_args(["--json"])
    assert args.json
    assert args.output_format is None


def test_parser_json_tree():
    parser = get_parser()
    args = parser.parse_args(["--json-tree"])
    assert args.json_tree
    assert not args.json
    assert args.output_format is None


def test_parser_mermaid():
    parser = get_parser()
    args = parser.parse_args(["--mermaid"])
    assert args.mermaid
    assert not args.json
    assert args.output_format is None


def test_parser_pdf():
    parser = get_parser()
    args = parser.parse_args(["--graph-output", "pdf"])
    assert args.output_format == "pdf"
    assert not args.json


def test_parser_svg():
    parser = get_parser()
    args = parser.parse_args(["--graph-output", "svg"])
    assert args.output_format == "svg"
    assert not args.json


@pytest.mark.parametrize(
    ("should_be_error", "depth_arg", "expected_value"),
    [
        (True, ["-d", "-1"], None),
        (True, ["--depth", "string"], None),
        (False, ["-d", "0"], 0),
        (False, ["--depth", "8"], 8),
        (False, [], float("inf")),
    ],
)
def test_parser_depth(should_be_error, depth_arg, expected_value):
    parser = get_parser()

    if should_be_error:
        with pytest.raises(SystemExit):
            parser.parse_args(depth_arg)
    else:
        args = parser.parse_args(depth_arg)
        assert args.depth == expected_value


@pytest.mark.parametrize("args_joined", [True, False])
def test_custom_interpreter(tmp_path, monkeypatch, capfd, args_joined):
    result = virtualenv.cli_run([str(tmp_path / "venv"), "--activators", ""])
    cmd = [sys.executable]
    monkeypatch.chdir(tmp_path)
    py = str(result.creator.exe.relative_to(tmp_path))
    cmd += [f"--python={result.creator.exe}"] if args_joined else ["--python", py]
    monkeypatch.setattr(sys, "argv", cmd)
    main()
    out, _ = capfd.readouterr()
    found = {i.split("==")[0] for i in out.splitlines()}
    implementation = platform.python_implementation()
    if implementation == "CPython":
        expected = {"pip", "setuptools", "wheel"}
    elif implementation == "PyPy":
        expected = {"cffi", "greenlet", "pip", "readline", "setuptools", "wheel"}
    else:
        raise ValueError(implementation)
    if sys.version_info >= (3, 12):
        expected -= {"setuptools", "wheel"}
    assert found == expected, out

    monkeypatch.setattr(sys, "argv", [*cmd, "--graph-output", "something"])
    with pytest.raises(SystemExit) as context:
        main()
    out, err = capfd.readouterr()
    assert context.value.code == 1
    assert not out
    assert err == "graphviz functionality is not supported when querying non-host python\n"


def test_guess_version_setuptools():
    script = Path(__file__).parent / "guess_version_setuptools.py"
    output = subprocess.check_output([sys.executable, script], text=True)
    assert output == "?"
