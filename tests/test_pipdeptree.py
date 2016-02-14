import pickle

from pipdeptree import (build_dist_index, construct_tree, peek_into,
                        DistPackage, ReqPackage, render_tree,
                        reverse_tree, conflicting_deps)


def venv_fixture(pickle_file):
    """Loads required virtualenv pkg data from a pickle file

    :param pickle_file: path to a .pickle file
    :returns: a tuple of pkgs, pkg_index, req_map
    :rtype: tuple

    """
    with open(pickle_file, 'rb') as f:
        pkgs = pickle.load(f)
        dist_index = build_dist_index(pkgs)
        tree = construct_tree(dist_index)
        return pkgs, dist_index, tree


pkgs, dist_index, tree = venv_fixture('tests/virtualenvs/testenv.pickle')


def find_dist(key):
    return dist_index[key]


def find_req(key, parent_key):
    parent = [x for x in tree.keys() if x.key == parent_key][0]
    return [x for x in tree[parent] if x.key == key][0]


def test_build_dist_index():
    assert len(dist_index) == len(pkgs)
    assert all(isinstance(x, str) for x in dist_index.keys())
    assert all(isinstance(x, DistPackage) for x in dist_index.values())


def test_tree():
    assert len(tree) == len(pkgs)
    assert all((isinstance(k, DistPackage) and
                all(isinstance(v, ReqPackage) for v in vs))
               for k, vs in tree.items())


def test_reverse_tree():
    rtree = reverse_tree(tree)
    assert all((isinstance(k, ReqPackage) and
                all(isinstance(v, DistPackage) for v in vs))
               for k, vs in rtree.items())


def test_DistPackage_render_as_root():
    alembic = find_dist('alembic')
    assert alembic.version == '0.6.2'
    assert alembic.project_name == 'alembic'
    assert alembic.render_as_root(frozen=False) == 'alembic==0.6.2'


def test_DistPackage_render_as_branch():
    alembic = find_dist('alembic')
    assert alembic.project_name == 'alembic'
    assert alembic.version == '0.6.2'
    sqlalchemy = find_req('sqlalchemy', 'alembic')
    assert sqlalchemy.project_name == 'SQLAlchemy'
    assert sqlalchemy.version_spec == '>=0.7.3'
    assert sqlalchemy.installed_version == '0.9.1'
    result_1 = alembic.render_as_branch(sqlalchemy, False)
    result_2 = alembic.render_as_branch(sqlalchemy, False)
    assert result_1 == result_2 == 'alembic==0.6.2 [requires: SQLAlchemy>=0.7.3]'


def test_ReqPackage_render_as_root():
    flask = find_req('flask', 'flask-script')
    assert flask.project_name == 'Flask'
    assert flask.installed_version == '0.10.1'
    assert flask.render_as_root(frozen=False) == 'Flask==0.10.1'


def test_ReqPackage_render_as_branch():
    mks1 = find_req('markupsafe', 'jinja2')
    jinja = find_dist('jinja2')
    assert mks1.project_name == 'markupsafe'
    assert mks1.installed_version == '0.18'
    assert mks1.version_spec is None
    assert mks1.render_as_branch(jinja, False) == 'markupsafe [installed: 0.18]'
    assert mks1.render_as_branch(jinja, True) == 'MarkupSafe==0.18'
    mks2 = find_req('markupsafe', 'mako')
    mako = find_dist('mako')
    assert mks2.project_name == 'MarkupSafe'
    assert mks2.installed_version == '0.18'
    assert mks2.version_spec == '>=0.9.2'
    assert mks2.render_as_branch(mako, False) == 'MarkupSafe [required: >=0.9.2, installed: 0.18]'
    assert mks2.render_as_branch(mako, True) == 'MarkupSafe==0.18'


def test_render_tree_only_top():
    tree_str = render_tree(tree, list_all=False)
    lines = set(tree_str.split('\n'))
    assert 'Flask-Script==0.6.6' in lines
    assert '  - SQLAlchemy [required: >=0.7.3, installed: 0.9.1]' in lines
    assert 'Lookupy==0.1' in lines
    assert 'itsdangerous==0.23' not in lines


def test_render_tree_list_all():
    tree_str = render_tree(tree, list_all=True)
    lines = set(tree_str.split('\n'))
    assert 'Flask-Script==0.6.6' in lines
    assert '  - SQLAlchemy [required: >=0.7.3, installed: 0.9.1]' in lines
    assert 'Lookupy==0.1' in lines
    assert 'itsdangerous==0.23' in lines


def test_render_tree_freeze():
    tree_str = render_tree(tree, list_all=False, frozen=True)
    lines = set()
    for line in tree_str.split('\n'):
        # Workaround for https://github.com/pypa/pip/issues/1867
        # When hash randomization is enabled, pip can return different names
        # for git editables from run to run
        line = line.replace('origin/master', 'master')
        line = line.replace('origin/HEAD', 'master')
        lines.add(line)
    assert 'Flask-Script==0.6.6' in lines
    assert '    SQLAlchemy==0.9.1' in lines
    # TODO! Fix the following failing test
    # assert '-e git+https://github.com/naiquevin/lookupy.git@cdbe30c160e1c29802df75e145ea4ad903c05386#egg=Lookupy-master' in lines
    assert 'itsdangerous==0.23' not in lines


def test_render_tree_cyclic_dependency():
    cyclic_pkgs, dist_index, tree = venv_fixture('tests/virtualenvs/cyclicenv.pickle')
    tree_str = render_tree(tree, list_all=True)
    lines = set(tree_str.split('\n'))
    assert 'CircularDependencyA==0.0.0' in lines
    assert '  - CircularDependencyB [installed: 0.0.0]' in lines
    assert 'CircularDependencyB==0.0.0' in lines
    assert '  - CircularDependencyA [installed: 0.0.0]' in lines


def test_render_tree_freeze_cyclic_dependency():
    cyclic_pkgs, dist_index, tree = venv_fixture('tests/virtualenvs/cyclicenv.pickle')
    tree_str = render_tree(tree, list_all=True, frozen=True)
    lines = set(tree_str.split('\n'))
    assert 'CircularDependencyA==0.0.0' in lines
    assert '    CircularDependencyB==0.0.0' in lines
    assert 'CircularDependencyB==0.0.0' in lines
    assert '    CircularDependencyA==0.0.0' in lines


def test_peek_into():
    r1, g1 = peek_into(i for i in [])
    assert r1
    assert len(list(g1)) == 0
    r2, g2 = peek_into(i for i in range(100))
    assert not r2
    assert len(list(g2)) == 100


def test_conflicting_deps():
    # the custom environment has a bad jinja version and it's missing simplejson
    _, _, conflicting_tree = venv_fixture('tests/virtualenvs/unsatisfiedenv.pickle')
    flask = next((x for x in conflicting_tree.keys() if x.key == 'flask'))
    jinja = next((x for x in conflicting_tree[flask] if x.key == 'jinja2'))
    uritemplate = next((x for x in conflicting_tree.keys() if x.key == 'uritemplate'))
    simplejson = next((x for x in conflicting_tree[uritemplate] if x.key == 'simplejson'))
    assert jinja
    assert flask
    assert uritemplate
    assert simplejson

    unsatisfied = conflicting_deps(conflicting_tree)
    assert unsatisfied == {
        flask: [jinja],
        uritemplate: [simplejson],
    }
