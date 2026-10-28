Output formats
==============

pipdeptree supports multiple output formats via ``-o FMT`` (or ``--output FMT``). An interactive terminal defaults to
``rich``. Redirected output, ``TERM=dumb`` and ``NO_COLOR`` default to ``text``. The executable examples use
``--packages pytest`` to keep the output concise.

text
----

Unicode box-drawing tree:

.. code-block:: console

    $ pipdeptree --packages pytest -o text
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

.. code-block:: console

    $ pipdeptree --packages pytest -o rich
    pytest==9.1.1
    ┣━━ ✓ iniconfig required: >=1.0.1 installed: 2.3.0
    ┣━━ ✓ packaging required: >=22 installed: 26.2
    ┣━━ ✓ pluggy required: >=1.5,<2 installed: 1.6.0
    ┗━━ ✓ Pygments required: >=2.7.2 installed: 2.20.0

freeze
------

Freeze emits pip-compatible requirements with indentation for the hierarchy:

.. code-block:: console

    $ pipdeptree --packages pytest -o freeze
    pytest==9.1.1
      iniconfig==2.3.0
      packaging==26.2
      pluggy==1.6.0
      Pygments==2.20.0

json
----

JSON emits a flat array of package and dependency objects:

.. code-block:: console

    $ pipdeptree --packages pytest -o json
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

