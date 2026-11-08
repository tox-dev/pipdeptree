"""
Programmatic access to pipdeptree.

Use :func:`render` when stdout is unavailable or when a dependency tree is needed as a string. Text results implement
the notebook rich-display protocol while retaining normal :class:`str` behavior.
"""

from __future__ import annotations

from ._api import render
from .version import __version__

__all__ = [
    "__version__",
    "render",
]
