Drop the user name and password from a direct URL in freeze output when the scheme holds a digit, ``-`` or ``.``, such
as ``static-http``, or when the user name or password holds an ``@``. The host now starts after the last ``@`` of the
authority, as pip reads it (:issue:`773`).
