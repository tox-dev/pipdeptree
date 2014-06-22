pipdeptree
==========

``pipdeptree`` is a command line utility for displaying the python
packages installed in an virtualenv in form of a dependency
tree. Since ``pip freeze`` shows all dependencies as a flat list,
finding out which are the top level packages and which packages do
they depend on requires some effort. It can also be tedious to resolve
conflicting dependencies because ``pip`` doesn't yet have true
dependency resolution (more on this later). This utility tries to
solve these problem.

To some extent, this tool is inspired by ``lein deps :tree`` command
of `Leiningen <http://leiningen.org/>`_.


Installation
------------

.. code-block:: bash

    $ pip install pipdeptree


Usage and examples
------------------

To give you a brief idea, here is the output of ``pipdeptree``
compared with ``pip freeze``:

.. code-block:: bash

    $ pip freeze
    Flask==0.10.1
    Flask-Script==0.6.6
    Jinja2==2.7.2
    -e git+git@github.com:naiquevin/lookupy.git@cdbe30c160e1c29802df75e145ea4ad903c05386#egg=Lookupy-master
    Mako==0.9.1
    MarkupSafe==0.18
    SQLAlchemy==0.9.1
    Werkzeug==0.9.4
    alembic==0.6.2
    argparse==1.2.1
    ipython==2.0.0
    itsdangerous==0.23
    psycopg2==2.5.2
    redis==2.9.1
    slugify==0.0.1
    wsgiref==0.1.2

And now see what ``pipdeptree`` outputs,

.. code-block:: bash

    $ pipdeptree
    Warning!!! Possible confusing dependencies found:
    * Mako==0.9.1 -> MarkupSafe [required: >=0.9.2, installed: 0.18]
      Jinja2==2.7.2 -> MarkupSafe [installed: 0.18]
    ------------------------------------------------------------------------
    Lookupy==0.1
    wsgiref==0.1.2
    argparse==1.2.1
    psycopg2==2.5.2
    Flask-Script==0.6.6
      - Flask [installed: 0.10.1]
        - Werkzeug [required: >=0.7, installed: 0.9.4]
        - Jinja2 [required: >=2.4, installed: 2.7.2]
          - MarkupSafe [installed: 0.18]
        - itsdangerous [required: >=0.21, installed: 0.23]
    alembic==0.6.2
      - SQLAlchemy [required: >=0.7.3, installed: 0.9.1]
      - Mako [installed: 0.9.1]
        - MarkupSafe [required: >=0.9.2, installed: 0.18]
    ipython==2.0.0
    slugify==0.0.1
    redis==2.9.1


What's with the warning about confusing dependencies?
-----------------------------------------------------

As seen in the above output, ``pipdeptree`` by default warns about
possible confusing dependencies. Any package that's specified as a
dependency of multiple packages with a different version is considered
as a possible confusing dependency. This is helpful because ``pip``
`doesn't have true dependency resolution
<https://github.com/pypa/pip/issues/988>`_ yet. The warning is printed
to stderr instead of stdout and it can be completely disabled by using
the ``--nowarn`` flag.


Warnings about circular dependencies
------------------------------------

In case any of the packages have circular dependencies (eg. package A
depending upon package B and package B depending upon package A), then
``pipdeptree`` will print warnings about that as well.

.. code-block:: bash

    $ pipdeptree
    Warning!!! Cyclic dependencies found:
    - CircularDependencyA => CircularDependencyB => CircularDependencyA
    - CircularDependencyB => CircularDependencyA => CircularDependencyB
    ------------------------------------------------------------------------
    wsgiref==0.1.2
    argparse==1.2.1

As with the confusing dependencies warnings, these are printed to
stderr and can be disabled using the ``--nowarn`` flag.


Using pipdeptree to write requirements.txt file
-----------------------------------------------

If you wish to track only the top level packages in your
``requirements.txt`` file, it's possible to do so using ``pipdeptree``
by grep-ing only the top-level lines from the output,

.. code-block:: bash

    $ pipdeptree | grep -P '^\w+'
    Lookupy==0.1
    wsgiref==0.1.2
    argparse==1.2.1
    psycopg2==2.5.2
    Flask-Script==0.6.6
    alembic==0.6.2
    ipython==2.0.0
    slugify==0.0.1
    redis==2.9.1

There is a problem here though. The output doesn't mention anything
about ``Lookupy`` being installed as an editable package (refer to the
output of ``pip freeze`` above) and information about it's source is
lost. To fix this, ``pipdeptree`` must be run with a ``-f`` or
``--freeze`` flag.

.. code-block:: bash

    $ pipdeptree -f --nowarn | grep -P '^[\w0-9\-=.]+'
    -e git+git@github.com:naiquevin/lookupy.git@cdbe30c160e1c29802df75e145ea4ad903c05386#egg=Lookupy-master
    wsgiref==0.1.2
    argparse==1.2.1
    psycopg2==2.5.2
    Flask-Script==0.6.6
    alembic==0.6.2
    ipython==2.0.0
    slugify==0.0.1
    redis==2.9.1

    $ pipdeptree -f --nowarn | grep -P '^[\w0-9\-=.]+' > requirements.txt


Usage
-----

.. code-block:: bash

    usage: pipdeptree.py [-h] [-f] [-a] [-l] [-w]

    Dependency tree of the installed python packages

    optional arguments:
      -h, --help        show this help message and exit
      -f, --freeze      Print names so as to write freeze files
      -a, --all         list all deps at top level
      -l, --local-only  If in a virtualenv that has global access donot show
                        globally installed packages
      -w, --nowarn      Inhibit warnings about possibly confusing packages


Known Issues
------------

* To work with packages installed inside a virtualenv, pipdeptree also
  needs to be installed in the same virtualenv even if it's already
  installed globally.

* One thing you might have noticed already is that ``flask`` is shown
  as a dependency of ``flask-script``, which although correct, sounds
  a bit odd. ``flask-script`` is being used here *because* we are
  using ``flask`` and not the other way around. Same with
  ``sqlalchemy`` and ``alembic``.  I haven't yet thought about a
  possible solution to this!  (May be if libs that are "extensions"
  could be distinguished from the ones that are
  "dependencies". Suggestions are welcome.)


Runnings Tests (for contributors)
---------------------------------

Tests require some dummy virtualenvs to be created. If you run them
using `tox <http://tox.readthedocs.org/en/latest/>`_, then that will
take care of creating the virtualenvs, so it's recommended that you
run the tests using ``tox`` for the first time.

.. code-block:: bash

    $ pip install tox
    $ tox

Thereafter, you may use either `pytest <http://pytest.org/latest/>`_
or `nose <https://nose.readthedocs.org/en/latest/>`_ to run them.

However, before pushing the code or sending pull requests it's
recommended to run ``tox`` once so that tests are run on all
environments.


License
-------

MIT (See LICENSE)
