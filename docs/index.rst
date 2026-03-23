##############
 pipdeptree
##############

.. image:: https://img.shields.io/pypi/v/pipdeptree?style=flat-square
    :target: https://pypi.org/project/pipdeptree/#history
    :alt: Latest version on PyPI

.. image:: https://img.shields.io/pypi/pyversions/pipdeptree?style=flat-square
    :alt: PyPI - Python Version

.. image:: https://static.pepy.tech/badge/pipdeptree/month
    :target: https://pepy.tech/project/pipdeptree
    :alt: Downloads

.. image:: https://github.com/tox-dev/pipdeptree/actions/workflows/check.yaml/badge.svg
    :target: https://github.com/tox-dev/pipdeptree/actions/workflows/check.yaml
    :alt: check

.. image:: https://results.pre-commit.ci/badge/github/tox-dev/pipdeptree/main.svg
    :target: https://results.pre-commit.ci/latest/github/tox-dev/pipdeptree/main
    :alt: pre-commit.ci status

.. image:: https://img.shields.io/pypi/l/pipdeptree?style=flat-square
    :target: https://opensource.org/licenses/MIT
    :alt: PyPI - License

``pipdeptree`` is a command-line utility that displays installed Python packages as a dependency tree. It works for
packages installed globally or inside a virtualenv.

**********************
 Why use pipdeptree?
**********************

``pip freeze`` shows all installed packages as a flat list, making it hard to tell which are top-level packages and
which are transitive dependencies. ``pipdeptree`` solves this by rendering the full dependency graph as a tree:

.. code-block:: console

    $ pip freeze
    Flask==0.10.1
    itsdangerous==0.24
    Jinja2==2.11.2
    MarkupSafe==0.22
    Werkzeug==0.11.2

    $ pipdeptree
    Flask==0.10.1
      - itsdangerous [required: >=0.21, installed: 0.24]
      - Jinja2 [required: >=2.4, installed: 2.11.2]
        - MarkupSafe [required: >=0.23, installed: 0.22]
      - Werkzeug [required: >=0.7, installed: 0.11.2]

The same relationships, visualized as a graph:

.. mermaid::

    flowchart TD
        flask["Flask<br/>0.10.1"] --> itsdangerous["itsdangerous<br/>0.24"]
        flask --> jinja2["Jinja2<br/>2.11.2"]
        flask --> werkzeug["Werkzeug<br/>0.11.2"]
        jinja2 --> markupsafe["MarkupSafe<br/>0.22"]
        jinja2 -. "CONFLICT: requires >=0.23" .-> markupsafe
        style markupsafe fill:#e74c3c,color:#fff

Beyond visualization, ``pipdeptree`` can:

- **Detect conflicting dependencies** -- packages required at incompatible versions by different parents.
- **Find circular dependencies** -- cycles in the dependency graph.
- **Reverse lookup** -- find out *why* a package is installed (``--reverse --packages <name>``).
- **Export** to JSON, `Mermaid <https://mermaid.js.org>`_ diagrams, or `Graphviz <https://graphviz.org>`_ graphs for
  further analysis.

******************
 Quick navigation
******************

**Tutorial** -- Learn by doing

- :doc:`tutorial/getting-started` -- Install pipdeptree and understand the output

**How-to guides** -- Solve specific problems

- :doc:`how-to/usage` -- Filtering, reverse lookup, virtualenvs, warnings
- :doc:`how-to/output-formats` -- Text, rich, freeze, JSON, Mermaid, Graphviz

**Reference** -- Technical information

- :doc:`reference/cli` -- All command-line options

**Explanation** -- Understand the internals

- :doc:`explanation` -- How pipdeptree discovers and resolves packages

.. toctree::
    :hidden:
    :caption: Tutorial

    tutorial/getting-started

.. toctree::
    :hidden:
    :caption: How-to guides

    how-to/usage
    how-to/output-formats

.. toctree::
    :hidden:
    :caption: Reference

    reference/cli

.. toctree::
    :hidden:
    :caption: Explanation

    explanation

.. toctree::
    :hidden:
    :caption: Project

    development
