import platform
import random
import subprocess
import sys
from contextlib import contextmanager
from itertools import chain
from pathlib import Path
from tempfile import NamedTemporaryFile
from textwrap import dedent

try:
    from unittest import mock
except ImportError:
    from unittest import mock

import pytest
import virtualenv

import pipdeptree as p

# Tests for DAG classes


def mock_pkgs(simple_graph):
    for node, children in simple_graph.items():
        nk, nv = node
        m = mock.Mock(key=nk, project_name=nk, version=nv)
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
    return p.PackageDAG.from_pkgs(pkgs)


# util for comparing tree contents with a simple graph
def dag_to_dict(g):
    return {k.key: [v.key for v in vs] for k, vs in g._obj.items()}


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
    }
)


def test_package_dag_get_node_as_parent():
    assert "b" == t.get_node_as_parent("b").key
    assert "c" == t.get_node_as_parent("c").key


def test_package_dag_filter():
    # When both show_only and exclude are not specified, same tree
    # object is returned
    assert t.filter(None, None) is t

    # when show_only is specified
    g1 = dag_to_dict(t.filter({"a", "d"}, None))
    expected = {"a": ["b", "c"], "b": ["d"], "c": ["d", "e"], "d": ["e"], "e": []}
    assert expected == g1

    # when exclude is specified
    g2 = dag_to_dict(t.filter(None, ["d"]))
    expected = {"a": ["b", "c"], "b": [], "c": ["e"], "e": [], "f": ["b"], "g": ["e", "f"]}
    assert expected == g2

    # when both show_only and exclude are specified
    g3 = dag_to_dict(t.filter({"a", "g"}, {"d", "e"}))
    expected = {"a": ["b", "c"], "b": [], "c": [], "f": ["b"], "g": ["f"]}
    assert expected == g3

    # when conflicting values in show_only and exclude, AssertionError
    # is raised
    with pytest.raises(AssertionError):
        dag_to_dict(t.filter({"d"}, {"D", "e"}))


def test_package_dag_reverse():
    t1 = t.reverse()
    expected = {"a": [], "b": ["a", "f"], "c": ["a"], "d": ["b", "c"], "e": ["c", "d", "g"], "f": ["g"], "g": []}
    assert isinstance(t1, p.ReversedPackageDAG)
    assert sort_map_values(expected) == sort_map_values(dag_to_dict(t1))
    assert all([isinstance(k, p.ReqPackage) for k in t1.keys()])
    assert all([isinstance(v, p.DistPackage) for v in chain.from_iterable(t1.values())])

    # testing reversal of ReversedPackageDAG instance
    expected = {"a": ["b", "c"], "b": ["d"], "c": ["d", "e"], "d": ["e"], "e": [], "f": ["b"], "g": ["e", "f"]}
    t2 = t1.reverse()
    assert isinstance(t2, p.PackageDAG)
    assert sort_map_values(expected) == sort_map_values(dag_to_dict(t2))
    assert all([isinstance(k, p.DistPackage) for k in t2.keys()])
    assert all([isinstance(v, p.ReqPackage) for v in chain.from_iterable(t2.values())])


# Tests for Package classes
#
# Note: For all render methods, we are only testing for frozen=False
# as mocks with frozen=True are a lot more complicated


def test_dist_package_render_as_root():
    foo = mock.Mock(key="foo", project_name="foo", version="20.4.1")
    dp = p.DistPackage(foo)
    is_frozen = False
    assert "foo==20.4.1" == dp.render_as_root(is_frozen)


def test_dist_package_render_as_branch():
    foo = mock.Mock(key="foo", project_name="foo", version="20.4.1")
    bar = mock.Mock(key="bar", project_name="bar", version="4.1.0")
    bar_req = mock.Mock(key="bar", project_name="bar", version="4.1.0", specs=[(">=", "4.0")])
    rp = p.ReqPackage(bar_req, dist=bar)
    dp = p.DistPackage(foo).as_parent_of(rp)
    is_frozen = False
    assert "foo==20.4.1 [requires: bar>=4.0]" == dp.render_as_branch(is_frozen)


