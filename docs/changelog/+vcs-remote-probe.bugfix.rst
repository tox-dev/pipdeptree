Stop ``--freeze`` from checking whether a local git, hg or bzr remote exists and from resolving its links; pipdeptree
writes the remote as a ``file://`` URL as configured, so the output no longer shows which paths exist on the host.
