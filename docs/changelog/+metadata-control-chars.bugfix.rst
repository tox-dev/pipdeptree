Replace control characters other than tab with U+FFFD in package names, versions, metadata header values,
``direct_url.json`` fields and lock file strings, so a package can no longer send escape sequences to the terminal, cut
a Graphviz label short or crash ``--summary -o rich``.
