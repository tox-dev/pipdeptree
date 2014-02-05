pipdeptree
==========

``pipdeptree`` is a command line utility for displaying the python
packages installed in an environment in form of a dependency
tree. Since ``pip freeze`` shows all dependencies as a flat list,
finding out which are the top level packages and which packages do
they depend on requires some effort. This utility tries to solve this
problem.


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
    Mako==0.9.1
    MarkupSafe==0.18
    SQLAlchemy==0.9.1
    Werkzeug==0.9.4
    alembic==0.6.2
    argparse==1.2.1
    itsdangerous==0.23
    psycopg2==2.5.2
    redis==2.9.1
    slugify==0.0.1
    wsgiref==0.1.2

And now see what ``pipdeptree`` outputs,

.. code-block:: bash

    $ pipdeptree
    wsgiref==0.1.2
    argparse==1.2.1
    psycopg2==2.5.2
    Flask-Script==0.6.6
      - Flask [installed: 0.10.1]
        - Werkzeug [required: >=0.7, installed: 0.9.4]
        - Jinja2 [required: >=2.4, installed: 2.7.2]
          - markupsafe [installed: 0.18]
        - itsdangerous [required: >=0.21, installed: 0.23]
    alembic==0.6.2
      - SQLAlchemy [required: >=0.7.3, installed: 0.9.1]
      - Mako [installed: 0.9.1]
        - MarkupSafe [required: >=0.9.2, installed: 0.18]
    slugify==0.0.1
    redis==2.9.1


If you wish to track only the top level packages in your
``requirements.txt`` file, you could use grep as follows,

.. code-block:: bash

    $ pipdeptree | grep -P '^[\w0-9\-=.]+'
    wsgiref==0.1.2
    argparse==1.2.1
    psycopg2==2.5.2
    Flask-Script==0.6.6
    alembic==0.6.2
    slugify==0.0.1
    redis==2.9.1
    
    $ pipdeptree | grep -P '^[\w0-9\-=.]+' > requirements.txt


Usage
-----

.. code-block:: bash

    $ pipdeptree -h
    usage: pipdeptree [-h] [-a] [-l]

    Dependency tree of the installed python packages

    optional arguments:
      -h, --help        show this help message and exit
      -a, --all         list all deps at top level
      -l, --local-only  list only the installations local to the current
                        virtualenv, if in a virtualenv


Known Issues
------------

One thing you might have noticed already is that ``flask`` is shown as
a dependency of ``flask-script``, which although correct, sounds a bit
odd. ``flask-script`` is being used here *because* we are using
``flask`` and not the other way around. Same with ``sqlalchemy`` and
``alembic``.  I haven't yet thought about a possible solution to this!
(May be if libs that are "extensions" could be distinguished from the
ones that are "dependencies". Suggestions are welcome.)


License
-------

MIT (See LICENSE)
