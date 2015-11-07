import pickle

import pip
from pipdeptree import pipdeptree, _peek_into


def venv_fixture(pickle_file):
    """Loads required virtualenv pkg data from a pickle file
    :param pickle_file: path to a .pickle file
    :returns: a tuple of pkgs, pkg_index, req_map
    :rtype: tuple
    """
    
    with open(pickle_file, 'rb') as f:
        return pickle.load(f)


pkgs = venv_fixture('tests/testenv.pickle')


def test_req_version():
    pdt = pipdeptree()
    sqlalchemy = pdt.get_requirement_instance('alembic', 'sqlalchemy')
    assert pdt.req_version(sqlalchemy) == '>=0.7.3'
    mako = pdt.get_requirement_instance('alembic', 'mako')
    assert pdt.req_version(mako) is None


def test_top_pkg_name():
    pdt = pipdeptree()
    assert pdt.top_pkg_name('alembic') == 'alembic==0.6.2'
    assert pdt.top_pkg_name('markupsafe') == 'MarkupSafe==0.18'
    assert pdt.top_pkg_name('jinja2') == 'Jinja2==2.7.2'


def test_non_top_pkg_name():
    pdt = pipdeptree()
    assert pdt.non_top_pkg_name('mako', 'alembic') == 'Mako [installed: 0.9.1]'
    assert pdt.non_top_pkg_name('markupsafe', 'jinja2') == 'MarkupSafe [installed: 0.18]'
    assert pdt.non_top_pkg_name('markupsafe', 'mako') == 'MarkupSafe [required: >=0.9.2, installed: 0.18]'


def test_non_bottom_pkg_name():
    pdt = pipdeptree()
    assert pdt.non_bottom_pkg_name('alembic', 'sqlalchemy') == 'alembic [installed: 0.6.2, requires: SQLAlchemy>=0.7.3]'
    assert pdt.non_bottom_pkg_name('jinja2', 'markupsafe') == 'Jinja2 [installed: 2.7.2]'
    assert pdt.non_bottom_pkg_name('mako', 'markupsafe') == 'Mako [installed: 0.9.1, requires: MarkupSafe>=0.9.2]'


def test_render_tree_only_top():
    pdt = pipdeptree()
    tree_str = pdt.render_tree()
    lines = set(tree_str.split('\n'))
    assert 'alembic==0.6.2' in lines
    assert '  - SQLAlchemy [required: >=0.7.3, installed: 0.9.1]' in lines
    assert 'Lookupy==0.1' in lines
    assert 'Mako==0.9.1' not in lines


def test_render_tree_list_all():
    pdt = pipdeptree()
    tree_str = pdt.render_tree(list_all=True)
    lines = set(tree_str.split('\n'))
    assert 'Sphinx==1.3.1' in lines
    assert '  - SQLAlchemy [required: >=0.7.3, installed: 0.9.1]' in lines
    assert 'Lookupy==0.1' in lines
    assert 'Mako==0.9.1' in lines


def test_render_tree_freeze():
    pdt = pipdeptree()
    tree_str = pdt.render_tree(bullets=False)
    lines = set()
    for line in tree_str.split('\n'):
        # Workaround for https://github.com/pypa/pip/issues/1867
        # When hash randomization is enabled, pip can return different names
        # for git editables from run to run
        line = line.replace('origin/master', 'master')
        line = line.replace('origin/HEAD', 'master')
        lines.add(line)
    assert 'alembic==0.6.2' in lines
    assert '    SQLAlchemy==0.9.1' in lines
    assert '-e git+https://github.com/naiquevin/lookupy.git@cdbe30c160e1c29802df75e145ea4ad903c05386#egg=Lookupy-master' in lines
    assert 'Mako==0.9.1' not in lines


def test_render_tree_cyclic_dependency():
    pdt = pipdeptree()
    tree_str = pdt.render_tree(list_all=True)
    lines = set(tree_str.split('\n'))
    assert 'Sphinx==1.3.1' in lines
    assert '  - sphinx-rtd-theme [required: >=0.1, installed: 0.1.9]' in lines
    assert 'sphinx-rtd-theme==0.1.9' in lines
    assert '  - Sphinx [required: >=1.3, installed: 1.3.1]' in lines


def test_render_tree_freeze_cyclic_dependency():
    pdt = pipdeptree()
    tree_str = pdt.render_tree(list_all=True, bullets=False)
    lines = set(tree_str.split('\n'))
    assert 'Sphinx==1.3.1' in lines
    assert '    sphinx-rtd-theme==0.1.9' in lines
    assert 'sphinx-rtd-theme==0.1.9' in lines
    assert '    Sphinx==1.3.1' in lines


def test_render_tree_only_top_reverse():
    pdt = pipdeptree()
    tree_str = pdt.render_tree(reverse=True)
    lines = set(tree_str.split('\n'))
    assert '    - alembic [installed: 0.6.2]' in lines
    assert '  - alembic [installed: 0.6.2, requires: SQLAlchemy>=0.7.3]' in lines
    assert 'docutils==0.12' in lines
    assert 'six==1.10.0' in lines


def test_render_tree_list_all_reverse():
    pdt = pipdeptree()
    tree_str = pdt.render_tree(list_all=True, reverse=True)
    lines = set(tree_str.split('\n'))
    assert '    - sphinx-rtd-theme [installed: 0.1.9, requires: sphinx>=1.3]' in lines
    assert '  - sphinx-rtd-theme [installed: 0.1.9, requires: sphinx>=1.3]' in lines
    assert 'Mako==0.9.1' in lines
    assert 'alembic==0.6.2' in lines


def test_render_tree_freeze_reverse():
    pdt = pipdeptree()
    tree_str = pdt.render_tree(bullets=False, reverse=True)
    lines = set()
    for line in tree_str.split('\n'):
        # Workaround for https://github.com/pypa/pip/issues/1867
        # When hash randomization is enabled, pip can return different names
        # for git editables from run to run
        line = line.replace('origin/master', 'master')
        line = line.replace('origin/HEAD', 'master')
        lines.add(line)
    assert '      sphinx-rtd-theme==0.1.9' in lines
    assert '    Babel=2.1.1' not in lines
    assert '-e git+https://github.com/naiquevin/lookupy.git@cdbe30c160e1c29802df75e145ea4ad903c05386#egg=Lookupy-master' in lines
    assert 'six==1.10.0' in lines


def test__peek_into():
    r1, g1 = _peek_into(i for i in [])
    assert r1
    assert len(list(g1)) == 0
    r2, g2 = _peek_into(i for i in range(100))
    assert not r2
    assert len(list(g2)) == 100
