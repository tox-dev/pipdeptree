Reject a ``Requires-Dist`` marker, or a lock package ``marker``, longer than 1024 bytes or with more than 16 ``extra``
comparisons before parsing it. Parsing builds a decision diagram that can double in size with each clause of ``extra``
alternatives, and a marker of about 900 bytes took 12 seconds and 15 GB of memory to parse. Installed metadata reports
such a marker with the ``Invalid requirement found`` warning; ``from-lock`` stops with an error naming the package.
pipdeptree also collects the extras a marker names by visiting each node of the parsed marker once, instead of
converting it to disjunctive normal form, and ``from-lock`` stops with an error when the ``name`` of a ``dependencies``
entry is not a project name.
