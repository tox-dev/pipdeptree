Skip the interpreter that ``poetry env info --executable`` reports when it lies inside the project in the working
directory, such as a ``.venv`` next to the ``pyproject.toml``. With no virtual or conda environment active, a plain
``pipdeptree`` and ``--python auto`` used to run that interpreter, so a cloned repository that committed both ran its
own program as the user. A plain run now inspects the interpreter running pipdeptree, and ``--python auto`` fails to
detect an environment. To inspect that environment, activate it or pass its interpreter to ``--python``.
