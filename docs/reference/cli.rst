CLI reference
=============

The native argument parser defines the command interface. Run ``pipdeptree --help`` to list the installed version's
options.

Summary metrics
---------------

``--summary`` emits the fields below in text, rich or JSON form. The *Modes* column identifies their sources. *all*
works for each command. *default* needs an installed environment; text reports ``n/a`` and JSON omits those fields for
``from-index`` and ``from-lock``.

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
      - Packages required by another package (``total - direct``).
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
