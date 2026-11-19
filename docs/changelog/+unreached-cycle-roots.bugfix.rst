Packages in a dependency cycle that no other package requires, such as ``poetry`` and ``poetry-plugin-export`` after
``pip install poetry==1.8.5``, now show as top-level entries instead of vanishing from the tree, freeze, JSON tree and
depth-limited Graphviz output, in both directions, and count toward the summary's maximum depth.
