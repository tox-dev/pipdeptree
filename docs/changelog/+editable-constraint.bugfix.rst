``from-index`` now rejects an ``-e`` / ``--editable`` line in a constraints file with ``source requirements cannot be
constraints``, the error a plain path or URL constraint already gets. Before, the editable project joined the resolve as
an extra top-level requirement, so its dependencies could change the versions picked for the real requirements. pip
refuses the same file.
