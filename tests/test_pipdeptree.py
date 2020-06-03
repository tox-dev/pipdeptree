from contextlib import contextmanager
import sys
from tempfile import NamedTemporaryFile
try:
    from unittest import mock
except ImportError:
    import mock

import pytest

import pipdeptree as p


# Tests for DAG classes

def mock_pkgs(simple_graph):
    for node, children in simple_graph.items():
        nk, nv = node
        p = mock.Mock(key=nk, project_name=nk, version=nv)
        as_req = mock.Mock(key=nk, project_name=nk, specs=[('==', nv)])
        p.as_requirement = mock.Mock(return_value=as_req)
        reqs = []
        for child in children:
            ck, cv = child
            r = mock.Mock(key=ck, project_name=ck, specs=cv)
            reqs.append(r)
        p.requires = mock.Mock(return_value=reqs)
        yield p


def mock_PackageDAG(simple_graph):
    pkgs = list(mock_pkgs(simple_graph))
    return p.PackageDAG.from_pkgs(pkgs)


# util for comparing tree contents with a simple graph
def dag_to_dict(g):
    return {k.key: [v.key for v in vs] for k, vs in g._obj.items()}


def sort_map_values(m):
    return {k: sorted(v) for k, v in m.items()}


t = mock_PackageDAG({
    ('a', '3.4.0'): [('b', [('>=', '2.0.0')]),
                     ('c', [('>=', '5.7.1')])],
    ('b', '2.3.1'): [('d', [('>=', '2.30'), ('<', '2.42')])],
    ('c', '5.10.0'): [('d', [('>=', '2.30')]),
                      ('e', [('>=', '0.12.1')])],
    ('d', '2.35'): [('e', [('>=', '0.9.0')])],
    ('e', '0.12.1'): [],
    ('f', '3.1'): [('b', [('>=', '2.1.0')])],
    ('g', '6.8.3rc1'): [('e', [('>=', '0.9.0')]),
                        ('f', [('>=', '3.0.0')])]
})


def test_PackageDAG__get_node_as_parent():
    assert 'b' == t.get_node_as_parent('b').key
    assert 'c' == t.get_node_as_parent('c').key


def test_PackageDAG_filter():
    # When both show_only and exclude are not specified, same tree
    # object is returned
    assert t.filter(None, None) is t

    # when show_only is specified
    g1 = dag_to_dict(t.filter(set(['a', 'd']), None))
    expected = {'a': ['b', 'c'],
                'b': ['d'],
                'c': ['d', 'e'],
                'd': ['e'],
                'e': []}
    assert expected == g1

    # when exclude is specified
    g2 = dag_to_dict(t.filter(None, ['d']))
    expected = {'a': ['b', 'c'],
                'b': [],
                'c': ['e'],
                'e': [],
                'f': ['b'],
                'g': ['e', 'f']}
    assert expected == g2

    # when both show_only and exclude are specified
    g3 = dag_to_dict(t.filter(set(['a', 'g']), set(['d', 'e'])))
    expected = {'a': ['b', 'c'],
                'b': [],
                'c': [],
                'f': ['b'],
                'g': ['f']}
    assert expected == g3

    # when conflicting values in show_only and exclude, AssertionError
    # is raised
    with pytest.raises(AssertionError):
        dag_to_dict(t.filter(set(['d']), set(['D', 'e'])))


def test_PackageDAG_reverse():
    t1 = t.reverse()
    expected = {'a': [],
                'b': ['a', 'f'],
                'c': ['a'],
                'd': ['b', 'c'],
                'e': ['c', 'd', 'g'],
                'f': ['g'],
                'g': []}
    assert isinstance(t1, p.ReversedPackageDAG)
    assert sort_map_values(expected) == sort_map_values(dag_to_dict(t1))
    assert all([isinstance(k, p.ReqPackage) for k in t1.keys()])
    assert all([isinstance(v, p.DistPackage) for v in p.flatten(t1.values())])

    # testing reversal of ReversedPackageDAG instance
    expected = {'a': ['b', 'c'],
                'b': ['d'],
                'c': ['d', 'e'],
                'd': ['e'],
                'e': [],
                'f': ['b'],
                'g': ['e', 'f']}
    t2 = t1.reverse()
    assert isinstance(t2, p.PackageDAG)
    assert sort_map_values(expected) == sort_map_values(dag_to_dict(t2))
    assert all([isinstance(k, p.DistPackage) for k in t2.keys()])
    assert all([isinstance(v, p.ReqPackage) for v in p.flatten(t2.values())])


