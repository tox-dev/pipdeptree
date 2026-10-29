Compute the ``--summary`` max depth in linear time, counting a dependency cycle as all of its packages, so a dozen
packages that require each other no longer stall the command.
