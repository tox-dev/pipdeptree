from __future__ import annotations

from typing import TYPE_CHECKING

from packaging.version import InvalidVersion, Version

from ._direct_url import ArchiveInfo, VcsInfo, get_direct_url
from ._editable import find_egg_link, read_egg_link_location, url_to_path
from ._vcs import get_vcs_requirement

if TYPE_CHECKING:
    from importlib.metadata import Distribution

    from ._direct_url import DirectUrl


def distribution_to_specifier(distribution: Distribution) -> str:
    """
    Convert distribution to requirement specifier string.

    Handles regular packages (PEP 440 version specifiers), editable installs (PEP 610 direct_url.json and legacy
    .egg-link), and direct URL installs (PEP 440 direct references for VCS, archive, directory).

    For editable installs, probes filesystem for VCS information (git) to generate full VCS URL with commit hash,
    falling back to local path if VCS not detected.

    See:
    - PEP 440: https://peps.python.org/pep-0440/
    - PEP 610: https://peps.python.org/pep-0610/

    :param distribution: Distribution to convert
    :returns: Requirement specifier string

    Examples:
        Regular: "package==1.0.0"
        Editable (VCS): "-e git+https://github.com/user/repo@abc123#egg=package"
        Editable (no VCS): "-e /path/to/source"
        Direct URL: "package @ https://example.com/archive.tar.gz#sha256=..."

    """
    direct_url = get_direct_url(distribution)
    if direct_url:
        if direct_url.is_editable():
            location = url_to_path(direct_url.url)
            return _format_editable(location, distribution.metadata["Name"])
        return format_requirement(direct_url, distribution.metadata["Name"])
    if egg_link := find_egg_link(distribution.metadata["Name"]):
        location = read_egg_link_location(egg_link)
        return _format_editable(location, distribution.metadata["Name"])
    name = distribution.metadata["Name"]
    try:
        Version(distribution.version)
    except InvalidVersion:
        return f"{name}==={distribution.version}"
    else:
        return f"{name}=={distribution.version}"


def _format_editable(location: str, package_name: str) -> str:
    """
    Format editable install requirement with VCS detection.

    Probes location for VCS (git) and generates VCS URL if detected, otherwise uses local path.

    :param location: Filesystem path to source directory
    :param package_name: Package name
    :returns: Editable requirement string
    """
    if vcs_req := get_vcs_requirement(location, package_name):
        return f"-e {vcs_req}"
    return f"-e {location}"


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
    if isinstance(direct_url.info, VcsInfo):
        requirement += f"{direct_url.info.vcs}+{direct_url.url}@{direct_url.info.commit_id}"
    elif isinstance(direct_url.info, ArchiveInfo):
        requirement += direct_url.url
        if direct_url.info.hash:
            requirement += f"#{direct_url.info.hash}"
    else:
        requirement += direct_url.url
    if direct_url.subdirectory:
        requirement += f"{'&' if '#' in requirement else '#'}subdirectory={direct_url.subdirectory}"
    return requirement


__all__ = [
    "distribution_to_specifier",
    "format_requirement",
]
