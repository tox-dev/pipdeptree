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

Next steps
----------

See :doc:`/how-to/usage` for filtering, virtualenv support, and warning control. See :doc:`/how-to/output-formats` for
all available output formats including JSON, Mermaid, and Graphviz.
