
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


def mock_tree(simple_graph):
    pkgs = list(mock_pkgs(simple_graph))
    return p.Tree.from_pkgs(pkgs)


# util for comparing tree contents with a simple graph
def tree_to_simple_graph(tree):
    return {k.key: [v.key for v in vs] for k, vs in tree._obj.items()}


t = mock_tree({'a': ['b', 'c'],
               'b': ['d'],
               'c': ['d', 'e'],
               'd': ['e'],
               'e': [],
               'f': ['b'],
               'g': ['e', 'f']})


def test_Tree__lookup():
    assert 'b' == t.lookup('b').key
    assert 'c' == t.lookup('c').key


def test_Tree__child_keys():
    assert {'b', 'c', 'd', 'e', 'f'} == t._child_keys


def test_Tree_filter():
    # When both show_only and exclude are not specified, same tree
    # object is returned
    assert t.filter(None, None) is t

    # when show_only is specified
    g1 = tree_to_simple_graph(t.filter(set(['a', 'd']), None))
    expected = {'a': ['b', 'c'],
                'b': ['d'],
                'c': ['d', 'e'],
                'd': ['e'],
                'e': []}
    assert expected == g1

    # when exclude is specified
    g2 = tree_to_simple_graph(t.filter(None, ['d']))
    expected = {'a': ['b', 'c'],
                'b': [],
                'c': ['e'],
                'e': [],
                'f': ['b'],
                'g': ['e', 'f']}
    assert expected == g2

    # when both show_only and exclude are specified
    g3 = tree_to_simple_graph(t.filter(set(['a', 'g']), set(['d', 'e'])))
    expected = {'a': ['b', 'c'],
                'b': [],
                'c': [],
                'f': ['b'],
                'g': ['f']}
    assert expected == g3

    # when conflicting values in show_only and exclude, AssertionError
    # is raised
    with pytest.raises(AssertionError):
        tree_to_simple_graph(t.filter(set(['d']), set(['d', 'e'])))


def test_Tree_reverse():
    t1 = t.reverse()
    expected = {'a': [],
                'b': ['a', 'f'],
                'c': ['a'],
                'd': ['b', 'c'],
                'e': ['c', 'd', 'g'],
                'f': ['g'],
                'g': []}
    sort_children = lambda m: {k: sorted(v) for k, v in m.items()}
    assert isinstance(t1, p.ReverseTree)
    assert sort_children(expected) == sort_children(tree_to_simple_graph(t1))
