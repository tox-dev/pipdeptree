How pipdeptree works
====================

Package discovery
-----------------

The native extension scans the selected interpreter's package paths and reads ``METADATA``, ``PKG-INFO``,
``direct_url.json``, ``RECORD`` and legacy ``.egg-link`` files. It does not import pip or packaging. The Python layer
starts the extension, writes its byte output and implements notebook display hooks.

.. mermaid::

    flowchart TD
        A["site-packages/"] --> B["Rust metadata scanner"]
        B --> C["PEP 508 requirements<br/>and package metadata"]
        C --> D["Rust dependency graph"]
        D --> E["Render output"]
        E --> F["text / rich"]
        E --> G["json / json-tree"]
        E --> H["mermaid / graphviz"]
        E --> I["freeze"]
        style A fill:#2c3e50,color:#ecf0f1
        style B fill:#2980b9,color:#fff
        style C fill:#2980b9,color:#fff
        style D fill:#27ae60,color:#fff
        style E fill:#8e44ad,color:#fff
        style F fill:#e67e22,color:#fff
        style G fill:#e67e22,color:#fff
        style H fill:#e67e22,color:#fff
        style I fill:#e67e22,color:#fff

Standards compliance
--------------------

Rust crates implement the relevant standards:

- **PEP 440:** versions and version specifiers.
- **PEP 508:** requirements, environment markers and direct references (``package @ url``).
- **PEP 503:** package name normalization for consistent keys.
- **PEP 610:** ``direct_url.json`` metadata for VCS, archives and editable installs.

Dependency resolution
---------------------

The default command constructs a graph from installed package metadata. Use ``from-index`` to solve requirements before
installation.

Conflicting dependency detection works by comparing version constraints: if package A requires ``foo>=2.0`` and package
B requires ``foo<2.0``, pipdeptree flags this as a conflict.

.. mermaid::

    flowchart TD
        A["App A"] -- "requires foo>=2.0" --> foo["foo 1.5\n(installed)"]
        B["App B"] -- "requires foo<2.0" --> foo
        foo -. "CONFLICT: 1.5 does not satisfy >=2.0" .-> A
        style foo fill:#e74c3c,color:#fff

pipdeptree finds circular dependencies with cycle detection on the directed graph.

.. mermaid::

    flowchart LR
        X["package-a"] --> Y["package-b"]
        Y --> X
        style X fill:#e67e22,color:#fff
        style Y fill:#e67e22,color:#fff

from-index: resolving from an index instead of inspecting
---------------------------------------------------------

The default command reads the selected environment's package metadata. Installed distributions have a
``METADATA`` or ``PKG-INFO`` file and may have real files on disk, so pipdeptree can report versions, dependencies,
licenses, requested metadata fields and on-disk size.

The ``from-index`` subcommand calculates a tree before installation. It hands requirements to the bundled index
resolver, which runs a PubGrub solve against a package index and picks a consistent set of versions without downloading
or installing packages. The result comes from the index server instead of the Python environment.
It reads requirements files as standard ``requirements.txt`` files, so nested ``-r``, ``-c`` constraints,
environment markers and comments all carry through. Editable installs, local paths and pinned git requirements
resolve from the checkout itself rather than the index (see below). Bare wheel/sdist archive URLs and non-git VCS
schemes stay out of scope, since the resolver has no way to map them. pipdeptree sends the resolved graph through the
default renderers.

PubGrub solves package versions. The resolver asks the index for candidates and follows their dependencies. It
backtracks when two constraints cannot hold at once until it finds a consistent assignment or proves none exists.
Querying an index requires network access. The nab resolver is a base dependency, so ``from-index`` needs no extra.
The default command reads files on disk and does not use the network.

This solve depends on the same environment markers that govern a real install. A requirement guarded by
``; python_version < "3.9"`` enters the resolve if the marker evaluates true, so the Python version you
resolve for can change which packages appear. The resolver evaluates markers against the interpreter running
pipdeptree, which matters when you preview a tree for a version other than your own.

The resolver handles a checkout (an editable install, a local path, or a cloned git repo) by reading its metadata
rather than querying the index. PEP 621 ``[project]`` data and PEP 643 static sdist metadata need no build. A target
that declares dynamic dependencies and has no static fallback runs its build backend. Most local and git dependencies
therefore incur no build.

