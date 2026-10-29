Write each character that stdout's encoding cannot represent as a backslash escape, such as ``\xe9`` for ``é`` under
``PYTHONIOENCODING=ascii``, so package metadata no longer crashes pipdeptree with ``UnicodeEncodeError`` before it
prints the tree or its warnings. Output redirected on Windows hit this for any character outside the ANSI code page.
