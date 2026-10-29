``from-index --requirements`` now reports a line it cannot parse as a requirement by file path and line number, for
example ``/work/netrc:2: invalid requirement``, instead of the parser message that repeats the line. An include that
pointed at a file holding credentials, such as ``-r ~/.netrc``, printed its first unparsable line, password included.
Requirements passed on the command line keep the full parser message.
