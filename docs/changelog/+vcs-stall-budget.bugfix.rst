Spend at most 10 seconds per run on ``git``, ``hg``, ``svn`` and ``bzr`` commands that time out while freezing editable
installs. Each record pointing at a stalled repository used to wait out its own 5 second timeout, so four such records
took 20 seconds. Commands that finish in time do not count toward the limit. Once a run uses it up, later commands fail
without starting, and each record whose lookup timed out gets a ``# Editable ... install whose lookup timed out``
comment instead of the one for an install with no version control or no remote. A timed-out ``git`` lookup still lets
``hg``, ``svn`` or ``bzr`` find the checkout.
