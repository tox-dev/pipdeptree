``from-index --requirements`` now stops with ``requirements include nested deeper than 100 levels`` and the path of the
file at that depth when ``-r`` and ``-c`` includes nest more than 100 levels deep. A chain of about 14,000 files used to
overflow the stack and kill the process with a segmentation fault and no message.
