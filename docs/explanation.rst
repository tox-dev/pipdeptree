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

Limitations
-----------

- pipdeptree only sees packages that are already installed. It cannot predict what a ``pip install`` will do.
- If you need a dependency resolver that works without installing packages first, consider :pypi:`uv`.
- Extra/optional dependencies are not shown by default; use ``--extras`` to include them.
