List a package's dependencies once per top-level package in the ``text``, ``rich``, ``freeze`` and ``json-tree`` trees,
forward and ``--reverse``. A later line for the package ends in ``(*)`` (``"repeated": true`` in ``json-tree``), and a
dependency cycle now shows its closing edge the same way, so tree output grows with the number of dependency edges
instead of the number of paths through them.
