Tree output (``text``, ``rich``, ``freeze`` and ``json-tree``) now fails with an error when a dependency chain nests
deeper than 500 levels, where it used to overflow the stack and kill the process, including a Python process that
called ``pipdeptree.render()``. Cycle warnings no longer recurse once per package in the cycle.
