pipdeptree
==========

.. image:: https://travis-ci.org/naiquevin/pipdeptree.svg?branch=master
   :target: https://travis-ci.org/naiquevin/pipdeptree


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
    Warning!!! Possible conflicting dependencies found:
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


Is it possible to find out why a particular package is installed?
-----------------------------------------------------------------

`New in ver. 0.5.0`

Yes, there's a `--reverse` (or simply `-r`) flag for this. To find out
what all packages require paricular package(s), it can be combined
with `--packages` flag as follows:

.. code-block:: bash

    $ python pipdeptree.py --reverse --packages itsdangerous,gnureadline --nowarn
    gnureadline==6.3.3
      - ipython==2.0.0 [requires: gnureadline]
    itsdangerous==0.24
      - Flask==0.10.1 [requires: itsdangerous>=0.21]
        - Flask-Script==0.6.6 [requires: Flask]


What's with the warning about conflicting dependencies?
-------------------------------------------------------

As seen in the above output, ``pipdeptree`` by default warns about
possible conflicting dependencies. Any package that's specified as a
dependency of multiple packages with a different version is considered
as a possible conflicting dependency. This is helpful because ``pip``
`doesn't have true dependency resolution
<https://github.com/pypa/pip/issues/988>`_ yet. The warning is printed
to stderr instead of stdout and it can be completely silenced by using
the ``-w silence`` or ``--warn silence`` flag. On the other hand, it
can be made mode strict with ``--warn fail`` in which case the command
will not only print the warnings to stderr but also exit with a
non-zero status code. This could be useful if you want to fit this
tool into your CI pipeline.

**Note** The ``--warn`` flag was added in version 0.6.0. If you are
using an older version, use ``--nowarn`` flag.


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

As with the conflicting dependencies warnings, these are printed to
stderr and can be controlled using the ``--warn`` flag.


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

The freeze flag will also not output the hyphens for child
dependencies, so you could dump the complete output of ``pipdeptree
-f`` to the requirements.txt file making the file human-friendly (due
to indentations) as well as pip-friendly. (Take care of duplicate
dependencies though)


Using pipdeptree with external tools
------------------------------------

`New in ver. 0.5.0`

It's also possible to have pipdeptree output json representation of
the dependency tree so that it may be used as input to other external
tools.

.. code-block:: bash

    $ python pipdeptree.py --json


Usage
-----

.. code-block:: bash

     usage: pipdeptree.py [-h] [-f] [-a] [-l] [-w [{silence,suppress,fail}]] [-r]
                          [-p PACKAGES] [-j]

     Dependency tree of the installed python packages

     optional arguments:
       -h, --help            show this help message and exit
       -f, --freeze          Print names so as to write freeze files
       -a, --all             list all deps at top level
       -l, --local-only      If in a virtualenv that has global access do not show
                             globally installed packages
       -w [{silence,suppress,fail}], --warn [{silence,suppress,fail}]
                             Warning control. "suppress" will show warnings but
                             return 0 whether or not they are present. "silence"
                             will not show warnings at all and always return 0.
                             "fail" will show warnings and return 1 if any are
                             present. The default is "suppress".
       -r, --reverse         Shows the dependency tree in the reverse fashion ie.
                             the sub-dependencies are listed with the list of
                             packages that need them under them.
       -p PACKAGES, --packages PACKAGES
                             Comma separated list of select packages to show in the
                             output. If set, --all will be ignored.
       -j, --json            Display dependency tree as json. This will yield "raw"
                             output that may be used by external tools. This option
                             overrides all other options.


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

Tests can be run against all version of python using `tox
<http://tox.readthedocs.org/en/latest/>`_ as follows:

.. code-block:: bash

    $ make test-tox

This assumes that you have python versions 2.6, 2.7, 3.2, 3.3 and 3.4
installed on your machine. (See more: tox.ini)

Or if you don't want to install all the versions of python but want to
run tests quickly against Python2.7 only:

.. code-block:: bash

    $ make test

Tests require some virtualenvs to be created, so another assumption is
that you have ``virtualenv`` installed.

Before pushing the code or sending pull requests it's recommended to
run ``make test-tox`` once so that tests are run on all environments.

(See more: Makefile)


License
-------

MIT (See LICENSE)
