Reject a package ``Name`` or ``Version`` longer than 255 bytes: an installed distribution with one is reported as
invalid metadata and left out, and ``from-lock`` stops with an error. Warnings and reverse JSON copy the name once per
requirement or edge, so one long name in a ``METADATA`` or lock file of 100 to 200 KB made pipdeptree write hundreds of
megabytes and use close to 2 GB of memory.
