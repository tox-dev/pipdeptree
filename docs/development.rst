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

Examples that still match keep their hand-written form. ``runs-online`` blocks stay untouched by default; append
``-- --online`` on a network-connected machine to re-resolve and refresh their pinned snapshots too.

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

Releasing
---------

``tools/version.py`` derives the version from the release tags, so the tag a release carries is the version its wheels
and sdist report. Nothing in the tree names the version, and the ``VERSION`` file exists for builds with no tags to
read, such as one from an unpacked sdist.

Every user-visible change brings a news fragment under ``docs/changelog``, named ``<issue>.<type>.rst`` with one of the
types ``breaking``, ``feature``, ``bugfix``, ``doc`` or ``packaging``. The unreleased fragments render as a draft
section at the top of :doc:`changelog`, and the release folds them into it.

Cut a release by running the ``Prepare release`` workflow and choosing a bump. It builds the changelog, commits it on
the upstream ``main`` branch, tags that commit and opens the GitHub release, and that tag push starts the publish
workflow. The same steps run from a checkout against the upstream remote:

.. code-block:: bash

    tox run -e release -- --bump minor

Contributing
------------

1. Fork the repository.
2. Create a feature branch.
3. Add a news fragment under ``docs/changelog`` when the change is user-visible.
4. Run the Rust tests, ``tox run -e 3.14,type,docs,pkg_meta`` and ``prek run --all-files``.
5. Submit a pull request.
