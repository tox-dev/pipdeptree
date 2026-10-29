Keep memory use linear in the size of a ``Requires-Dist`` line that both requests many extras and is activated by
many extras; such a line no longer stores one copy of its requested extras per activating extra.
