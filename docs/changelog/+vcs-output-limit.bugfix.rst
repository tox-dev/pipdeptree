Read at most 1 MiB of output from each ``git``, ``hg``, ``svn`` and ``bzr`` command that freeze runs, so a repository
config that makes ``git`` print gigabytes no longer grows pipdeptree's memory with it. A command that prints more counts
as failed (:issue:`760`).
