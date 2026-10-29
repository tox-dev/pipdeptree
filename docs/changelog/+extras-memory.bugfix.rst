Keep memory use linear in the size of a ``Requires-Dist`` line that requests many extras and that many extras activate;
pipdeptree no longer stores one copy of the requested extras per activating extra.
