import pickle

from pipdeptree import req_version, non_top_pkg_name, render_tree


with open('tests/pkgs.pickle', 'rb') as f:
    pkgs = pickle.load(f)


pkg_index = {p.key: p for p in pkgs}


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
    assert non_top_pkg_name(flask_r, flask_p) == 'flask [installed: 0.10.1]'

    markupsafe_p = pkg_index['markupsafe']
    markupsafe_jinja2_r = find_req('markupsafe', 'jinja2')
    assert non_top_pkg_name(markupsafe_jinja2_r, markupsafe_p) == 'markupsafe [installed: 0.18]'

    markupsafe_mako_r = find_req('markupsafe', 'mako')
    assert non_top_pkg_name(markupsafe_mako_r, markupsafe_p) == 'markupsafe [required: >=0.9.2, installed: 0.18]'


def test_render_tree_only_top():
    tree_str = render_tree(pkgs, False)
    lines = set(tree_str.split('\n'))
    assert 'flask-script==0.6.6' in lines
    assert '  - sqlalchemy [required: >=0.7.3, installed: 0.9.1]' in lines
    assert 'itsdangerous==0.23' not in lines


def test_render_tree_list_all():
    tree_str = render_tree(pkgs, True)
    lines = set(tree_str.split('\n'))
    assert 'flask-script==0.6.6' in lines
    assert '  - sqlalchemy [required: >=0.7.3, installed: 0.9.1]' in lines
    assert 'itsdangerous==0.23' in lines
