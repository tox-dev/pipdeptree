Reject a package ``Name`` or ``Version`` longer than 255 bytes; pipdeptree leaves out an installed distribution with one
as invalid metadata, and ``from-lock`` stops with an error. Warnings and reverse JSON copy the name once per requirement
or edge, so one long name could make pipdeptree write hundreds of megabytes.
