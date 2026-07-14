Development
===========

Setup
-----

Clone the repository and create a development environment:

.. code-block:: bash

    git clone https://github.com/tox-dev/pipdeptree.git
    cd pipdeptree
    tox run -e dev

Tox installs pipdeptree in editable mode with its test dependencies.

The build uses Meson for editable installs and wheels. Its native target invokes Cargo for dependency resolution and
compilation; PyO3 provides the extension boundary. Python exposes the public API, notebook display hooks and CLI byte
output. Rust handles environment inspection, package data, dependency graphs, lock and index input, and rendering.

Running from source
-------------------

After setting up the dev environment:

.. code-block:: bash

    .tox/dev/bin/pipdeptree

Building packages
-----------------

Build through the PEP 517 Meson backend:

.. code-block:: bash

    uv build

To inspect the native build without creating a wheel:

.. code-block:: bash

    meson setup build
    meson compile -C build

Running tests
-------------

.. code-block:: bash

    cargo test --no-default-features --test public_api
    cargo llvm-cov --no-default-features --test public_api --fail-under-lines 100 --fail-under-functions 100
    tox run -e 3.14

The Rust suite calls production code through ``Application`` and its public process boundary. Disabling
extension-module linking lets the test executable link to Python. The Python suite tests the packaged API and CLI.
You can substitute a supported Python version from 3.10 through 3.14.

Documentation examples
-----------------------

Pytest executes every ``$ pipdeptree`` command inside the documentation's ``code-block:: console`` blocks against a
synthetic package directory and compares the documented output (``...`` elides, a ``$ echo $?`` line checks the exit
code). A ``code-block`` with a ``:caption:`` defines the file that later commands in the same document read, so lock
and requirements examples stay self-contained. Two comment markers placed directly above a console block change how
it runs: ``.. runs-online`` skips it (its output is a pinned snapshot of a live index resolve),
``.. illustrative`` skips a narrative example that no fixture reproduces, and ``.. conflicting-environment`` runs it
against a fixture with a version conflict. Blocks that show a command without output also stay unchecked.

After a change that alters rendered output, refresh the pinned blocks in place and review the diff:

.. code-block:: bash

    tox run -e docs-update

Examples that still match keep their hand-written form; ``runs-online`` blocks are never rewritten, so refresh their
snapshots manually when the resolve changes.

Linting and formatting
-----------------------

.. code-block:: bash

    cargo fmt --all --check
    cargo clippy --all-targets --all-features -- -D warnings
    tox run -e fix

The tox environment runs the repository hooks. These include Ruff, TOML formatters, workflow validation and Prettier.

Type checking
-------------

.. code-block:: bash

    tox run -e type

Building documentation
----------------------

.. code-block:: bash

    tox run -e docs

Sphinx writes ``.tox/docs_out/html/index.html``.

Contributing
------------

1. Fork the repository.
2. Create a feature branch.
3. Run the Rust tests, ``tox run -e 3.14,type,docs,pkg_meta`` and ``prek run --all-files``.
4. Submit a pull request.
