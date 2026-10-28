Escape package metadata in Mermaid output. Quotes, ``#``, ``&``, ``<``, ``>``, backticks and control characters in node
labels become Mermaid entity codes, and a package whose canonical name is empty or has characters other than lowercase
letters, digits and ``-`` gets a generated ``package_<n>`` node id, so metadata can no longer add statements to the
diagram.
