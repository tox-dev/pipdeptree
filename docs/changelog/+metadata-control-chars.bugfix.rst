Replace control characters in package names, versions, metadata header values, ``direct_url.json`` fields and lock
file strings with U+FFFD, so a package can no longer send escape sequences to the terminal, end a Graphviz label early
with a NUL byte or crash ``--summary -o rich`` by :user:`gaborbernat`.
