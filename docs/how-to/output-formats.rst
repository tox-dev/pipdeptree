Output formats
==============

pipdeptree supports multiple output formats via ``-o FMT`` (or ``--output FMT``). An interactive terminal defaults to
``rich``. Redirected output, ``TERM=dumb`` and ``NO_COLOR`` default to ``text``. The executable examples use
``--packages pytest`` to keep the output concise.

text
----

Unicode box-drawing tree:

.. doctest::

    >>> print(run_pipdeptree("--packages", "pytest", "-o", "text"), end="")
    pytest==9.1.1
    ├── iniconfig [required: >=1.0.1, installed: 2.3.0]
    ├── packaging [required: >=22, installed: 26.2]
    ├── pluggy [required: >=1.5,<2, installed: 1.6.0]
    └── Pygments [required: >=2.7.2, installed: 2.20.0]

rich
----

Rich output uses the terminal palette to separate fields. Warning colors do not mark normal package data.

.. list-table::
    :header-rows: 1

    * - Element
      - Style
    * - Package names
      - Bold cyan
    * - Versions and successful status markers
      - Bold green
    * - Version constraints
      - Bright blue
    * - Labels and tree guides
      - Dim
    * - Extras and metadata
      - Magenta
    * - Warnings
      - Yellow
    * - Errors
      - Red

.. doctest::

    >>> print(run_pipdeptree("--packages", "pytest", "-o", "rich"), end="")
    pytest==9.1.1
    ┣━━ ✓ iniconfig required: >=1.0.1 installed: 2.3.0
    ┣━━ ✓ packaging required: >=22 installed: 26.2
    ┣━━ ✓ pluggy required: >=1.5,<2 installed: 1.6.0
    ┗━━ ✓ Pygments required: >=2.7.2 installed: 2.20.0

freeze
------

Freeze emits pip-compatible requirements with indentation for the hierarchy:

.. doctest::

    >>> print(run_pipdeptree("--packages", "pytest", "-o", "freeze"), end="")
    pytest==9.1.1
      iniconfig==2.3.0
      packaging==26.2
      pluggy==1.6.0
      Pygments==2.20.0

json
----

JSON emits a flat array of package and dependency objects:

.. doctest::

    >>> print(run_pipdeptree("--packages", "pytest", "-o", "json"), end="")
    [
        {
            "package": {
                "key": "iniconfig",
                "package_name": "iniconfig",
                "installed_version": "2.3.0"
            },
            "dependencies": []
        },
        {
            "package": {
                "key": "packaging",
                "package_name": "packaging",
                "installed_version": "26.2"
            },
            "dependencies": []
        },
        {
            "package": {
                "key": "pluggy",
                "package_name": "pluggy",
                "installed_version": "1.6.0"
            },
            "dependencies": []
        },
        {
            "package": {
                "key": "pygments",
                "package_name": "Pygments",
                "installed_version": "2.20.0"
            },
            "dependencies": []
        },
        {
            "package": {
                "key": "pytest",
                "package_name": "pytest",
                "installed_version": "9.1.1"
            },
            "dependencies": [
                {
                    "key": "iniconfig",
                    "package_name": "iniconfig",
                    "installed_version": "2.3.0",
                    "required_version": ">=1.0.1"
                },
                {
                    "key": "packaging",
                    "package_name": "packaging",
                    "installed_version": "26.2",
                    "required_version": ">=22"
                },
                {
                    "key": "pluggy",
                    "package_name": "pluggy",
                    "installed_version": "1.6.0",
                    "required_version": ">=1.5,<2"
                },
                {
                    "key": "pygments",
                    "package_name": "Pygments",
                    "installed_version": "2.20.0",
                    "required_version": ">=2.7.2"
                }
            ]
        }
    ]

With ``--metadata`` or ``--computed``, package dictionaries include extra fields:

.. doctest::

    >>> print(
    ...     run_pipdeptree(
    ...         "--packages", "iniconfig", "-o", "json", "--metadata", "license", "--computed",
    ...         "size,unique-deps-count,unique-deps-names",
    ...     ),
    ...     end="",
    ... )
    [
        {
            "package": {
                "key": "iniconfig",
                "package_name": "iniconfig",
                "installed_version": "2.3.0",
                "metadata": {
                    "license": "N/A License"
                },
                "computed": {
                    "size": "0 B",
                    "unique_deps_count": 0,
                    "unique_deps_names": []
                }
            },
            "dependencies": []
        }
    ]

json-tree
---------

``json-tree`` nests package objects to match the text tree:

.. doctest::

    >>> print(run_pipdeptree("--packages", "pytest", "-o", "json-tree"), end="")
    [
        {
            "dependencies": [
                {
                    "dependencies": [],
                    "installed_version": "2.3.0",
                    "key": "iniconfig",
                    "package_name": "iniconfig",
                    "required_version": ">=1.0.1"
                },
                {
                    "dependencies": [],
                    "installed_version": "26.2",
                    "key": "packaging",
                    "package_name": "packaging",
                    "required_version": ">=22"
                },
                {
                    "dependencies": [],
                    "installed_version": "1.6.0",
                    "key": "pluggy",
                    "package_name": "pluggy",
                    "required_version": ">=1.5,<2"
                },
                {
                    "dependencies": [],
                    "installed_version": "2.20.0",
                    "key": "pygments",
                    "package_name": "Pygments",
                    "required_version": ">=2.7.2"
                }
            ],
            "installed_version": "9.1.1",
            "key": "pytest",
            "package_name": "pytest",
            "required_version": "9.1.1"
        }
    ]

