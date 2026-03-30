Usage patterns
==============

Running in virtualenvs
----------------------

If pipdeptree is installed globally but you want to inspect a virtualenv, use ``--python``:

.. code-block:: console

    $ pipdeptree --python /path/to/venv/bin/python
    covdefaults==2.3.0
    └── coverage [required: >=6.0.2, installed: 7.13.5]
    ...

As of version 2.21.0, you can use ``--python auto`` to auto-detect the active virtualenv:

.. code-block:: console

    $ pipdeptree --python auto
    covdefaults==2.3.0
    └── coverage [required: >=6.0.2, installed: 7.13.5]
    ...

Alternatively, install pipdeptree inside the virtualenv and run it directly.

Filtering packages
------------------

By default, pipdeptree shows the full dependency tree of your environment:

.. code-block:: console

    $ pipdeptree
    covdefaults==2.3.0
    └── coverage [required: >=6.0.2, installed: 7.13.5]
    diff_cover==10.2.0
    ├── Jinja2 [required: >=2.7.1, installed: 3.1.6]
    │   └── MarkupSafe [required: >=2.0, installed: 3.0.3]
    ├── Pygments [required: >=2.19.1,<3.0.0, installed: 2.19.2]
    ├── chardet [required: >=3.0.0, installed: 7.1.0]
    └── pluggy [required: >=0.13.1,<2, installed: 1.6.0]
    graphviz==0.21
    pipdeptree==2.33.0
    └── packaging [required: >=26, installed: 26.0]
    pytest-cov==7.0.0
    ├── coverage [required: >=7.10.6, installed: 7.13.5]
    ├── pluggy [required: >=1.2, installed: 1.6.0]
    └── pytest [required: >=7, installed: 9.0.2]
        ├── iniconfig [required: >=1.0.1, installed: 2.3.0]
        ├── packaging [required: >=22, installed: 26.0]
        ├── pluggy [required: >=1.5,<2, installed: 1.6.0]
        └── Pygments [required: >=2.7.2, installed: 2.19.2]
    ...

Show only specific packages with ``--packages`` (``-p``):

.. code-block:: console

    $ pipdeptree --packages pytest
    pytest==9.0.2
    ├── iniconfig [required: >=1.0.1, installed: 2.3.0]
    ├── packaging [required: >=22, installed: 26.0]
    ├── pluggy [required: >=1.5,<2, installed: 1.6.0]
    └── Pygments [required: >=2.7.2, installed: 2.19.2]

Multiple packages can be comma-separated, and wildcards are supported:

.. code-block:: console

    $ pipdeptree --packages "pytest*"
    pytest-cov==7.0.0
    ├── coverage [required: >=7.10.6, installed: 7.13.5]
    ├── pluggy [required: >=1.2, installed: 1.6.0]
    └── pytest [required: >=7, installed: 9.0.2]
        ├── iniconfig [required: >=1.0.1, installed: 2.3.0]
        ├── packaging [required: >=22, installed: 26.0]
        ├── pluggy [required: >=1.5,<2, installed: 1.6.0]
        └── Pygments [required: >=2.7.2, installed: 2.19.2]
    pytest-mock==3.15.1
    └── pytest [required: >=6.2.5, installed: 9.0.2]
        ├── iniconfig [required: >=1.0.1, installed: 2.3.0]
        ├── packaging [required: >=22, installed: 26.0]
        ├── pluggy [required: >=1.5,<2, installed: 1.6.0]
        └── Pygments [required: >=2.7.2, installed: 2.19.2]
    pytest-subprocess==1.5.3
    └── pytest [required: >=4.0.0, installed: 9.0.2]
        ├── iniconfig [required: >=1.0.1, installed: 2.3.0]
        ├── packaging [required: >=22, installed: 26.0]
        ├── pluggy [required: >=1.5,<2, installed: 1.6.0]
        └── Pygments [required: >=2.7.2, installed: 2.19.2]

Excluding packages
------------------

Use ``--exclude`` (``-e``) to hide specific packages:

