Stop ``--freeze`` from running hooks, aliases or extensions from an editable install's ``.hg/hgrc``; pipdeptree runs
``hg`` with ``HGRCSKIPREPO=1`` and reads ``paths.default`` from that file as plain text.
