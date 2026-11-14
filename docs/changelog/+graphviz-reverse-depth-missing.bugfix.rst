``-o graphviz-*`` with ``--reverse`` and ``--depth`` now treats a missing requirement as a root, as the text tree does.
Before, ``--depth 0`` still drew the edges from it, and a package reached only through it within the limit got an edge
but no labeled node, so ``dot`` drew it as a bare name.