def test_dist_package_as_parent_of():
    foo = mock.Mock(key="foo", project_name="foo", version="20.4.1")
    dp = p.DistPackage(foo)
    assert dp.req is None

    bar = mock.Mock(key="bar", project_name="bar", version="4.1.0")
    bar_req = mock.Mock(key="bar", project_name="bar", version="4.1.0", specs=[(">=", "4.0")])
    rp = p.ReqPackage(bar_req, dist=bar)
    dp1 = dp.as_parent_of(rp)
    assert dp1._obj == dp._obj
    assert dp1.req is rp

    dp2 = dp.as_parent_of(None)
    assert dp2 is dp


def test_dist_package_as_dict():
    foo = mock.Mock(key="foo", project_name="foo", version="1.3.2b1")
    dp = p.DistPackage(foo)
    result = dp.as_dict()
    expected = {"key": "foo", "package_name": "foo", "installed_version": "1.3.2b1"}
    assert expected == result


def test_req_package_render_as_root():
    bar = mock.Mock(key="bar", project_name="bar", version="4.1.0")
    bar_req = mock.Mock(key="bar", project_name="bar", version="4.1.0", specs=[(">=", "4.0")])
    rp = p.ReqPackage(bar_req, dist=bar)
    is_frozen = False
    assert "bar==4.1.0" == rp.render_as_root(is_frozen)


def test_req_package_render_as_branch():
    bar = mock.Mock(key="bar", project_name="bar", version="4.1.0")
    bar_req = mock.Mock(key="bar", project_name="bar", version="4.1.0", specs=[(">=", "4.0")])
    rp = p.ReqPackage(bar_req, dist=bar)
    is_frozen = False
    assert "bar [required: >=4.0, installed: 4.1.0]" == rp.render_as_branch(is_frozen)


def test_req_package_as_dict():
    bar = mock.Mock(key="bar", project_name="bar", version="4.1.0")
    bar_req = mock.Mock(key="bar", project_name="bar", version="4.1.0", specs=[(">=", "4.0")])
    rp = p.ReqPackage(bar_req, dist=bar)
    result = rp.as_dict()
    expected = {"key": "bar", "package_name": "bar", "installed_version": "4.1.0", "required_version": ">=4.0"}
    assert expected == result


# Tests for render_text


