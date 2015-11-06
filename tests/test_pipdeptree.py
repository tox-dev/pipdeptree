import pickle

from pipdeptree import pipdeptree, _peek_into


def test_req_version():
    pdt = pipdeptree()
    sqlalchemy = pdt.get_requirement_instance('alembic', 'sqlalchemy')
    assert pdt.req_version(sqlalchemy) == '>=0.7.3'
    mako = pdt.get_requirement_instance('alembic', 'mako')
    assert pdt.req_version(mako) is None


def test_top_pkg_name():
    pdt = pipdeptree()
    assert pdt.top_pkg_name('flask') == 'Flask==0.10.1'
    assert pdt.top_pkg_name('markupsafe') == 'MarkupSafe==0.18'
    assert pdt.top_pkg_name('jinja2') == 'Jinja2==2.7.2'


def test_non_top_pkg_name():
    pdt = pipdeptree()
    assert pdt.non_top_pkg_name('flask', 'flask-script') == 'Flask [installed: 0.10.1]'
    assert pdt.non_top_pkg_name('markupsafe', 'jinja2') == 'MarkupSafe [installed: 0.18]'
    assert pdt.non_top_pkg_name('markupsafe', 'mako') == 'MarkupSafe [required: >=0.9.2, installed: 0.18]'


def test_non_bottom_pkg_name():
    pdt = pipdeptree()
    assert pdt.non_bottom_pkg_name('flask-script', 'flask') == 'Flask-Script [installed: 0.6.6]'
    assert pdt.non_bottom_pkg_name('jinja2', 'markupsafe') == 'Jinja2 [installed: 2.7.2]'
    assert pdt.non_bottom_pkg_name('mako', 'markupsafe') == 'Mako [installed: 0.9.1, requires: MarkupSafe>=0.9.2]'


def test_render_tree_only_top():
    pdt = pipdeptree()
    tree_str = pdt.render_tree()
    lines = set(tree_str.split('\n'))
    assert 'Flask-Script==0.6.6' in lines
    assert '  - SQLAlchemy [required: >=0.7.3, installed: 0.9.1]' in lines
    assert 'Lookupy==0.1' in lines
    assert 'itsdangerous==0.23' not in lines


def test_render_tree_list_all():
    pdt = pipdeptree()
    tree_str = pdt.render_tree(list_all=True)
    lines = set(tree_str.split('\n'))
    assert 'Flask-Script==0.6.6' in lines
    assert '  - SQLAlchemy [required: >=0.7.3, installed: 0.9.1]' in lines
    assert 'Lookupy==0.1' in lines
    assert 'itsdangerous==0.23' in lines


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
    assert 'Flask-Script==0.6.6' in lines
    assert '    SQLAlchemy==0.9.1' in lines
    assert '-e git+https://github.com/naiquevin/lookupy.git@cdbe30c160e1c29802df75e145ea4ad903c05386#egg=Lookupy-master' in lines
    assert 'itsdangerous==0.23' not in lines


def test_render_tree_cyclic_dependency():
    pdt = pipdeptree()
    tree_str = pdt.render_tree()
    lines = set(tree_str.split('\n'))
    assert 'CircularDependencyA==0.0.0' in lines
    assert '  - CircularDependencyB [installed: 0.0.0]' in lines
    assert 'CircularDependencyB==0.0.0' in lines
    assert '  - CircularDependencyA [installed: 0.0.0]' in lines


def test_render_tree_freeze_cyclic_dependency():
    pdt = pipdeptree()
    tree_str = pdt.render_tree(bullets=False)
    lines = set(tree_str.split('\n'))
    assert 'CircularDependencyA==0.0.0' in lines
    assert '  - CircularDependencyB==0.0.0' in lines
    assert 'CircularDependencyB==0.0.0' in lines
    assert '  - CircularDependencyA==0.0.0' in lines


def test_render_tree_only_top_reverse():
    pdt = pipdeptree()
    tree_str = pdt.render_tree(reverse=True)
    lines = set(tree_str.split('\n'))
    assert '    - Flask-Script [installed: 0.6.6]' in lines
    assert '  - Flask [installed: 0.10.1, requires: Werkzeug>=0.7]' in lines
    assert '    - Flask [installed: 0.10.1, requires: Jinja2>=2.4]' in lines
    assert 'itsdangerous==0.23' in lines


def test_render_tree_list_all_reverse():
    pdt = pipdeptree()
    tree_str = pdt.render_tree(list_all=True, reverse=True)
    lines = set(tree_str.split('\n'))
    assert '    - Flask-Script [installed: 0.6.6]' in lines
    assert '  - Flask-Script [installed: 0.6.6]' in lines
    assert 'Flask-Script==0.6.6' in lines
    assert 'itsdangerous==0.23' in lines


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
    assert 'MarkupSafe==0.18' in lines
    assert '        MarkupSafe==0.18' not in lines
    assert '-e git+https://github.com/naiquevin/lookupy.git@cdbe30c160e1c29802df75e145ea4ad903c05386#egg=Lookupy-master' in lines
    assert 'itsdangerous==0.23' in lines


def test__peek_into():
    r1, g1 = _peek_into(i for i in [])
    assert r1
    assert len(list(g1)) == 0
    r2, g2 = _peek_into(i for i in range(100))
    assert not r2
    assert len(list(g2)) == 100