.. code-block:: console

    $ pipdeptree --packages iniconfig -o json --metadata license --computed size,unique-deps-count,unique-deps-names
    [
        {
            "package": {
                "key": "iniconfig",
                "package_name": "iniconfig",
                "installed_version": "2.3.0",
                "metadata": {
                    "license": "MIT License"
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

.. code-block:: console

    $ pipdeptree --packages pytest -o json-tree
    [
        {
            "key": "pytest",
            "package_name": "pytest",
            "installed_version": "9.1.1",
            "required_version": "9.1.1",
            "dependencies": [
                {
                    "key": "iniconfig",
                    "package_name": "iniconfig",
                    "installed_version": "2.3.0",
                    "required_version": ">=1.0.1",
                    "dependencies": []
                },
                {
                    "key": "packaging",
                    "package_name": "packaging",
                    "installed_version": "26.2",
                    "required_version": ">=22",
                    "dependencies": []
                },
                {
                    "key": "pluggy",
                    "package_name": "pluggy",
                    "installed_version": "1.6.0",
                    "required_version": ">=1.5,<2",
                    "dependencies": []
                },
                {
                    "key": "pygments",
                    "package_name": "Pygments",
                    "installed_version": "2.20.0",
                    "required_version": ">=2.7.2",
                    "dependencies": []
                }
            ]
        }
    ]

mermaid
-------

`Mermaid <https://mermaid.js.org>`_ flowchart diagram. Quotes, ``#``, ``&``, ``<``, ``>``, backticks and control
characters in node labels appear as `entity codes
<https://mermaid.js.org/syntax/flowchart.html#entity-codes-to-escape-characters>`_ such as ``#34;``. A package whose name
is empty or holds characters other than ASCII letters, digits, ``-``, ``_`` and ``.`` gets a ``package_<n>`` node id:

.. code-block:: console

    $ pipdeptree --packages pytest -o mermaid
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

.. code-block:: console

    $ pipdeptree --packages pytest -o graphviz-dot
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


Binary formats require the Graphviz ``dot`` executable from the operating system. pipdeptree sends its DOT source to
that executable:

.. code-block:: console

    $ pipdeptree -o graphviz-pdf > dependencies.pdf
    $ pipdeptree -o graphviz-png > dependencies.png
    $ pipdeptree -o graphviz-svg > dependencies.svg

Use ``graphviz-<format>``, where ``<format>`` is any
`Graphviz output format <https://graphviz.org/docs/outputs/>`_ (dot, pdf, png, svg, jpeg, etc.).

pipdeptree stops ``dot`` and exits with an error when the layout takes longer than 300 seconds. For a graph that needs
more time, write ``-o graphviz-dot`` to a file and run ``dot`` on it yourself.

summary
-------

``--summary`` replaces the tree with an environment health report for CI gates and audits. The flag selects the
metrics; ``-o`` selects ``text``, ``rich`` or ``json`` presentation. pipdeptree rejects tree formats such as Mermaid
for a summary. Run it over the environment or scope it with ``--packages``:

.. code-block:: console

    $ pipdeptree --packages pytest --summary -o text
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
    total size:               0 B

For terminals, ``--summary -o rich`` prints the same metrics as a styled table. For automation, ``-o json`` emits
a machine-readable object:

.. code-block:: console

    $ pipdeptree --packages pytest --summary -o json
    {
      "total_packages": 5,
      "direct_dependencies": 1,
      "transitive_dependencies": 4,
      "max_depth": 2,
      "cyclic_dependencies": 0,
      "missing_dependencies": 0,
      "conflicting_dependencies": {
        "packages": 0,
        "edges": 0
      },
      "licenses": {
        "breakdown": {
          "(Apache-2.0 OR BSD-2-Clause)": 1,
          "(BSD-2-Clause)": 1,
          "(MIT License)": 1,
          "(MIT)": 2
        },
        "unknown": 0,
        "copyleft": false
      },
      "min_requires_python": "3.10",
      "total_size": "0 B",
      "total_size_raw": 0
    }

``pipdeptree from-lock pylock.toml --summary`` and ``pipdeptree from-index 'flask' --summary`` summarize resolved
trees. The first five graph-structural metrics work with all sources. Installed-environment metrics read distribution
metadata and files, which ``from-index`` and ``from-lock`` do not carry. Under those subcommands, text reports ``n/a``
and JSON omits the field. See :doc:`/explanation` for the reasoning.

The formats work with ``from-index`` (alias ``i``) and ``from-lock`` (alias ``l``). For example,
``pipdeptree from-index --requirements requirements.txt -o json`` resolves and renders index packages, while
``pipdeptree from-lock pylock.toml -o json`` renders a PEP 751 lock offline. See :doc:`/how-to/usage` for details.

cyclonedx-json
--------------

``cyclonedx-json`` emits a `CycloneDX <https://cyclonedx.org/>`_ 1.5 JSON Software Bill of Materials, built with the Rust
``cyclonedx-bom`` library. It works with every dependency source:

.. code-block:: console

    $ pipdeptree -o cyclonedx-json > environment.cdx.json
    $ pipdeptree --python /path/to/venv/bin/python -o cyclonedx-json > venv.cdx.json
    $ pipdeptree from-lock pylock.toml -o cyclonedx-json > locked.cdx.json
    $ pipdeptree from-index --requirements requirements.txt -o cyclonedx-json > resolved.cdx.json
    $ pipdeptree from-index --pyproject pyproject.toml -o cyclonedx-json > project.cdx.json

The Python API also supports ``pipdeptree.render(output_format="cyclonedx-json")`` for installed environments.

Each distribution becomes one ``library`` component. Its name retains the distribution's spelling; its PyPI
package URL (``purl``) uses the normalized Python project name and an escaped version. The same URL serves as its
``bom-ref``. Extras select dependencies of a distribution; they do not create additional components or versions.
The ``dependencies`` section links parent references to their required components, with duplicate links collapsed.
Cycles are preserved.

``--packages``, ``--exclude`` and ``--extras`` select the graph using the same rules as other renderers. With
``--reverse``, package selection follows dependents, but SBOM links still point from a package to its dependencies.
``--depth`` and ``--all`` control tree presentation and have no effect on the flat SBOM. ``--summary`` cannot be
combined with ``-o cyclonedx-json``.

Installed package metadata supplies licenses and repeated ``pipdeptree:provides-extra`` properties automatically. Valid
SPDX ``License-Expression`` values become CycloneDX license expressions; other license labels become named licenses, one
per license classifier. ``--metadata`` and ``--computed`` add properties under ``pipdeptree:metadata:FIELD`` and
``pipdeptree:computed:FIELD`` respectively.

Missing distributions remain identifiable as unversioned components marked ``pipdeptree:missing: true``. Their own
dependency graph is unknown, so they have no dependency entry and are listed in a ``compositions`` entry with
``aggregate: unknown``. A package present in a lock without a version also omits its version, but is not marked missing.

The SBOM contains the data available in pipdeptree's graph. Lock and index sources currently supply names,
versions and dependency relationships, rather than installed distribution metadata, artifact hashes or source
provenance. A lock's exact-version links are derived from its pins; they do not reconstruct the original dependency
constraints. Index resolution retains original declarations when the resolver provides them. Requirements and
pyproject inputs use ``from-index`` resolution; pipdeptree does not infer an installed environment from those files.
