Stop ``from-index`` from looking for a Nab workspace above the project it generates in the temporary directory, so a
``nab.toml`` or ``pyproject.toml`` there can no longer add local sources to the resolve; a lone ``--pyproject`` still
finds its workspace.
