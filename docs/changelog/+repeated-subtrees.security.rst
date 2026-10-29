List a package's dependencies once per top-level package in the ``text``, ``rich``, ``freeze`` and ``json-tree`` trees,
forward and ``--reverse``, and end each later line for it, and the line that closes a dependency cycle, in ``(*)``
(``"repeated": true`` in ``json-tree``). Tree output now grows with the number of dependency edges instead of the number
of paths through them.
