How pipdeptree works
====================

Package discovery
-----------------

pipdeptree uses Python's standard library (``importlib.metadata``) to discover installed packages and their metadata.
This approach makes it lightweight and stable across different Python and pip versions without depending on pip's
internal APIs.

.. mermaid::

    flowchart TD
        A["📁 site-packages/"] --> B["importlib.metadata"]
        B --> C["Package metadata<br/>(name, version, requires)"]
        C --> D["Build dependency graph"]
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

For generating freeze-format output and resolving package information, pipdeptree implements:

- **PEP 440** -- Version specifiers and direct reference syntax (``package @ url``).
- **PEP 503** -- Package name normalization for consistent key generation.
- **PEP 610** -- ``direct_url.json`` metadata parsing for VCS, archive, and editable installs.

Dependency resolution
---------------------

pipdeptree does **not** resolve dependencies -- it reads metadata from already-installed packages and constructs the
tree from that. It reports what is installed, not what *should* be installed.

Conflicting dependency detection works by comparing version constraints: if package A requires ``foo>=2.0`` and package
B requires ``foo<2.0``, pipdeptree flags this as a conflict.

.. mermaid::

    flowchart TD
        A["App A"] -- "requires foo>=2.0" --> foo["foo 1.5\n(installed)"]
        B["App B"] -- "requires foo<2.0" --> foo
        foo -. "CONFLICT: 1.5 does not satisfy >=2.0" .-> A
        style foo fill:#e74c3c,color:#fff

Circular dependency detection uses cycle detection on the directed dependency graph.

.. mermaid::

    flowchart LR
        X["package-a"] --> Y["package-b"]
        Y --> X
        style X fill:#e67e22,color:#fff
        style Y fill:#e67e22,color:#fff

from-index: resolving from an index instead of inspecting
---------------------------------------------------------

The default command reads ``importlib.metadata`` for packages that are *already installed*: each one has a
``METADATA`` file and real files on disk, so pipdeptree can report its version, dependencies, license, metadata
fields and on-disk size.

The ``from-index`` subcommand answers a different question -- "what *would* this tree look like?" -- so it cannot
read installed state, because nothing is installed. It hands the requirements to the optional index resolver, which
runs a PubGrub solve against a package index (PyPI) and picks a consistent set of versions *without downloading or
installing anything*. The name says where the answer comes from: the index server, not the Python environment.
It reads requirements files as standard ``requirements.txt`` files, so nested ``-r``, ``-c`` constraints,
environment markers and comments all carry through. Editable installs, local paths and pinned git requirements
resolve from the checkout itself rather than the index (see below). Bare wheel/sdist archive URLs and non-git VCS
schemes stay out of scope, since the resolver has no way to map them. pipdeptree then renders that resolved graph
through the same machinery as the default command.

PubGrub is a version-solving algorithm: the resolver asks the index for the candidate versions of each
requirement, follows their declared dependencies, and backtracks when two constraints cannot hold at once until it
reaches a single consistent assignment or proves none exists. Querying the index is why the subcommand needs the
network and the extra. The default command reads files already on disk, so it needs neither.

This solve depends on the same environment markers that govern a real install. A requirement guarded by
``; python_version < "3.9"`` enters the resolve only when the marker evaluates true, so the Python version you
resolve for can change which packages appear. The resolver evaluates markers against the interpreter running
pipdeptree, which matters when you preview a tree for a version other than your own.

The resolver handles a checkout (an editable install, a local path, or a cloned git repo) by reading its metadata
rather than querying the index. It reads the project's PEP 621 ``[project]`` table -- and PEP 643 static metadata
in sdists -- *statically*, with no build. It runs a build backend only when a target declares its dependencies
dynamically and offers no static fallback. Most local and git dependencies resolve without any build; a project
that computes its dependencies at build time pays for one.

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

The resolver yields only names, versions and dependency edges, so ``from-index`` drops the installed-only display
options: ``--metadata``, ``--computed`` and ``--license`` each need a ``METADATA`` file or on-disk files that never
exist for un-downloaded packages, and the environment-inspection options (``--python``, ``--path``, ``-l``/``-u``)
have no environment to point at. The pure graph/version/render flags -- filtering, depth, ``--reverse``,
``--extras`` and the output formats -- apply unchanged.

Optional dependencies (extras)
------------------------------

The ``--extras`` option controls which optional dependency edges appear in the tree. It takes one
of three values:

``explicit`` (the default)
    Show an extra only when a parent's metadata requests it via ``name[extra]``, such as
    ``oauthlib[signedtoken]``. The deps gated behind that extra are added under the parent,
    annotated with ``extra: signedtoken``. This propagates: if ``A[x]`` pulls in ``B[y]``, the
    deps ``B[y]`` gates are added too.

``active``
    Everything ``explicit`` shows, plus extras that nothing requested but whose dependencies are
    all installed. Packaging metadata never records why a package was installed, so this treats a
    satisfiable extra as if it had been requested. The same package can then appear under several
    parents, and the tree grows accordingly.

``none``
    Omit optional edges entirely.

.. mermaid::

    flowchart TD
        A[App] -- requires --> O[oauthlib]
        A -- "requires<br/>oauthlib[signedtoken]" --> O
        O -. "extra: signedtoken" .-> C[cryptography]
        O -. "extra: signedtoken" .-> P[pyjwt]
        style C fill:#8e44ad,color:#fff
        style P fill:#8e44ad,color:#fff

Edges added through an extra are always annotated with the originating extra, so they stay
distinguishable from mandatory dependencies in every output format.

Limitations
-----------

- pipdeptree only sees packages that are already installed. It cannot predict what a ``pip install`` will do.
- To preview the tree for a set of requirements without installing them, use the ``from-index`` subcommand (see
  :doc:`/how-to/usage` and the "from-index: resolving from an index instead of inspecting" section above), which
  resolves them via the optional index resolver. For a full-featured standalone resolver, :pypi:`uv` is another
  option.
- Optional dependencies show by default (``--extras=explicit``); use ``--extras=none`` to omit them,
  or ``--extras=active`` to also include extras that are merely satisfiable.
- ``--extras`` cannot reconstruct extras that were requested only on the command line
  (e.g. ``pip install foo[dev]`` where ``foo`` is itself top-level), because that information
  is never persisted into installed package metadata.
