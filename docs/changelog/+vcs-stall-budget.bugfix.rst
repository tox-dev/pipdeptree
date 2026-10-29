Spend at most 10 seconds per run on ``git``, ``hg``, ``svn`` and ``bzr`` commands that time out while freezing editable
installs. Each record pointing at a stalled repository used to wait out its own 5 second timeout, so four such records
took 20 seconds. Commands that finish in time do not count toward the limit, and once a run uses it up, later commands
fail without starting. A record whose lookup timed out now gets a ``# Editable ... install whose lookup timed out``
comment. Before, it printed the comment for an install with no version control or no remote, which hid the timeout. A
timed-out ``git`` lookup still lets the other systems find the checkout. See :issue:`759`.
