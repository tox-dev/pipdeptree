
try:
    from unittest import mock
except ImportError:
    import mock

import pytest

import pipdeptree as p


def mock_pkgs(simple_graph):
    for node, children in simple_graph.items():
        p = mock.Mock(key=node, project_name=node)
        as_req = mock.Mock(key=node, project_name=node)
        p.as_requirement = mock.Mock(return_value=as_req)
        reqs = []
        for c in children:
            r = mock.Mock(key=c, project_name=c)
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


t = mock_PackageDAG({'a': ['b', 'c'],
                     'b': ['d'],
                     'c': ['d', 'e'],
                     'd': ['e'],
                     'e': [],
                     'f': ['b'],
                     'g': ['e', 'f']})


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
