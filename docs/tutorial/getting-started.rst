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

For enhanced terminal output with colors and checkmarks, install the ``rich`` extra:

.. code-block:: bash

    pip install pipdeptree[rich]

For Graphviz diagram generation, install the ``graphviz`` extra:

.. code-block:: bash

    pip install pipdeptree[graphviz]

First run
---------

Run ``pipdeptree`` with no arguments to see the full dependency tree of your environment:

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

Each top-level entry is a package with no parent depending on it. Indented lines show dependencies, with the required
version range and the actually installed version.

Understanding the output
------------------------

Each line shows:

- **Package name and version** -- the top-level line (e.g., ``pytest-cov==7.0.0``).
- **Dependencies** -- indented with tree-drawing characters.
- **Version constraints** -- ``[required: >=7, installed: 9.0.2]`` shows what the parent needs vs what's installed.

When a dependency appears multiple times (e.g., ``pluggy`` above), it means multiple packages depend on it. If their
version requirements conflict, pipdeptree will warn you.

The dependency graph for the above output looks like this:

.. mermaid::

    flowchart TD
        pytest-cov["pytest-cov<br/>7.0.0"]:::top --> coverage["coverage<br/>7.13.5"]:::dep
        pytest-cov --> pluggy["pluggy<br/>1.6.0"]:::shared
        pytest-cov --> pytest["pytest<br/>9.0.2"]:::dep
        pytest --> iniconfig["iniconfig<br/>2.3.0"]:::dep
        pytest --> packaging["packaging<br/>26.0"]:::shared
        pytest --> pluggy
        pytest --> pygments["Pygments<br/>2.19.2"]:::shared
        covdefaults["covdefaults<br/>2.3.0"]:::top --> coverage
        diff_cover["diff_cover<br/>10.2.0"]:::top --> jinja2["Jinja2<br/>3.1.6"]:::dep
        diff_cover --> pygments
        diff_cover --> chardet["chardet<br/>7.1.0"]:::dep
        diff_cover --> pluggy
        jinja2 --> markupsafe["MarkupSafe<br/>3.0.3"]:::dep
        classDef top fill:#2980b9,color:#fff
        classDef dep fill:#27ae60,color:#fff
        classDef shared fill:#8e44ad,color:#fff

Common operations
-----------------

Filter to a specific package:

.. code-block:: console

    $ pipdeptree --packages pytest
    pytest==9.0.2
    ├── iniconfig [required: >=1.0.1, installed: 2.3.0]
    ├── packaging [required: >=22, installed: 26.0]
    ├── pluggy [required: >=1.5,<2, installed: 1.6.0]
    └── Pygments [required: >=2.7.2, installed: 2.19.2]

Find out why a package is installed (reverse tree):

.. code-block:: console

    $ pipdeptree --reverse --packages pygments
    Pygments==2.19.2
    ├── rich==14.3.3 [requires: Pygments>=2.13.0,<3.0.0]
    ├── diff_cover==10.2.0 [requires: Pygments>=2.19.1,<3.0.0]
    └── pytest==9.0.2 [requires: Pygments>=2.7.2]
        ├── pytest-mock==3.15.1 [requires: pytest>=6.2.5]
        ├── pytest-subprocess==1.5.3 [requires: pytest>=4.0.0]
        └── pytest-cov==7.0.0 [requires: pytest>=7]

Limit the tree depth:

.. code-block:: console

    $ pipdeptree -d 1
    covdefaults==2.3.0
    └── coverage [required: >=6.0.2, installed: 7.13.5]
    diff_cover==10.2.0
    ├── Jinja2 [required: >=2.7.1, installed: 3.1.6]
    ├── Pygments [required: >=2.19.1,<3.0.0, installed: 2.19.2]
    ├── chardet [required: >=3.0.0, installed: 7.1.0]
    └── pluggy [required: >=0.13.1,<2, installed: 1.6.0]

Get an at-a-glance health report with ``--summary``:

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

So far you have looked at packages that are already installed. You can also peek at the tree a package *would*
pull in before you commit to installing it. This lives in the ``from-index`` subcommand, which queries PyPI
instead of inspecting your environment. It ships in an optional extra, so install that first:

.. code-block:: console

    $ pip install pipdeptree[index]

Now ask what ``starlette`` brings along:

.. code-block:: console

    $ pipdeptree from-index "starlette"
    starlette==1.2.1
    ├── anyio [candidate: 4.13.0]
    │   ├── idna [candidate: 3.17]
    │   └── typing-extensions [candidate: 4.15.0]
    └── typing-extensions [candidate: 4.15.0]

Read this the same way as the tree from your environment. The top line is the requirement you asked for and the
indented lines are its dependencies. Each edge shows the candidate version the resolver selected from PyPI:
nothing is installed and the resolver produces a single version per package without a requirement range, so the
edges read ``[candidate: <version>]`` rather than the ``[required: ..., installed: ...]`` pair you see for an
installed environment.

The positional argument is a PEP 508 requirement, the same string you would pass to ``pip install``, so you can
pin or bound it. Bound ``fastapi`` and resolve it alongside ``starlette`` -- the pin lands on the upper bound:

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

The constraint moves the top-level pin to ``0.115.2`` and the dependency picks follow from it. You can also resolve
a ``pyproject.toml`` with ``--pyproject`` or a requirements file with ``--requirements``, and even a local checkout
or a pinned git requirement, where the resolver reads the target's metadata. See :doc:`/how-to/usage` for those
sources, the render flags, and the inputs the resolver rejects.

Render a lock file
------------------

If you already have a `PEP 751 <https://peps.python.org/pep-0751/>`_ lock file (a ``pylock.toml``, such as the one
:pypi:`uv` exports), point ``from-lock`` at it to read its tree:

.. code-block:: console

    $ pipdeptree from-lock pylock.toml
    build==1.5.0
    ├── packaging [candidate: 26.2]
    └── pyproject-hooks [candidate: 1.2.0]

The lock already lists every package, version and edge, so ``from-lock`` runs offline with no install, no network
and no extra. The filtering and output flags you used above work here too. See :doc:`/how-to/usage` for the full
set.

Next steps
----------

See :doc:`/how-to/usage` for filtering, virtualenv support, warning control, and how to surface
optional (extras) dependencies. See :doc:`/how-to/output-formats` for all available output formats
including JSON, Mermaid, and Graphviz. See :doc:`/explanation` for how pipdeptree decides when an
optional dependency edge is "active".
