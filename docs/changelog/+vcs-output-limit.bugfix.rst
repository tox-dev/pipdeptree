Read at most 1 MiB of output from each ``git``, ``hg``, ``svn`` and ``bzr`` command that freeze runs for an editable
install. Before, pipdeptree kept everything a command printed. A repository config that repeats remote keys through
includes made ``git`` print more than a gigabyte within its timeout, and pipdeptree's memory grew with it. A command
that prints more than the limit on stdout or stderr now counts as failed, and freeze prints the record as it does for
any other failed VCS command. Closing the pipe at the limit also ends a command that keeps writing, so it no longer runs
until its timeout.
