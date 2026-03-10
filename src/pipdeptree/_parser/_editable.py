from __future__ import annotations

import locale
import site
from pathlib import Path
from typing import TYPE_CHECKING
from urllib.parse import unquote, urlparse
from urllib.request import url2pathname

from ._direct_url import get_direct_url

if TYPE_CHECKING:
    from importlib.metadata import Distribution


def get_editable_location(distribution: Distribution) -> str | None:
    """
    Get source location for an editable installation.

    Tries modern PEP 610 direct_url.json first, then falls back to legacy .egg-link files.
    See: https://peps.python.org/pep-0610/

    :param distribution: Distribution to check
    :returns: Path to editable source location, or None if package is not editable
    """
    if (direct_url := get_direct_url(distribution)) and direct_url.is_editable():
        return url_to_path(direct_url.url)
    if egg_link := find_egg_link(distribution.metadata["Name"]):
        return read_egg_link_location(egg_link)
    return None


def url_to_path(url: str) -> str:
    """
    Convert file:// URL to filesystem path.

    :param url: URL to convert (must have file:// scheme)
    :returns: Filesystem path
    :raises ValueError: If URL doesn't use file:// scheme
    """
    parsed = urlparse(url)
    if parsed.scheme != "file":
        msg = f"Expected file:// URL, got {parsed.scheme}://"
        raise ValueError(msg)
    path = unquote(parsed.path)
    if parsed.netloc:  # pragma: win32 cover
        return url2pathname(f"//{parsed.netloc}{path}")  # pragma: win32 cover
    return url2pathname(path)


def find_egg_link(package_name: str) -> Path | None:
    """
    Find .egg-link file for legacy editable installations.

    :param package_name: Name of package to search for
    :returns: Path to .egg-link file if found, None otherwise
    """
    site_dirs = site.getsitepackages() if hasattr(site, "getsitepackages") else []
    if user_site := site.getusersitepackages():
        site_dirs.append(user_site)
    for site_dir in site_dirs:
        if (egg_link := Path(site_dir) / f"{package_name}.egg-link").exists():
            return egg_link
    return None


def read_egg_link_location(egg_link_path: Path) -> str:
    """
    Read source directory path from .egg-link file.

    The first line of an .egg-link file contains the absolute path to the source directory.

    :param egg_link_path: Path to .egg-link file
    :returns: Source directory path
    """
    with egg_link_path.open("r", encoding=locale.getpreferredencoding(do_setlocale=False)) as f:
        return f.readline().rstrip()


__all__ = [
    "find_egg_link",
    "get_editable_location",
    "read_egg_link_location",
    "url_to_path",
]
