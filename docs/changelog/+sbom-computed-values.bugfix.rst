``-o cyclonedx-json`` writes each ``--computed`` value as plain text, with one property per name for
``unique-deps-names``. Before, a string kept its JSON quotes (``"\"2.1 KB\""``) and a list became one JSON array
string. ``--depth`` help names the formats it applies to, and ``pipdeptree.render()`` no longer calls ``svg`` and
``ps`` binary formats when it rejects them.
