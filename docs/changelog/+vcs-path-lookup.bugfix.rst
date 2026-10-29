Look up ``git``, ``hg``, ``svn`` and ``bzr`` on ``PATH`` from the directory pipdeptree runs in when freezing an editable
install. On Unix the child process changes into the editable project before it searches ``PATH``, so an empty or
relative entry, such as a trailing separator, ``.`` or ``./bin``, used to find a program inside that project. A file
named ``git`` or ``bzr`` there then ran in place of the real tool, with the permissions of the user who ran pipdeptree.
pipdeptree now resolves the program itself and skips entries without an executable file, as the system lookup does. If
no entry holds the tool, freeze reports it as missing. Windows already searched from pipdeptree's own directory and
keeps its behavior. See :issue:`772`.
