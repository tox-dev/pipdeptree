Print the warnings the ``from-index`` resolver logs, such as a skipped release whose metadata does not parse, as a
pipdeptree warning that ``--warn silence`` hides, with control characters replaced by U+FFFD. The same replacement now
applies to Python errors the resolver raises. Before, Python wrote these warnings to stderr with the index's escape
sequences intact, even under ``--warn silence``.
