Stop tree output (``text``, ``rich``, ``freeze`` and ``json-tree``) with an error when a dependency chain nests deeper
than 200 levels, where it used to overflow the stack and kill the process, including a Python process that called
``pipdeptree.render()``. Cycle warnings no longer recurse.