# Tests for Package classes
#
# Note: For all render methods, we are only testing for frozen=False
# as mocks with frozen=True are a lot more complicated

def test_DistPackage__render_as_root():
    foo = mock.Mock(key='foo', project_name='foo', version='20.4.1')
    dp = p.DistPackage(foo)
    is_frozen = False
    assert 'foo==20.4.1' == dp.render_as_root(is_frozen)


def test_DistPackage__render_as_branch():
    foo = mock.Mock(key='foo', project_name='foo', version='20.4.1')
    bar = mock.Mock(key='bar', project_name='bar', version='4.1.0')
    bar_req = mock.Mock(key='bar',
                        project_name='bar',
                        version='4.1.0',
                        specs=[('>=', '4.0')])
    rp = p.ReqPackage(bar_req, dist=bar)
    dp = p.DistPackage(foo).as_parent_of(rp)
    is_frozen = False
    assert 'foo==20.4.1 [requires: bar>=4.0]' == dp.render_as_branch(is_frozen)


def test_DistPackage__as_parent_of():
    foo = mock.Mock(key='foo', project_name='foo', version='20.4.1')
    dp = p.DistPackage(foo)
    assert dp.req is None

    bar = mock.Mock(key='bar', project_name='bar', version='4.1.0')
    bar_req = mock.Mock(key='bar',
                        project_name='bar',
                        version='4.1.0',
                        specs=[('>=', '4.0')])
    rp = p.ReqPackage(bar_req, dist=bar)
    dp1 = dp.as_parent_of(rp)
    assert dp1._obj == dp._obj
    assert dp1.req is rp

    dp2 = dp.as_parent_of(None)
    assert dp2 is dp


def test_DistPackage__as_dict():
    foo = mock.Mock(key='foo', project_name='foo', version='1.3.2b1')
    dp = p.DistPackage(foo)
    result = dp.as_dict()
    expected = {'key': 'foo',
                'package_name': 'foo',
                'installed_version': '1.3.2b1'}
    assert expected == result


def test_ReqPackage__render_as_root():
    bar = mock.Mock(key='bar', project_name='bar', version='4.1.0')
    bar_req = mock.Mock(key='bar',
                        project_name='bar',
                        version='4.1.0',
                        specs=[('>=', '4.0')])
    rp = p.ReqPackage(bar_req, dist=bar)
    is_frozen = False
    assert 'bar==4.1.0' == rp.render_as_root(is_frozen)


def test_ReqPackage__render_as_branch():
    bar = mock.Mock(key='bar', project_name='bar', version='4.1.0')
    bar_req = mock.Mock(key='bar',
                        project_name='bar',
                        version='4.1.0',
                        specs=[('>=', '4.0')])
    rp = p.ReqPackage(bar_req, dist=bar)
    is_frozen = False
    assert 'bar [required: >=4.0, installed: 4.1.0]' == rp.render_as_branch(is_frozen)


def test_ReqPackage__as_dict():
    bar = mock.Mock(key='bar', project_name='bar', version='4.1.0')
    bar_req = mock.Mock(key='bar',
                        project_name='bar',
                        version='4.1.0',
                        specs=[('>=', '4.0')])
    rp = p.ReqPackage(bar_req, dist=bar)
    result = rp.as_dict()
    expected = {'key': 'bar',
                'package_name': 'bar',
                'installed_version': '4.1.0',
                'required_version': '>=4.0'}
    assert expected == result


# Tests for graph outputs

def test_render_pdf():
    output = p.dump_graphviz(t, output_format='pdf')

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
        rf = open(f.name, 'rb')
        assert b'%PDF' == rf.read()[:4]
        # @NOTE: rf is not closed to avoid "bad filedescriptor" error


def test_render_svg(capsys):
    output = p.dump_graphviz(t, output_format='svg')
    p.print_graphviz(output)
    out, _ = capsys.readouterr()
    assert out.startswith('<?xml')
    assert '<svg' in out
    assert out.strip().endswith('</svg>')
