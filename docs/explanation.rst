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

Optional dependencies (extras)
------------------------------

When you pass ``--extras``, pipdeptree augments the tree with optional dependency edges. Two kinds
of extras are surfaced:

1. **Explicitly requested extras.** When a parent's metadata records a dependency like
   ``oauthlib[signedtoken]``, the deps gated behind oauthlib's ``signedtoken`` extra get
   added under oauthlib in the tree, annotated with ``extra: signedtoken``.

2. **Active extras.** Python packaging metadata never records *why* a package was installed,
   only what it could require. pipdeptree therefore considers an extra "active" when every dep
   that extra would have requested is already installed -- the same heuristic Python libraries use
   at runtime to decide whether a feature is available (``try: import optional_dep``). When an
   extra is active, pipdeptree adds the same edges it would have added if the extra had been
   requested explicitly.

Both kinds propagate. If activating ``A[x]`` pulls in ``B[y]``, pipdeptree also adds the deps
``B[y]`` would gate. Because metadata cannot tell us that ``B`` was installed for some other
reason, the same package may appear under multiple parents through this mechanism.

.. mermaid::

    flowchart TD
        A[App] -- requires --> O[oauthlib]
        A -- "requires<br/>oauthlib[signedtoken]" --> O
        O -. "extra: signedtoken" .-> C[cryptography]
        O -. "extra: signedtoken" .-> P[pyjwt]
        style C fill:#8e44ad,color:#fff
        style P fill:#8e44ad,color:#fff

To leave optional edges out entirely, omit ``--extras`` (the default). Edges added through
extras are always annotated with the originating extra, so they remain distinguishable from
mandatory dependencies in every output format.

Limitations
-----------

- pipdeptree only sees packages that are already installed. It cannot predict what a ``pip install`` will do.
- If you need a dependency resolver that works without installing packages first, consider :pypi:`uv`.
- Extra/optional dependencies are not shown by default; use ``--extras`` to include them.
- ``--extras`` cannot reconstruct extras that were requested only on the command line
  (e.g. ``pip install foo[dev]`` where ``foo`` is itself top-level), because that information
  is never persisted into installed package metadata.
