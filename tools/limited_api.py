#!/usr/bin/env python3  # ruff:ignore[shebang-not-executable]  # Meson uses its interpreter for this script.
"""Prints whether the build may target the stable ABI."""

from __future__ import annotations

import os
import sys
import sysconfig


def main() -> None:
    allowed = (
        os.environ.get("PIPDEPTREE_ABI3") == "1"
        and sys.implementation.name == "cpython"
        and not sysconfig.get_config_var("Py_GIL_DISABLED")
    )
    print(str(allowed).lower())  # ruff:ignore[print]  # Meson reads the option value off this output.


if __name__ == "__main__":
    main()


__all__ = []