mermaid
-------

`Mermaid <https://mermaid.js.org>`_ flowchart diagram:

.. doctest::

    >>> print(run_pipdeptree("--packages", "pytest", "-o", "mermaid"), end="")
    flowchart TD
        classDef missing stroke-dasharray: 5
        iniconfig["iniconfig<br/>2.3.0"]
        packaging["packaging<br/>26.2"]
        pluggy["pluggy<br/>1.6.0"]
        pygments["Pygments<br/>2.20.0"]
        pytest["pytest<br/>9.1.1"]
        pytest -- ">=1.0.1" --> iniconfig
        pytest -- ">=1.5,<2" --> pluggy
        pytest -- ">=2.7.2" --> pygments
        pytest -- ">=22" --> packaging
    <BLANKLINE>

This renders as:

.. mermaid::

    flowchart TD
        classDef missing stroke-dasharray: 5
        iniconfig["iniconfig<br/>2.3.0"]
        packaging["packaging<br/>26.2"]
        pluggy["pluggy<br/>1.6.0"]
        pygments["Pygments<br/>2.20.0"]
        pytest["pytest<br/>9.1.1"]
        pytest -- ">=1.0.1" --> iniconfig
        pytest -- ">=1.5,<2" --> pluggy
        pytest -- ">=2.7.2" --> pygments
        pytest -- ">=22" --> packaging

graphviz
--------

The Graphviz renderer supports DOT source and binary formats such as PDF and SVG. DOT source needs no external program:

.. doctest::

    >>> print(run_pipdeptree("--packages", "pytest", "-o", "graphviz-dot").expandtabs(4), end="")
    digraph {
        iniconfig [label="iniconfig\n2.3.0"]
        packaging [label="packaging\n26.2"]
        pluggy [label="pluggy\n1.6.0"]
        pygments [label="Pygments\n2.20.0"]
        pytest -> iniconfig [label=">=1.0.1"]
        pytest -> packaging [label=">=22"]
        pytest -> pluggy [label=">=1.5,<2"]
        pytest -> pygments [label=">=2.7.2"]
        pytest [label="pytest\n9.1.1"]
    }
    <BLANKLINE>

Binary formats require the Graphviz ``dot`` executable from the operating system. pipdeptree sends its DOT source to
that executable:

.. code-block:: console

    $ pipdeptree -o graphviz-pdf > dependencies.pdf
    $ pipdeptree -o graphviz-png > dependencies.png
    $ pipdeptree -o graphviz-svg > dependencies.svg

Use ``graphviz-<format>``, where ``<format>`` is any
`Graphviz output format <https://graphviz.org/docs/outputs/>`_ (dot, pdf, png, svg, jpeg, etc.).

summary
-------

``--summary`` replaces the tree with an environment health report for CI gates and audits. The flag selects the
metrics; ``-o`` selects ``text``, ``rich`` or ``json`` presentation. pipdeptree rejects tree formats such as Mermaid
for a summary. Run it over the environment or scope it with ``--packages``:

.. doctest::

    >>> print(run_pipdeptree("--packages", "pytest", "--summary", "-o", "text"), end="")
    total packages:           5
    direct dependencies:      1
    transitive dependencies:  4
    max depth:                2
    cyclic dependencies:      0
    missing dependencies:     0
    conflicting dependencies: 0 (0 edges)
    licenses:                 (N/A): 5
    unknown licenses:         5
    copyleft licenses:        no
    min requires-python:      n/a
    total size:               0 B

For terminals, ``--summary -o rich`` prints the same metrics as a styled table. For automation, ``-o json`` emits
a machine-readable object:

.. doctest::

    >>> print(run_pipdeptree("--packages", "pytest", "--summary", "-o", "json"), end="")
    {
      "conflicting_dependencies": {
        "edges": 0,
        "packages": 0
      },
      "cyclic_dependencies": 0,
      "direct_dependencies": 1,
      "licenses": {
        "breakdown": {
          "(N/A)": 5
        },
        "copyleft": false,
        "unknown": 5
      },
      "max_depth": 2,
      "min_requires_python": "n/a",
      "missing_dependencies": 0,
      "total_packages": 5,
      "total_size": "0 B",
      "total_size_raw": 0,
      "transitive_dependencies": 4
    }

``pipdeptree from-lock pylock.toml --summary`` and ``pipdeptree from-index 'flask' --summary`` summarize resolved
trees. The first five graph-structural metrics work with all sources. Installed-environment metrics read distribution
metadata and files, which ``from-index`` and ``from-lock`` do not carry. Under those subcommands, text reports ``n/a``
and JSON omits the field. See :doc:`/explanation` for the reasoning.

The formats work with ``from-index`` (alias ``i``) and ``from-lock`` (alias ``l``). For example,
``pipdeptree from-index --requirements requirements.txt -o json`` resolves and renders index packages, while
``pipdeptree from-lock pylock.toml -o json`` renders a PEP 751 lock offline. See :doc:`/how-to/usage` for details.
