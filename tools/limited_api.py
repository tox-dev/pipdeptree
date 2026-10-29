#!/usr/bin/env python3  # ruff:ignore[shebang-not-executable]  # Executable, it would run the python3 on PATH.
"""Prints whether the build may target the stable ABI."""

from __future__ import annotations

import os
import sys
import sysconfig
from typing import Final


def main() -> None:
    print(str(_allowed()).lower())  # ruff:ignore[print]  # Meson reads the option value off this output.


def _allowed() -> bool:
    return (
        os.environ.get("PIPDEPTREE_ABI3") == "1"
        and sys.implementation.name == "cpython"
        and not sysconfig.get_config_var("Py_GIL_DISABLED")
    )


if __name__ == "__main__":
    main()


__all__: Final = []
