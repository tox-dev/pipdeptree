Spend at most 10 seconds per run on ``git``, ``hg``, ``svn`` and ``bzr`` commands that time out while freezing editable
installs. Each record pointing at a stalled repository used to wait out its own 5 second timeout. A record whose lookup
timed out now gets a ``# Editable ... install whose lookup timed out`` comment instead of the one for an install with no
version control (:issue:`759`).
