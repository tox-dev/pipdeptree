Percent-encode whitespace and control characters in the URLs, VCS remotes and subdirectories of freeze output, and write
an editable location that holds one as a ``file://`` URL. Before, an installed distribution could add a line such as
``--index-url`` to the requirements file through its ``direct_url.json``, ``.egg-link`` or a shipped checkout, and an
escape sequence reached the terminal. An editable location with a space now installs with ``pip install -r`` instead
of pip reading only the text before the space.