@pytest.mark.parametrize(
    ("list_all", "reverse", "expected_output"),
    [
        (
            True,
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
def test_render_text(capsys, list_all, reverse, expected_output):
    tree = t.reverse() if reverse else t
    p.render_text(tree, list_all=list_all, frozen=False)
    captured = capsys.readouterr()
    assert "\n".join(expected_output).strip() == captured.out.strip()


# Tests for graph outputs


def randomized_dag_copy(t):
    """Returns a copy of the package tree fixture with dependencies in randomized order."""
    # Extract the dependency graph from the package tree and randomize it.
    randomized_graph = {}
    randomized_nodes = list(t._obj.keys())
    random.shuffle(randomized_nodes)
    for node in randomized_nodes:
        edges = t._obj[node]
        random.shuffle(edges)
        randomized_graph[node] = edges
    assert set(randomized_graph) == set(t._obj)

    # Create a randomized package tree.
    randomized_dag = p.PackageDAG(randomized_graph)
    assert len(t) == len(randomized_dag)
    return randomized_dag


def test_render_mermaid():
    # Check both the sorted and randomized package tree produces the same sorted
    # Mermaid output.
    for package_tree in (t, randomized_dag_copy(t)):
        output = p.render_mermaid(package_tree)
        assert output == dedent(
            """\
            flowchart TD
                classDef missing stroke-dasharray: 5
                a[a\\n3.4.0]
                b[b\\n2.3.1]
                c[c\\n5.10.0]
                d[d\\n2.35]
                e[e\\n0.12.1]
                f[f\\n3.1]
                g[g\\n6.8.3rc1]
                a -- >=2.0.0 --> b
                a -- >=5.7.1 --> c
                b -- >=2.30,<2.42 --> d
                c -- >=0.12.1 --> e
                c -- >=2.30 --> d
                d -- >=0.9.0 --> e
                f -- >=2.1.0 --> b
                g -- >=0.9.0 --> e
                g -- >=3.0.0 --> f
            """
        )


def test_render_dot(capsys):
    # Check both the sorted and randomized package tree produces the same sorted
    # graphviz output.
    for package_tree in (t, randomized_dag_copy(t)):
        output = p.dump_graphviz(package_tree, output_format="dot")
        p.print_graphviz(output)
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

            """
        )


def test_render_pdf():
    output = p.dump_graphviz(t, output_format="pdf")

    @contextmanager
    def redirect_stdout(new_target):
        old_target, sys.stdout = sys.stdout, new_target
        try:
            yield new_target
        finally:
            sys.stdout = old_target

    with NamedTemporaryFile(delete=True) as f:
        with redirect_stdout(f):
            p.print_graphviz(output)
        rf = open(f.name, "rb")
        assert b"%PDF" == rf.read()[:4]
        # @NOTE: rf is not closed to avoid "bad filedescriptor" error


def test_render_svg(capsys):
    output = p.dump_graphviz(t, output_format="svg")
    p.print_graphviz(output)
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
    result = p.conflicting_deps(tree)
    result_keys = {k.key: [v.key for v in vs] for k, vs in result.items()}
    assert expected_keys == result_keys
    p.render_conflicts_text(result)
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
    result = p.cyclic_deps(tree)
    result_keys = [(a.key, b.key, c.key) for (a, b, c) in result]
    assert sorted(expected_keys) == sorted(result_keys)
    p.render_cycles_text(result)
    captured = capsys.readouterr()
    assert "\n".join(expected_output).strip() == captured.err.strip()


# Tests for the argparse parser


def test_parser_default():
    parser = p.get_parser()
    args = parser.parse_args([])
    assert not args.json
    assert args.output_format is None


def test_parser_j():
    parser = p.get_parser()
    args = parser.parse_args(["-j"])
    assert args.json
    assert args.output_format is None


def test_parser_json():
    parser = p.get_parser()
    args = parser.parse_args(["--json"])
    assert args.json
    assert args.output_format is None


def test_parser_json_tree():
    parser = p.get_parser()
    args = parser.parse_args(["--json-tree"])
    assert args.json_tree
    assert not args.json
    assert args.output_format is None


def test_parser_mermaid():
    parser = p.get_parser()
    args = parser.parse_args(["--mermaid"])
    assert args.mermaid
    assert not args.json
    assert args.output_format is None


def test_parser_pdf():
    parser = p.get_parser()
    args = parser.parse_args(["--graph-output", "pdf"])
    assert args.output_format == "pdf"
    assert not args.json


def test_parser_svg():
    parser = p.get_parser()
    args = parser.parse_args(["--graph-output", "svg"])
    assert args.output_format == "svg"
    assert not args.json


@pytest.mark.parametrize("args_joined", [True, False])
def test_custom_interpreter(tmp_path, monkeypatch, capfd, args_joined):
    result = virtualenv.cli_run([str(tmp_path), "--activators", ""])
    cmd = [sys.executable]
    cmd += [f"--python={result.creator.exe}"] if args_joined else ["--python", str(result.creator.exe)]
    monkeypatch.setattr(sys, "argv", cmd)
    p.main()
    out, _ = capfd.readouterr()
    found = {i.split("==")[0] for i in out.splitlines()}
    implementation = platform.python_implementation()
    if implementation == "CPython":
        expected = {"pip", "setuptools", "wheel"}
    elif implementation == "PyPy":
        expected = {"cffi", "greenlet", "pip", "readline", "setuptools", "wheel"}
    else:
        raise ValueError(implementation)
    assert found == expected, out

    monkeypatch.setattr(sys, "argv", cmd + ["--graph-output", "something"])
    with pytest.raises(SystemExit) as context:
        p.main()
    out, err = capfd.readouterr()
    assert context.value.code == 1
    assert not out
    assert err == "graphviz functionality is not supported when querying" " non-host python\n"


def test_guess_version_setuptools():
    script = Path(__file__).parent / "guess_version_setuptools.py"
    output = subprocess.check_output([sys.executable, script], text=True)
    assert output == "?"
