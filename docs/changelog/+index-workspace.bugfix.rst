Stop ``from-index`` from looking for a Nab workspace above the project it generates in the temporary directory, so a
``nab.toml`` or ``pyproject.toml`` there no longer adds local sources to the resolve. A lone ``--pyproject`` still finds
its workspace.
