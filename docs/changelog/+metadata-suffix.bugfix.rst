Build the ``--metadata`` and ``--computed`` suffix of a package once per ``text`` or ``rich`` tree instead of once per
line that shows the package, so the time of a tree no longer grows with the stored length of a metadata value on every
repeated line.
