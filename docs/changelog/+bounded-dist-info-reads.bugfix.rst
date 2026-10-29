Read ``direct_url.json``, ``RECORD``, ``.egg-link`` files, ``.hg/hgrc`` and ``.svn/entries`` only when they are regular
files of at most 16 MiB, as ``METADATA`` already was. A FIFO in place of ``direct_url.json`` or ``RECORD`` made
``--freeze`` or ``--computed size`` wait for a writer, and a link to ``/dev/zero`` or a multi-gigabyte file made them
allocate until the allocator or the OOM killer stopped the run. Freeze now prints the version pin for such a package,
its size counts as zero, and an unreadable ``.egg-link``, ``hgrc`` or ``entries`` file counts as absent.
