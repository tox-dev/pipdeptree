``from-index --requirements`` errors on Windows now name the requirements file as a plain ``C:\...`` path instead of
the ``\\?\C:\...`` form. This covers ``file:line: invalid requirement``, ``recursive requirements include`` and the
nesting depth error.
