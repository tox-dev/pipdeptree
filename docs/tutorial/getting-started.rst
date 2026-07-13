Getting started
===============

Installation
------------

.. tab:: uv

    .. code-block:: bash

        uv tool install pipdeptree

.. tab:: pipx

    .. code-block:: bash

        pipx install pipdeptree

.. tab:: pip

    .. code-block:: bash

        pip install pipdeptree

pipdeptree includes rich output and Graphviz DOT source. Binary Graphviz formats require the ``dot`` executable.

First run
---------

Run ``pipdeptree`` with no arguments to see the full dependency tree of your environment:

.. doctest::

    >>> print(run_pipdeptree(), end="")
    covdefaults==2.3.0
    └── coverage [required: >=6.0.2, installed: 7.15.1]
    diff_cover==10.3.0
    ├── chardet [required: >=3.0.0, installed: 7.4.3]
    ├── Jinja2 [required: >=2.7.1, installed: 3.1.6]
    │   └── MarkupSafe [required: >=2.0, installed: 3.0.3]
    ├── pluggy [required: >=0.13.1,<2, installed: 1.6.0]
    └── Pygments [required: >=2.19.1,<3.0.0, installed: 2.20.0]
    pipdeptree==4.0.0
    ├── nab-index [required: >=0.0.8, installed: 0.0.8]
    │   ├── packaging [required: >=24.0, installed: 26.2]
    │   ├── truststore [required: >=0.10, installed: 0.10.4]
    │   ├── typing_extensions [required: >=4.6, installed: 4.16.0]
    │   └── urllib3 [required: >=2.0, installed: 2.7.0]
    └── nab-python [required: >=0.0.8, installed: 0.0.8]
        ├── build [required: >=1.2, installed: 1.5.1]
        │   ├── packaging [required: >=24.0, installed: 26.2]
        │   └── pyproject_hooks [required: Any, installed: 1.2.0]
        ├── installer [required: >=0.7, installed: 1.0.1]
        ├── nab-index [required: ==0.0.8, installed: 0.0.8]
        │   ├── packaging [required: >=24.0, installed: 26.2]
        │   ├── truststore [required: >=0.10, installed: 0.10.4]
        │   ├── typing_extensions [required: >=4.6, installed: 4.16.0]
        │   └── urllib3 [required: >=2.0, installed: 2.7.0]
        ├── nab-resolver [required: ==0.0.8, installed: 0.0.8]
        │   └── typing_extensions [required: >=4.6, installed: 4.16.0]
        ├── pyproject_hooks [required: >=1.2, installed: 1.2.0]
        ├── tomli [required: >=2.0, installed: 2.4.1]
        ├── tomli_w [required: >=1.2, installed: 1.2.0]
        └── typing_extensions [required: >=4.6, installed: 4.16.0]
    pytest-cov==7.1.0
    ├── coverage [required: >=7.10.6, installed: 7.15.1]
    ├── pluggy [required: >=1.2, installed: 1.6.0]
    └── pytest [required: >=7, installed: 9.1.1]
        ├── iniconfig [required: >=1.0.1, installed: 2.3.0]
        ├── packaging [required: >=22, installed: 26.2]
        ├── pluggy [required: >=1.5,<2, installed: 1.6.0]
        └── Pygments [required: >=2.7.2, installed: 2.20.0]

Each top-level entry is a package with no parent depending on it. Indented lines show dependencies, with the required
version range and the installed version.

Understanding the output
------------------------

The top-level line contains the package name and version, such as ``pytest-cov==7.1.0``. Tree-drawing characters indent
its dependencies. ``[required: >=7, installed: 9.1.1]`` gives the parent's constraint and the installed version.

A dependency appears multiple times when several packages require it, as with ``pluggy`` above. pipdeptree warns when
their version requirements conflict.

The dependency graph for the above output looks like this:

.. mermaid::

    flowchart TD
        pytest-cov["pytest-cov<br/>7.1.0"]:::top --> coverage["coverage<br/>7.15.1"]:::dep
        pytest-cov --> pluggy["pluggy<br/>1.6.0"]:::shared
        pytest-cov --> pytest["pytest<br/>9.1.1"]:::dep
        pytest --> iniconfig["iniconfig<br/>2.3.0"]:::dep
        pytest --> packaging["packaging<br/>26.2"]:::shared
        pytest --> pluggy
        pytest --> pygments["Pygments<br/>2.20.0"]:::shared
        covdefaults["covdefaults<br/>2.3.0"]:::top --> coverage
        diff_cover["diff_cover<br/>10.3.0"]:::top --> jinja2["Jinja2<br/>3.1.6"]:::dep
        diff_cover --> pygments
        diff_cover --> chardet["chardet<br/>7.4.3"]:::dep
        diff_cover --> pluggy
        jinja2 --> markupsafe["MarkupSafe<br/>3.0.3"]:::dep
        classDef top fill:#2980b9,color:#fff
        classDef dep fill:#27ae60,color:#fff
        classDef shared fill:#8e44ad,color:#fff

Common operations
-----------------

Filter to a specific package:

.. doctest::

    >>> print(run_pipdeptree("--packages", "pytest"), end="")
    pytest==9.1.1
    ├── iniconfig [required: >=1.0.1, installed: 2.3.0]
    ├── packaging [required: >=22, installed: 26.2]
    ├── pluggy [required: >=1.5,<2, installed: 1.6.0]
    └── Pygments [required: >=2.7.2, installed: 2.20.0]

