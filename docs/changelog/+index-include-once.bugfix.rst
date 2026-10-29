``from-index --requirements`` now parses a requirements file at most once as requirements and once as constraints,
however many ``-r`` and ``-c`` lines include it. It used to parse such a file again for every include path, so a layout
that repeats an include at several nesting levels took time multiplied by the repeat count at each level, and the
resolver received each requirement once per path (:issue:`771`).
