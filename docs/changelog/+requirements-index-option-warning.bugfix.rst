``from-index --requirements`` now prints a warning for each ``-i``, ``--index-url`` or ``--extra-index-url`` line in a
requirements file, naming the file, the line and the command-line flag to use instead. The resolve still ignores these
lines, and ``--warn fail`` makes the run exit with code 1. Before, it skipped them without a word, so a pip-compile file
for a private index resolved against PyPI with no hint why.
