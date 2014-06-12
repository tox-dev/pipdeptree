import pickle

from pipdeptree import (req_version, render_tree,
                        top_pkg_name, non_top_pkg_name,
                        top_pkg_src, non_top_pkg_src)


with open('tests/pkgs.pickle', 'rb') as f:
    pkgs = pickle.load(f)


pkg_index = dict([(p.key, p) for p in pkgs])  # {p.key: p for p in pkgs}
req_map = dict([(p, p.requires()) for p in pkgs])  # {p: p.requires() for p in pkgs}


def find_req(req, parent):
    """Helper to get the requirement object from it's parent package

    :param req    : string
    :param parent : pkg_resources.Distribution instance
    :rtype        : instance of requirement frozen set

    """
    return [r for r in pkg_index[parent].requires() if r.key == req][0]


def test_req_version():
    sqlalchemy = find_req('sqlalchemy', 'alembic')
    assert req_version(sqlalchemy) == '>=0.7.3'
    mako = find_req('mako', 'alembic')
    assert req_version(mako) is None


def test_non_top_pkg_name():
    flask_p = pkg_index['flask']
    flask_r = find_req('flask', 'flask-script')
    assert non_top_pkg_name(flask_r, flask_p) == 'Flask [installed: 0.10.1]'

    markupsafe_p = pkg_index['markupsafe']
    markupsafe_jinja2_r = find_req('markupsafe', 'jinja2')
    assert non_top_pkg_name(markupsafe_jinja2_r, markupsafe_p) == 'MarkupSafe [installed: 0.18]'

    markupsafe_mako_r = find_req('markupsafe', 'mako')
    assert non_top_pkg_name(markupsafe_mako_r, markupsafe_p) == 'MarkupSafe [required: >=0.9.2, installed: 0.18]'


def test_render_tree_only_top():
    tree_str = render_tree(pkgs, pkg_index, req_map, False,
                           top_pkg_name, non_top_pkg_name)
    lines = set(tree_str.split('\n'))
    assert 'Flask-Script==0.6.6' in lines
    assert '  - SQLAlchemy [required: >=0.7.3, installed: 0.9.1]' in lines
    assert 'Lookupy==0.1' in lines
    assert 'itsdangerous==0.23' not in lines


def test_render_tree_list_all():
    tree_str = render_tree(pkgs, pkg_index, req_map, True,
                           top_pkg_name, non_top_pkg_name)
    lines = set(tree_str.split('\n'))
    assert 'Flask-Script==0.6.6' in lines
    assert '  - SQLAlchemy [required: >=0.7.3, installed: 0.9.1]' in lines
    assert 'Lookupy==0.1' in lines
    assert 'itsdangerous==0.23' in lines


def test_render_tree_freeze():
    tree_str = render_tree(pkgs, pkg_index, req_map, False,
                           top_pkg_src, non_top_pkg_src)
    lines = set(tree_str.split('\n'))
    assert 'Flask-Script==0.6.6' in lines
    assert '  - SQLAlchemy==0.9.1' in lines
    assert '-e git+git@github.com:naiquevin/lookupy.git@cdbe30c160e1c29802df75e145ea4ad903c05386#egg=Lookupy-master' in lines
    assert 'itsdangerous==0.23' not in lines