.. mermaid::

    flowchart TD
        S["requirements /<br/>pyproject.toml"] --> R["PubGrub resolver<br/>(index = PyPI)"]
        R --> G["Resolved graph<br/>(names, versions, edges)"]
        G --> E["Render output"]
        style S fill:#2c3e50,color:#ecf0f1
        style R fill:#2980b9,color:#fff
        style G fill:#27ae60,color:#fff
        style E fill:#8e44ad,color:#fff

Index selection feeds the resolver's index list. ``--index-url``/``--extra-index-url``, their ``PIP_*``/``UV_*``
environment fallbacks, and a ``--pyproject``'s ``[tool.nab].indexes`` each supply that list; with none set the
resolve uses PyPI.

The resolver yields names, versions and dependency edges, so ``from-index`` drops the installed-environment display
options. ``--metadata``, ``--computed`` and ``--license`` need package files on disk. The environment-inspection
options (``--python``, ``--path``, ``-l``/``-u``) need an installed environment. Filtering, depth, ``--reverse``,
``--extras`` and the output formats apply.

``from-lock`` reads versions and edges from a `PEP 751 <https://peps.python.org/pep-0751/>`_ lock (``pylock.toml``).

A PEP 751 lock records each package's name, its pinned version and the forward edges between packages (its
``[[packages]]`` and ``[[packages.dependencies]]`` tables). The tool that wrote the lock did the resolution.
``from-lock`` runs offline: Rust's ``toml`` crate maps the tables to a graph and feeds that graph through the same
render machinery, with no resolver or network. A lock holds names, versions and edges, so ``from-lock`` omits the
installed-environment display options.

The summary report and its two tiers
------------------------------------

``--summary`` condenses the tree into environment-health metrics. The flag selects the report; ``-o`` selects text,
rich or JSON presentation. The same metrics can print as a terminal table or display as an HTML table in a notebook.
All tree sources support the report. pipdeptree rejects tree formats such as Mermaid for a summary.

The metrics fall into two tiers that mirror the same installed-vs-resolved split as the display options above.

*Graph-structural* metrics include total/direct/transitive counts, max depth and cyclic dependencies. They derive
from the DAG's nodes and edges. All commands can produce them, including ``from-index`` and ``from-lock``, because
a resolved or locked graph still has nodes and edges.

*Installed-environment* metrics cover missing or conflicting dependencies, licenses, ``Requires-Python`` and size.
They read ``METADATA`` files and installed files. The synthetic ``from-index`` and ``from-lock`` graphs carry names,
versions and edges, so Rust lacks the source data for these metrics. Text marks them ``n/a`` and JSON omits them. An
API clients can distinguish zero conflicts from an unavailable measurement.

Optional dependencies (extras)
------------------------------

The ``--extras`` option controls which optional dependency edges appear in the tree. It takes one
of three values:

``explicit`` (the default)
    Show an extra when a parent's metadata requests it via ``name[extra]``, such as
    ``oauthlib[signedtoken]``. pipdeptree adds dependencies gated by that extra under the parent and annotates them
    with ``extra: signedtoken``. A request for ``A[x]`` that pulls in ``B[y]`` adds dependencies gated by ``B[y]``.

``active``
    Show the ``explicit`` extras and unrequested extras whose dependencies are present. Packaging metadata does not
    record which command requested a package, so this treats a satisfiable extra like a requested one. The same package
    can appear under multiple parents.

``none``
    Omit optional edges.

.. mermaid::

    flowchart TD
        A[App] -- requires --> O[oauthlib]
        A -- "requires<br/>oauthlib[signedtoken]" --> O
        O -. "extra: signedtoken" .-> C[cryptography]
        O -. "extra: signedtoken" .-> P[pyjwt]
        style C fill:#8e44ad,color:#fff
        style P fill:#8e44ad,color:#fff

Each extra edge carries its name, which distinguishes it from mandatory dependencies in each output format.

Limits
------

The default command sees installed packages and cannot predict a future ``pip install``. Use ``from-index`` to preview
a requirement set; :pypi:`uv` provides a standalone resolver.

Installed metadata does not preserve command-line extras such as ``pip install foo[dev]`` for a top-level ``foo``.
``--extras`` therefore cannot reconstruct that request.
