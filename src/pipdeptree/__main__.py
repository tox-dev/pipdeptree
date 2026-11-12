"""Run pipdeptree as a Python module."""

from __future__ import annotations

# Direct file execution has no package context for the relative import.
if __package__ is None:
    __package__ = "pipdeptree"

from ._runner import main

if __name__ == "__main__":
    raise SystemExit(main())

__all__ = []
