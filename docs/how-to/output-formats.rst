Output formats
==============

pipdeptree supports multiple output formats via ``-o FMT`` (or ``--output FMT``). All examples below use
``--packages pytest`` to keep the output concise.

text (default)
--------------

Unicode box-drawing tree:

.. code-block:: console

    $ pipdeptree --packages pytest
    pytest==9.0.2
    ├── iniconfig [required: >=1.0.1, installed: 2.3.0]
    ├── packaging [required: >=22, installed: 26.0]
    ├── pluggy [required: >=1.5,<2, installed: 1.6.0]
    └── Pygments [required: >=2.7.2, installed: 2.19.2]

rich
----

Enhanced terminal output with colors and checkmarks (requires ``pipdeptree[rich]``):

.. code-block:: console

    $ pipdeptree --packages pytest -o rich
    pytest==9.0.2
    ┣━━ ✓ iniconfig required: >=1.0.1 installed: 2.3.0
    ┣━━ ✓ packaging required: >=22 installed: 26.0
    ┣━━ ✓ pluggy required: >=1.5,<2 installed: 1.6.0
    ┗━━ ✓ Pygments required: >=2.7.2 installed: 2.19.2

freeze
------

pip-compatible flat format with indentation showing hierarchy:

.. code-block:: console

    $ pipdeptree --packages pytest -o freeze
    pytest==9.0.2
      iniconfig==2.3.0
      packaging==26.0
      pluggy==1.6.0
      Pygments==2.19.2

json
----

Flat JSON array with package and dependency objects:

.. code-block:: console

    $ pipdeptree --packages pytest -o json

.. code-block:: json

    [
        {
            "package": {
                "key": "pytest",
                "package_name": "pytest",
                "installed_version": "9.0.2"
            },
            "dependencies": [
                {
                    "key": "iniconfig",
                    "package_name": "iniconfig",
                    "installed_version": "2.3.0",
                    "required_version": ">=1.0.1"
                },
                {
                    "key": "pluggy",
                    "package_name": "pluggy",
                    "installed_version": "1.6.0",
                    "required_version": ">=1.5,<2"
                }
            ]
        }
    ]

With ``--metadata`` or ``--computed``, package dicts include extra fields:

.. code-block:: console

    $ pipdeptree --packages rich -o json --metadata license --computed size,unique-deps-count,unique-deps-names

.. code-block:: json

    {
        "package": {
            "key": "rich",
            "package_name": "rich",
            "installed_version": "14.3.3",
            "metadata": {
                "license": "MIT License"
            },
            "computed": {
                "size": "1.2 MB",
                "unique_deps_count": 2,
                "unique_deps_names": [
                    "markdown-it-py",
                    "mdurl"
                ]
            }
        },
        "dependencies": [
            {
                "key": "markdown-it-py",
                "package_name": "markdown-it-py",
                "installed_version": "4.0.0",
                "required_version": ">=2.2.0"
            },
            {
                "key": "pygments",
                "package_name": "Pygments",
                "installed_version": "2.19.2",
                "required_version": ">=2.13.0,<3.0.0"
            }
        ]
    }

json-tree
---------

Nested JSON mirroring the text tree layout:

.. code-block:: console

    $ pipdeptree --packages pytest -o json-tree

.. code-block:: json

    [
        {
            "key": "pytest",
            "package_name": "pytest",
            "installed_version": "9.0.2",
            "required_version": "9.0.2",
            "dependencies": [
                {
                    "key": "iniconfig",
                    "package_name": "iniconfig",
                    "installed_version": "2.3.0",
                    "required_version": ">=1.0.1",
                    "dependencies": []
                }
            ]
        }
    ]

mermaid
-------

`Mermaid <https://mermaid.js.org>`_ flowchart diagram:

.. code-block:: console

    $ pipdeptree --packages pytest -o mermaid

.. code-block:: text

    flowchart TD
        classDef missing stroke-dasharray: 5
        iniconfig["iniconfig<br/>2.3.0"]
        packaging["packaging<br/>26.0"]
        pluggy["pluggy<br/>1.6.0"]
        pygments["Pygments<br/>2.19.2"]
        pytest["pytest<br/>9.0.2"]
        pytest -- ">=1.0.1" --> iniconfig
        pytest -- ">=1.5,<2" --> pluggy
        pytest -- ">=2.7.2" --> pygments
        pytest -- ">=22" --> packaging

This renders as:

.. mermaid::

    flowchart TD
        classDef missing stroke-dasharray: 5
        iniconfig["iniconfig<br/>2.3.0"]
        packaging["packaging<br/>26.0"]
        pluggy["pluggy<br/>1.6.0"]
        pygments["Pygments<br/>2.19.2"]
        pytest["pytest<br/>9.0.2"]
        pytest -- ">=1.0.1" --> iniconfig
        pytest -- ">=1.5,<2" --> pluggy
        pytest -- ">=2.7.2" --> pygments
        pytest -- ">=22" --> packaging

graphviz
--------

Generate Graphviz output in various formats (requires ``pipdeptree[graphviz]``). The ``dot`` format produces the graph
description language:

.. code-block:: console

    $ pipdeptree --packages pytest -o graphviz-dot
    digraph {
    	iniconfig [label="iniconfig\n2.3.0"]
    	packaging [label="packaging\n26.0"]
    	pluggy [label="pluggy\n1.6.0"]
    	pygments [label="Pygments\n2.19.2"]
    	pytest -> iniconfig [label=">=1.0.1"]
    	pytest -> packaging [label=">=22"]
    	pytest -> pluggy [label=">=1.5,<2"]
    	pytest -> pygments [label=">=2.7.2"]
    	pytest [label="pytest\n9.0.2"]
    }

Other formats render the graph directly to binary output:

.. code-block:: console

    $ pipdeptree -o graphviz-pdf > dependencies.pdf
    $ pipdeptree -o graphviz-png > dependencies.png
    $ pipdeptree -o graphviz-svg > dependencies.svg

The format is specified as ``graphviz-<format>`` where ``<format>`` is any
`Graphviz output format <https://graphviz.org/docs/outputs/>`_ (dot, pdf, png, svg, jpeg, etc.).
