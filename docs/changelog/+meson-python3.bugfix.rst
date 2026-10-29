``meson setup`` works on systems that ship ``python3`` without a ``python`` command. The stable ABI check now runs under
the interpreter that runs Meson, the same one the build targets, instead of the first ``python`` on ``PATH``.
