Stop ``--freeze`` from running hooks, aliases and extensions defined in an editable install's ``.hg/hgrc``: ``hg``
now runs with ``HGRCSKIPREPO=1``, and pipdeptree reads ``paths.default`` from that file as plain text.
