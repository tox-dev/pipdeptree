``-o graphviz-*`` with ``--reverse`` and ``--depth`` now treats a missing requirement as a root, as the text tree does.
Before, ``--depth 0`` still drew the edges from it, a package that needed only missing requirements showed up as a root
of its own, and a package reached only through a missing requirement within the limit got an edge but no labeled node,
so ``dot`` drew it as a bare name.