Find the packages that require a dependency with a reverse tree:

.. doctest::

    >>> print(run_pipdeptree("--reverse", "--packages", "pygments"), end="")
    Pygments==2.20.0
    ├── diff_cover==10.3.0 [requires: pygments>=2.19.1,<3.0.0]
    └── pytest==9.1.1 [requires: pygments>=2.7.2]
        └── pytest-cov==7.1.0 [requires: pytest>=7]

Limit the tree depth:

.. doctest::

    >>> print(run_pipdeptree("--depth", "1"), end="")
    covdefaults==2.3.0
    └── coverage [required: >=6.0.2, installed: 7.15.1]
    diff_cover==10.3.0
    ├── chardet [required: >=3.0.0, installed: 7.4.3]
    ├── Jinja2 [required: >=2.7.1, installed: 3.1.6]
    ├── pluggy [required: >=0.13.1,<2, installed: 1.6.0]
    └── Pygments [required: >=2.19.1,<3.0.0, installed: 2.20.0]
    pipdeptree==4.0.0
    ├── nab-index [required: >=0.0.8, installed: 0.0.8]
    └── nab-python [required: >=0.0.8, installed: 0.0.8]
    pytest-cov==7.1.0
    ├── coverage [required: >=7.10.6, installed: 7.15.1]
    ├── pluggy [required: >=1.2, installed: 1.6.0]
    └── pytest [required: >=7, installed: 9.1.1]

Report environment health with ``--summary``:

.. code-block:: console

    $ pipdeptree --packages pytest --summary
    total packages:           5
    direct dependencies:      1
    transitive dependencies:  4
    max depth:                2
    cyclic dependencies:      0
    missing dependencies:     0
    conflicting dependencies: 0 (0 edges)
    licenses:                 (Apache-2.0 OR BSD-2-Clause): 1, (BSD-2-Clause): 1, (MIT License): 1, (MIT): 2
    unknown licenses:         0
    copyleft licenses:        no
    min requires-python:      3.10
    total size:               6.0 MB

Drop ``--packages`` to report on the whole environment. Add ``-o rich`` for a styled table, or ``-o json`` for a
machine-readable version to gate CI on. The programmatic ``pipdeptree.render(summary=True)`` returns the same report
and displays as an HTML table in a notebook. See :doc:`/how-to/output-formats` for the full field list.

Preview a tree before installing
--------------------------------

The ``from-index`` subcommand shows the tree a package would install. It queries PyPI instead of inspecting your
environment.

Ask what ``starlette`` brings along:

.. code-block:: console

    $ pipdeptree from-index "starlette"
    starlette==1.2.1
    ├── anyio [candidate: 4.13.0]
    │   ├── idna [candidate: 3.17]
    │   └── typing-extensions [candidate: 4.15.0]
    └── typing-extensions [candidate: 4.15.0]

Read this the same way as the tree from your environment. The top line is the requirement you asked for and the
indented lines are its dependencies. Each edge shows the candidate version the resolver selected from PyPI:
the resolver does not install packages. It produces one version per package without a requirement range, so the edges
read ``[candidate: <version>]`` instead of the ``[required: ..., installed: ...]`` pair from an installed environment.

The positional argument is a PEP 508 requirement, the same string you would pass to ``pip install``, so you can
pin or bound it. Bound ``fastapi`` and resolve it alongside ``starlette``; the resolver selects the upper bound:

.. code-block:: console

    $ pipdeptree from-index "fastapi<=0.115.2" starlette
    fastapi==0.115.2
    ├── pydantic [candidate: 2.13.4]
    │   ├── annotated-types [candidate: 0.7.0]
    │   ├── pydantic-core [candidate: 2.46.4]
    │   │   └── typing-extensions [candidate: 4.15.0]
    │   ├── typing-extensions [candidate: 4.15.0]
    │   └── typing-inspection [candidate: 0.4.2]
    │       └── typing-extensions [candidate: 4.15.0]
    ├── starlette [candidate: 0.40.0]
    │   └── anyio [candidate: 4.13.0]
    │       ├── idna [candidate: 3.17]
    │       └── typing-extensions [candidate: 4.15.0]
    └── typing-extensions [candidate: 4.15.0]

The resolver selects ``0.115.2`` for the top-level package and follows its dependencies. You can resolve a
``pyproject.toml`` with ``--pyproject`` or a requirements file with ``--requirements``. The resolver reads metadata
from local checkouts and pinned git requirements. See :doc:`/how-to/usage` for these sources, render flags and rejected
inputs.

Render a lock file
------------------

For an existing `PEP 751 <https://peps.python.org/pep-0751/>`_ lock file (a ``pylock.toml``, such as the one :pypi:`uv`
exports), point ``from-lock`` at it to read its tree:

.. code-block:: console

    $ pipdeptree from-lock pylock.toml
    build==1.5.0
    ├── packaging [candidate: 26.2]
    └── pyproject-hooks [candidate: 1.2.0]

The lock lists the package names, versions and edges, so ``from-lock`` runs offline with no install or network.
The filtering and output flags you used above work here too. See :doc:`/how-to/usage` for the full set.

Next steps
----------

:doc:`/how-to/usage` covers filtering, virtual environments, warnings and extras. :doc:`/how-to/output-formats` covers
JSON, Mermaid and Graphviz. :doc:`/explanation` describes how pipdeptree decides when an optional dependency edge is
"active".
