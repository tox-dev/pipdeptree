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
You can substitute a supported Python version from 3.11 through 3.15.

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

Builds use the following version sources, in order:

1. ``PIPDEPTREE_VERSION``, if set.
2. A reachable Git release tag, with a development suffix for commits after the tag.
3. The ``Version`` header in the source distribution's ``PKG-INFO`` metadata.
4. ``0.0.0`` if none of those sources provides a version.

Meson-Python includes ``PKG-INFO`` in sdists, so rebuilding a wheel from an sdist needs no Git history. Bare Cargo
builds use the same precedence. Fetch release tags in shallow clones to obtain the release-derived version.

Package maintainers building without Git history or distribution metadata can supply their own version:

.. code-block:: bash

    PIPDEPTREE_VERSION=4.2.3 uv build

The override takes precedence over tags and metadata; the build uses the value the maintainer supplies.

Every user-visible change brings a news fragment under ``docs/changelog``. Name it for the change, such as
``+python-support.feature.rst``; you do not need a pull request number when writing it. Release preparation links the
fragment to its merged squash pull request and credits its human authors. Cite a separate issue with ``:issue:`123```
in the fragment text when that issue helps explain the change. The fragments appear in the draft section of
:doc:`changelog` until release.

Use ``feature`` for added or removed Python version support and other new capabilities, ``change`` for changed
behavior, ``bugfix`` for fixes, and ``doc`` for documentation that helps users. Use ``security``, ``performance``,
``deprecation``, ``removal``, ``breaking`` or ``packaging`` when the change directly affects users. A maintenance-only
pull request needs the ``skip news`` label rather than a fragment. Bot pull requests without a fragment receive that
label automatically.

Cut a release by running the ``Prepare release`` workflow with ``auto``. Feature fragments select a minor version;
other fragments select a patch version. The workflow builds and checks the changelog, commits it on upstream ``main``,
and pushes an annotated tag. The tag workflow checks the source archive and every wheel, renders GitHub notes from the
tagged changelog, publishes to PyPI, then creates the GitHub Release. The GitHub notes link to PyPI, the version diff,
and credited contributors; the documentation changelog keeps the RST links and section anchors.

Preview preparation, notes, the package build and package checks from a clean checkout. The preview uses a temporary
clone and does not push a commit, tag or release:

.. code-block:: bash

    tox run -e release

Use ``-- --bump minor`` to override automatic version selection. After reviewing the preview, dispatch the protected
workflow on ``main``:

.. code-block:: bash

    tox run -e release -- --dispatch

Contributing
------------

1. Fork the repository.
2. Create a feature branch.
3. Add a news fragment under ``docs/changelog`` when the change is user-visible.
4. Run the Rust tests, ``tox run -e 3.14,type,docs,pkg_meta`` and ``prek run --all-files``.
5. Submit a pull request.
