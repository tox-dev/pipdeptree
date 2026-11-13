"""Expose the release version provided by the Rust extension."""

from __future__ import annotations

from typing import Final

from ._rust import version as _version

#: Version string from the Rust extension.
version: Final[str] = _version()
#: The version the Rust extension was built with, as shown by ``pipdeptree --version``.
__version__: Final[str] = version
#: Dot-separated version parts with numeric parts converted to integers.
version_tuple: Final[tuple[int | str, ...]] = tuple(
    int(part) if part.isdigit() else part for part in version.split(".")
)
#: Alias for ``version_tuple``.
__version_tuple__: Final[tuple[int | str, ...]] = version_tuple
#: Commit identifier, unavailable in the Rust build.
commit_id: Final[None] = None
#: Alias for ``commit_id``.
__commit_id__: Final[None] = commit_id

__all__ = [
    "__commit_id__",
    "__version__",
    "__version_tuple__",
    "commit_id",
    "version",
    "version_tuple",
]
