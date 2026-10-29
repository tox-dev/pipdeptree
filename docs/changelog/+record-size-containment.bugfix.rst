Count a ``RECORD`` row toward ``--computed size`` and ``--summary`` only when it resolves to a regular file inside the
installation prefix of the site directory, so absolute paths, ``..`` segments and symbolic links in ``RECORD`` no longer
add the size of files elsewhere on the machine.
