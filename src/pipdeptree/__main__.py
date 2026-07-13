"""Run pipdeptree as a Python module."""

from __future__ import annotations

from pipdeptree._runner import main

if __name__ == "__main__":
    raise SystemExit(main())

__all__ = ["main"]
