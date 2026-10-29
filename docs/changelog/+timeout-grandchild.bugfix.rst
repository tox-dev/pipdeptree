Stop waiting for a command at its timeout even when a process it started still holds its output open. A ``poetry``
wrapper script that ran the real command without ``exec`` used to keep the environment probe waiting until that command
exited, past the 5 second timeout; the same applied to the VCS commands that freeze runs and to ``dot``. Such a command
now counts as timed out at the deadline, also when it exited first and left the other process running. pipdeptree does
not stop that process.
