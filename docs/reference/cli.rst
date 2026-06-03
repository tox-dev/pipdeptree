CLI reference
=============

.. sphinx_argparse_cli::
    :module: pipdeptree._cli
    :func: build_parser
    :title:

Summary metrics
---------------

Fields emitted by ``--summary`` (styled with ``-o text``, ``rich`` or ``json``). The *Modes* column notes where
each is available: *all* works for every command; *default* needs an installed environment and is reported as
``n/a`` (omitted in JSON) under ``from-index``/``from-lock``.

.. list-table::
    :header-rows: 1
    :widths: 25 55 20

    * - Field
      - Meaning
      - Modes
    * - ``total_packages``
      - Number of packages in the tree.
      - all
    * - ``direct_dependencies``
      - Top-level packages (not required by any other package).
      - all
    * - ``transitive_dependencies``
      - Packages pulled in only as a dependency of another (``total - direct``).
      - all
    * - ``max_depth``
      - Longest dependency chain, counted in packages.
      - all
    * - ``cyclic_dependencies``
      - Number of dependency cycles detected.
      - all
    * - ``missing_dependencies``
      - Distinct packages required but not installed.
      - default
    * - ``conflicting_dependencies``
      - ``packages`` with an unsatisfied requirement and the total conflicting ``edges``.
      - default
    * - ``licenses``
      - ``breakdown`` per license string, count of ``unknown`` licenses, and a ``copyleft`` flag.
      - default
    * - ``min_requires_python``
      - Highest ``Requires-Python`` lower bound across packages (the effective floor).
      - default
    * - ``total_size`` / ``total_size_raw``
      - On-disk size of all packages, human-readable and in bytes.
      - default
