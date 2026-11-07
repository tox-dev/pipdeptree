"""Expose the release version provided by the Rust extension."""

from __future__ import annotations

from typing import Final

from ._rust import version as _version

version: Final = _version()
#: The version the Rust extension was built with, as shown by ``pipdeptree --version``.
__version__: Final = version
version_tuple: Final = tuple(int(part) if part.isdigit() else part for part in version.split("."))
__version_tuple__: Final = version_tuple
commit_id: Final = None
__commit_id__: Final = commit_id

__all__ = [
    "__version__",
]
