``from-index`` on Windows now hands a local source to the resolver as a plain ``C:\...`` path instead of the
``\\?\C:\...`` form, so a project whose ``pyproject.toml`` sets ``backend-path = ["."]`` can build its metadata. The
build frontend joined ``.`` to the ``\\?\`` path, which Windows does not normalize, and rejected the entry as missing.
