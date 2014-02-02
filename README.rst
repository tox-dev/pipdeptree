pipdeptree
==========

`pipdeptree` is a command line utility to show the installed python
packages as a dependency tree. It works pretty much like `pip
freeze`. Since `pip freeze` shows all dependencies as a flat list,
finding out which are the top level packages and which packages do
they depend on requires some effort. This utility tries to solve this
problem.

To give you a brief idea here is the output of `pipdeptree` compared
to `pip freeze`

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

.. code-block:: bash

    $ python pipdeptree.py
    wsgiref==0.1.2
    argparse==1.2.1
    psycopg2==2.5.2
    flask-script==0.6.6
      - flask [installed: 0.10.1]
        - werkzeug [required: >=0.7, installed: 0.9.4]
        - jinja2 [required: >=2.4, installed: 2.7.2]
          - markupsafe [installed: 0.18]
        - itsdangerous [required: >=0.21, installed: 0.23]
    alembic==0.6.2
      - sqlalchemy [required: >=0.7.3, installed: 0.9.1]
      - mako [installed: 0.9.1]
        - markupsafe [required: >=0.9.2, installed: 0.18]
    slugify==0.0.1
    redis==2.9.1


Installation
------------

This library is still being worked upon and hence, yet to be published
on pypi


Usage
-----

:todo


License
-------

MIT
