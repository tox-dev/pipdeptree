Look up ``git``, ``hg``, ``svn`` and ``bzr`` on ``PATH`` from the directory pipdeptree runs in when freezing an editable
install. On Unix an empty or relative ``PATH`` entry used to find a program inside the editable project, so a file named
``git`` or ``bzr`` there ran in place of the real tool (:issue:`772`).
