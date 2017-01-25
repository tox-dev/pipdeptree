import json
import os
import pickle
import sys
from contextlib import contextmanager
from tempfile import NamedTemporaryFile
from operator import attrgetter

from pipdeptree import (build_dist_index, construct_tree,
                        DistPackage, ReqPackage, render_tree,
                        reverse_tree, cyclic_deps, conflicting_deps,
                        get_parser, jsonify_tree, dump_graphviz,
                        print_graphviz)


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
    assert all(isinstance(k, ReqPackage) for k, vs in rtree.items())
    assert all(all(isinstance(v, DistPackage) for v in vs)
               for k, vs in rtree.items())
    assert all(all(v.req is not None for v in vs)
               for k, vs in rtree.items())


def test_DistPackage_render_as_root():
    alembic = find_dist('alembic')
    assert alembic.version == '0.6.2'
    assert alembic.project_name == 'alembic'
    assert alembic.render_as_root(frozen=False) == 'alembic==0.6.2'


def test_DistPackage_render_as_branch():
    sqlalchemy = find_req('sqlalchemy', 'alembic')
    alembic = find_dist('alembic').as_required_by(sqlalchemy)
    assert alembic.project_name == 'alembic'
    assert alembic.version == '0.6.2'
    assert sqlalchemy.project_name == 'SQLAlchemy'
    assert sqlalchemy.version_spec == '>=0.7.3'
    assert sqlalchemy.installed_version == '0.9.1'
    result_1 = alembic.render_as_branch(False)
    result_2 = alembic.render_as_branch(False)
    assert result_1 == result_2 == 'alembic==0.6.2 [requires: SQLAlchemy>=0.7.3]'


def test_ReqPackage_render_as_root():
    flask = find_req('flask', 'flask-script')
    assert flask.project_name == 'Flask'
    assert flask.installed_version == '0.10.1'
    assert flask.render_as_root(frozen=False) == 'Flask==0.10.1'


def test_ReqPackage_render_as_branch():
    mks1 = find_req('markupsafe', 'jinja2')
    assert mks1.project_name == 'markupsafe'
    assert mks1.installed_version == '0.18'
    assert mks1.version_spec is None
    assert mks1.render_as_branch(False) == 'markupsafe [required: Any, installed: 0.18]'
    assert mks1.render_as_branch(True) == 'MarkupSafe==0.18'
    mks2 = find_req('markupsafe', 'mako')
    assert mks2.project_name == 'MarkupSafe'
    assert mks2.installed_version == '0.18'
    assert mks2.version_spec == '>=0.9.2'
    assert mks2.render_as_branch(False) == 'MarkupSafe [required: >=0.9.2, installed: 0.18]'
    assert mks2.render_as_branch(True) == 'MarkupSafe==0.18'


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
    assert '  SQLAlchemy==0.9.1' in lines
    # TODO! Fix the following failing test
    # assert '-e git+https://github.com/naiquevin/lookupy.git@cdbe30c160e1c29802df75e145ea4ad903c05386#egg=Lookupy-master' in lines
    assert 'itsdangerous==0.23' not in lines


def test_render_json(capsys):
    output = jsonify_tree(tree, indent=4)
    print_graphviz(output)
    out, _ = capsys.readouterr()
    assert out.startswith('[\n    {\n        "')
    assert out.strip().endswith('}\n]')
    data = json.loads(out)
    assert 'package' in data[0]
    assert 'dependencies' in data[0]


def test_render_pdf():
    output = dump_graphviz(tree, output_format='pdf')

    @contextmanager
    def redirect_stdout(new_target):
        old_target, sys.stdout = sys.stdout, new_target
        try:
            yield new_target
        finally:
            sys.stdout = old_target

    f = NamedTemporaryFile(delete=False)
    with redirect_stdout(f):
        print_graphviz(output)
    with open(f.name, 'rb') as rf:
        out = rf.read()
    os.remove(f.name)
    assert out[:4] == b'%PDF'


def test_render_svg(capsys):
    output = dump_graphviz(tree, output_format='svg')
    print_graphviz(output)
    out, _ = capsys.readouterr()
    assert out.startswith('<?xml')
    assert '<svg' in out
    assert out.strip().endswith('</svg>')


def test_parser_default():
    parser = get_parser()
    args = parser.parse_args([])
    assert not args.json
    assert args.output_format is None


def test_parser_j():
    parser = get_parser()
    args = parser.parse_args(['-j'])
    assert args.json
    assert args.output_format is None


def test_parser_json():
    parser = get_parser()
    args = parser.parse_args(['--json'])
    assert args.json
    assert args.output_format is None


def test_parser_pdf():
    parser = get_parser()
    args = parser.parse_args(['--graph-output', 'pdf'])
    assert args.output_format == 'pdf'
    assert not args.json


def test_parser_svg():
    parser = get_parser()
    args = parser.parse_args(['--graph-output', 'svg'])
    assert args.output_format == 'svg'
    assert not args.json


def test_cyclic_dependencies():
    cyclic_pkgs, dist_index, tree = venv_fixture('tests/virtualenvs/cyclicenv.pickle')
    cyclic = [map(attrgetter('key'), cs) for cs in cyclic_deps(tree)]
    assert len(cyclic) == 2
    a, b, c = cyclic[0]
    x, y, z = cyclic[1]
    assert a == c == y
    assert x == z == b


def test_render_tree_cyclic_dependency():
    cyclic_pkgs, dist_index, tree = venv_fixture('tests/virtualenvs/cyclicenv.pickle')
    tree_str = render_tree(tree, list_all=True)
    lines = set(tree_str.split('\n'))
    assert 'CircularDependencyA==0.0.0' in lines
    assert '  - CircularDependencyB [required: Any, installed: 0.0.0]' in lines
    assert 'CircularDependencyB==0.0.0' in lines
    assert '  - CircularDependencyA [required: Any, installed: 0.0.0]' in lines


def test_render_tree_freeze_cyclic_dependency():
    cyclic_pkgs, dist_index, tree = venv_fixture('tests/virtualenvs/cyclicenv.pickle')
    tree_str = render_tree(tree, list_all=True, frozen=True)
    lines = set(tree_str.split('\n'))
    assert 'CircularDependencyA==0.0.0' in lines
    assert '  CircularDependencyB==0.0.0' in lines
    assert 'CircularDependencyB==0.0.0' in lines
    assert '  CircularDependencyA==0.0.0' in lines


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
