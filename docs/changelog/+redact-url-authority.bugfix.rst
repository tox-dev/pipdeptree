Drop the user name and password from a direct URL in freeze output when the scheme holds a digit, ``-`` or ``.``, such
as ``static-http`` or ``s3``. Before, pipdeptree printed such a URL as recorded, credentials included. Also drop them
when the user name or password holds an ``@``. pipdeptree used to cut the authority at the first ``@``, so the rest of
the password showed up as part of the host. The host now starts after the last ``@``, as pip and ``urllib`` read it, and
an ``@`` in the path, query or fragment no longer counts. The same rule applies to the remote of an editable VCS
checkout.