.. code-block:: console

    $ pipdeptree --exclude pip,pipdeptree,setuptools,wheel
    covdefaults==2.3.0
    └── coverage [required: >=6.0.2, installed: 7.13.5]
    diff_cover==10.2.0
    ├── Jinja2 [required: >=2.7.1, installed: 3.1.6]
    │   └── MarkupSafe [required: >=2.0, installed: 3.0.3]
    ├── Pygments [required: >=2.19.1,<3.0.0, installed: 2.19.2]
    ├── chardet [required: >=3.0.0, installed: 7.1.0]
    └── pluggy [required: >=0.13.1,<2, installed: 1.6.0]
    graphviz==0.21
    pytest-cov==7.0.0
    ├── coverage [required: >=7.10.6, installed: 7.13.5]
    ├── pluggy [required: >=1.2, installed: 1.6.0]
    └── pytest [required: >=7, installed: 9.0.2]
        ├── iniconfig [required: >=1.0.1, installed: 2.3.0]
        ├── packaging [required: >=22, installed: 26.0]
        ├── pluggy [required: >=1.5,<2, installed: 1.6.0]
        └── Pygments [required: >=2.7.2, installed: 2.19.2]
    ...

Add ``--exclude-dependencies`` to also hide their transitive dependencies:

.. code-block:: console

    $ pipdeptree --exclude pipdeptree --exclude-dependencies
    covdefaults==2.3.0
    └── coverage [required: >=6.0.2, installed: 7.13.5]
    diff_cover==10.2.0
    ├── Jinja2 [required: >=2.7.1, installed: 3.1.6]
    │   └── MarkupSafe [required: >=2.0, installed: 3.0.3]
    ├── Pygments [required: >=2.19.1,<3.0.0, installed: 2.19.2]
    ├── chardet [required: >=3.0.0, installed: 7.1.0]
    └── pluggy [required: >=0.13.1,<2, installed: 1.6.0]
    graphviz==0.21
    pytest-cov==7.0.0
    ├── coverage [required: >=7.10.6, installed: 7.13.5]
    ├── pluggy [required: >=1.2, installed: 1.6.0]
    └── pytest [required: >=7, installed: 9.0.2]
        ├── iniconfig [required: >=1.0.1, installed: 2.3.0]
        ├── pluggy [required: >=1.5,<2, installed: 1.6.0]
        └── Pygments [required: >=2.7.2, installed: 2.19.2]
    ...

Note that ``packaging`` no longer appears under ``pytest`` because it was excluded as a transitive dependency of
``pipdeptree``.

Reverse dependency lookup
-------------------------

Use ``--reverse`` (``-r``) with ``--packages`` to find out why a package is installed:

.. code-block:: console

    $ pipdeptree --reverse --packages pygments
    Pygments==2.19.2
    ├── rich==14.3.3 [requires: Pygments>=2.13.0,<3.0.0]
    ├── diff_cover==10.2.0 [requires: Pygments>=2.19.1,<3.0.0]
    └── pytest==9.0.2 [requires: Pygments>=2.7.2]
        ├── pytest-mock==3.15.1 [requires: pytest>=6.2.5]
        ├── pytest-subprocess==1.5.3 [requires: pytest>=4.0.0]
        └── pytest-cov==7.0.0 [requires: pytest>=7]

Writing requirements files
--------------------------

Extract top-level packages from the tree output:

.. code-block:: console

    $ pipdeptree --warn silence | grep -E '^\w+'
    covdefaults==2.3.0
    diff_cover==10.2.0
    graphviz==0.21
    pipdeptree==2.33.0
    pytest-cov==7.0.0
    pytest-mock==3.15.1
    pytest-subprocess==1.5.3
    rich==14.3.3
    virtualenv==20.39.1

Or use freeze format for pip-compatible output:

.. code-block:: console

    $ pipdeptree -o freeze --warn silence | grep -E '^[a-zA-Z0-9\-]+' > requirements.txt

The freeze output can also serve as a human-readable lock file with indented dependencies:

.. code-block:: console

    $ pipdeptree --packages pytest -o freeze
    pytest==9.0.2
      iniconfig==2.3.0
      packaging==26.0
      pluggy==1.6.0
      Pygments==2.19.2

Warning control
---------------

pipdeptree warns about conflicting and circular dependencies on stderr. Control this with ``-w``:

- ``-w suppress`` (default) -- show warnings, exit 0.
- ``-w silence`` -- hide warnings, exit 0.
- ``-w fail`` -- show warnings, exit 1 if any found (useful in CI).

.. code-block:: console

    $ pipdeptree -w fail
    $ echo $?
    0

When conflicts exist, the output includes warnings and a non-zero exit code:

