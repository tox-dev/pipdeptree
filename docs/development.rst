Development
===========

Setup
-----

Clone the repository and create a development environment:

.. code-block:: bash

    git clone https://github.com/tox-dev/pipdeptree.git
    cd pipdeptree
    tox run -e dev

This installs pipdeptree in editable mode with all extras (graphviz, rich, test).

Running from source
-------------------

After setting up the dev environment:

.. code-block:: bash

    .tox/dev/bin/pipdeptree

Running tests
-------------

.. code-block:: bash

    tox run -e 3.13

This runs the full test suite with coverage. You can substitute any supported Python version (3.10--3.14).

Linting and formatting
-----------------------

.. code-block:: bash

    tox run -e fix

This runs all pre-commit hooks including ruff formatting and linting.

Type checking
-------------

.. code-block:: bash

    tox run -e type

Building documentation
----------------------

.. code-block:: bash

    tox run -e docs

The output is written to ``.tox/docs_out/html/index.html``.

Contributing
------------

1. Fork the repository.
2. Create a feature branch.
3. Ensure ``tox run -e fix`` passes.
4. Submit a pull request.
