``--extras active`` now leaves an extra off when an installed dependency does not satisfy its version specifier. Before,
an extra declaring ``bar>=99`` turned on with ``bar 1.0`` installed, so ``--warn fail`` failed on a conflict from an
unrequested extra.
