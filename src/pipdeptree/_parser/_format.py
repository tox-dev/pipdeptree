from __future__ import annotations

from typing import TYPE_CHECKING

from ._direct_url import get_direct_url
from ._editable import find_egg_link, read_egg_link_location, url_to_path

if TYPE_CHECKING:
    from importlib.metadata import Distribution

    from ._direct_url import DirectUrl


def distribution_to_specifier(distribution: Distribution) -> str:
    """
    Convert distribution to requirement specifier string.

    Handles regular packages (PEP 440 version specifiers), editable installs (PEP 610 direct_url.json and legacy
    .egg-link), and direct URL installs (PEP 440 direct references for VCS, archive, directory).

    See:
    - PEP 440: https://peps.python.org/pep-0440/
    - PEP 610: https://peps.python.org/pep-0610/

    :param distribution: Distribution to convert
    :returns: Requirement specifier string

    Examples:
        Regular: "package==1.0.0"
        Editable: "-e /path/to/source"
        Direct URL: "package @ https://example.com/archive.tar.gz#sha256=..."

    """
    if (direct_url := get_direct_url(distribution)) and direct_url.is_editable():
        return f"-e {url_to_path(direct_url.url)}"
    if egg_link := find_egg_link(distribution.metadata["Name"]):
        return f"-e {read_egg_link_location(egg_link)}"
    name = distribution.metadata["Name"]
    if direct_url:
        return format_requirement(direct_url, name)
    return f"{name}=={distribution.version}"


def format_requirement(direct_url: DirectUrl, package_name: str) -> str:
    """
    Format DirectUrl as PEP 440 direct reference requirement.

    Implements PEP 440 direct reference syntax for VCS, archive, and local directory installs. See:
    https://peps.python.org/pep-0440/#direct-references

    :param direct_url: DirectUrl object to format (from PEP 610 direct_url.json)
    :param package_name: Package name to include in requirement string
    :returns: Formatted requirement string

    Examples:
        VCS: "package @ git+https://github.com/user/repo@abc123"
        Archive: "package @ https://example.com/file.tar.gz#sha256=..."
        Directory: "package @ file:///path/to/dir"

    """
    requirement = f"{package_name} @ "
    if direct_url.vcs_info:
        requirement += f"{direct_url.vcs_info.vcs}+{direct_url.url}@{direct_url.vcs_info.commit_id}"
    elif direct_url.archive_info:
        requirement += direct_url.url
        if direct_url.archive_info.hash_value:
            requirement += f"#{direct_url.archive_info.hash_value}"
    else:
        requirement += direct_url.url
    if direct_url.subdirectory:
        requirement += f"{'&' if '#' in requirement else '#'}subdirectory={direct_url.subdirectory}"
    return requirement


__all__ = [
    "distribution_to_specifier",
    "format_requirement",
]