.. code-block:: console

    $ pipdeptree -w fail
    Warning!!! Possibly conflicting dependencies found:
    * Jinja2==2.11.2
     - MarkupSafe [required: >=0.23, installed: 0.22]
    $ echo $?
    1

Depth limiting
--------------

Limit how deep the tree renders with ``-d``:

.. code-block:: console

    $ pipdeptree -d 1 --packages pytest-cov,rich
    pytest-cov==7.0.0
    ├── coverage [required: >=7.10.6, installed: 7.13.5]
    ├── pluggy [required: >=1.2, installed: 1.6.0]
    └── pytest [required: >=7, installed: 9.0.2]
    rich==14.3.3
    ├── markdown-it-py [required: >=2.2.0, installed: 4.0.0]
    └── Pygments [required: >=2.13.0,<3.0.0, installed: 2.19.2]

Use ``-d 0`` to show only top-level packages with no dependencies:

.. code-block:: console

    $ pipdeptree -d 0 --packages pytest-cov,rich
    pytest-cov==7.0.0
    rich==14.3.3

Package metadata
----------------

Display metadata fields from the package's ``METADATA`` file with ``--metadata`` (``-m``). Pass a comma-separated list
of field names. Metadata is shown on every package in the tree in brackets:

.. code-block:: console

    $ pipdeptree --metadata license --packages rich
    rich==14.3.3 [MIT License]
    ├── markdown-it-py [required: >=2.2.0, installed: 4.0.0] [MIT License]
    │   └── mdurl [required: ~=0.1, installed: 0.1.2] [MIT License]
    └── Pygments [required: >=2.13.0,<3.0.0, installed: 2.19.2] [BSD License]

Multiple fields can be combined:

.. code-block:: console

    $ pipdeptree --metadata license,summary --packages rich -d 0
    rich==14.3.3 [MIT License, Render rich text, tables, progress bars, syntax highlighting, markdown and more to the terminal]

Common metadata fields: ``license``, ``summary``, ``author``, ``author-email``, ``home-page``, ``requires-python``.
Any field from the package's ``METADATA`` file is accepted.

.. note::

   The ``--license`` flag still works for backwards compatibility but is deprecated. Use ``--metadata license``
   instead.

Computed fields
---------------

Display computed package information with ``--computed`` (``-c``):

- ``size`` -- installed size on disk (human-readable)
- ``size-raw`` -- installed size in bytes (integer, useful for JSON output)
- ``unique-deps-count`` -- number of dependencies exclusive to this package (hidden when 0)
- ``unique-deps-names`` -- names of dependencies exclusive to this package (hidden when empty)
- ``unique-deps-size`` -- total installed size of exclusive dependencies (hidden when 0)

Unique dependencies are transitive: if removing a package would orphan a dependency, and that orphaned dependency
would in turn orphan its own dependencies, all of them are counted.

.. code-block:: console

    $ pipdeptree --computed size --packages rich -d 0
    rich==14.3.3 [1.2 MB]

.. code-block:: console

    $ pipdeptree --computed unique-deps-count,unique-deps-names,unique-deps-size --packages rich
    rich==14.3.3 [2 unique deps, unique: markdown-it-py, mdurl, unique size: 248.2 KB]
    ├── markdown-it-py [required: >=2.2.0, installed: 4.0.0] [1 unique deps, unique: mdurl, unique size: 22.9 KB]
    │   └── mdurl [required: ~=0.1, installed: 0.1.2]
    └── Pygments [required: >=2.13.0,<3.0.0, installed: 2.19.2]

Both ``--metadata`` and ``--computed`` can be combined and work with all output formats. In JSON output, ``size_raw``
and ``unique_deps_count`` are native integers, ``unique_deps_names`` is a list of strings.

Including extras
----------------

Show optional (extras) dependencies in the tree with ``--extras`` (``-x``):

.. code-block:: console

    $ pipdeptree --extras --packages pytest
    pytest==9.0.2
    ├── iniconfig [required: >=1.0.1, installed: 2.3.0]
    ├── packaging [required: >=22, installed: 26.0]
    ├── pluggy [required: >=1.5,<2, installed: 1.6.0]
    └── Pygments [required: >=2.7.2, installed: 2.19.2]

Without ``--extras``, only mandatory dependencies are shown. Packages that declare optional dependency groups (extras)
will have those additional dependencies included when this flag is set.
