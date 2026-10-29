Escape package metadata in Mermaid output, so it can no longer add statements to the diagram. Quotes, ``#``, ``&``,
``<``, ``>``, backticks and control characters in node labels become entity codes, and a package whose canonical name is
empty or holds characters other than lowercase letters, digits and ``-`` gets a ``package_<n>`` node id.
