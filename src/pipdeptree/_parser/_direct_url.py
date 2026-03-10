from __future__ import annotations

import json
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from importlib.metadata import Distribution


def get_direct_url(distribution: Distribution) -> DirectUrl | None:
    """
    Read and parse direct_url.json from a distribution's metadata.

    :param distribution: Distribution to read direct_url.json from
    :returns: Parsed DirectUrl object, or None if file doesn't exist or cannot be parsed
    """
    try:
        return parse_direct_url_json(json_str) if (json_str := distribution.read_text("direct_url.json")) else None
    except (UnicodeDecodeError, DirectUrlValidationError):
        return None


def parse_direct_url_json(json_str: str) -> DirectUrl:
    """
    Parse direct_url.json content into structured DirectUrl object.

    :param json_str: JSON string content from direct_url.json metadata file
    :returns: Parsed DirectUrl object
    :raises DirectUrlValidationError: If JSON is malformed or missing required fields
    """
    try:
        data = json.loads(json_str)
    except json.JSONDecodeError as e:
        msg = f"Invalid JSON: {e}"
        raise DirectUrlValidationError(msg) from e
    if not isinstance(data, dict):
        msg = "direct_url.json must be a JSON object"
        raise DirectUrlValidationError(msg)
    if "url" not in data:
        msg = "Missing required 'url' field"
        raise DirectUrlValidationError(msg)
    infos = [
        _parse_vcs_info(data["vcs_info"]) if "vcs_info" in data and isinstance(data["vcs_info"], dict) else None,
        _parse_archive_info(data["archive_info"])
        if "archive_info" in data and isinstance(data["archive_info"], dict)
        else None,
        _parse_dir_info(data["dir_info"]) if "dir_info" in data and isinstance(data["dir_info"], dict) else None,
    ]
    non_none_infos = [info for info in infos if info is not None]
    if not non_none_infos:
        msg = "Missing one of vcs_info, archive_info, or dir_info"
        raise DirectUrlValidationError(msg)
    if len(non_none_infos) > 1:
        msg = "More than one of vcs_info, archive_info, or dir_info specified"
        raise DirectUrlValidationError(msg)
    return DirectUrl(
        url=data["url"],
        info=non_none_infos[0],
        subdirectory=data.get("subdirectory"),
    )


def _parse_vcs_info(vcs_data: dict) -> VcsInfo:
    """Parse vcs_info dictionary into VcsInfo object."""
    if "vcs" not in vcs_data:
        msg = "Missing required vcs_info.vcs field"
        raise DirectUrlValidationError(msg)
    if "commit_id" not in vcs_data:
        msg = "Missing required vcs_info.commit_id field"
        raise DirectUrlValidationError(msg)
    return VcsInfo(
        vcs=vcs_data["vcs"],
        commit_id=vcs_data["commit_id"],
        requested_revision=vcs_data.get("requested_revision"),
    )


def _parse_archive_info(archive_data: dict) -> ArchiveInfo:
    """Parse archive_info dictionary into ArchiveInfo object."""
    return ArchiveInfo(hash=archive_data.get("hash"))


def _parse_dir_info(dir_data: dict) -> DirInfo:
    """Parse dir_info dictionary into DirInfo object."""
    editable = dir_data.get("editable", False)
    if not isinstance(editable, bool):
        msg = "dir_info.editable must be a boolean"
        raise DirectUrlValidationError(msg)
    return DirInfo(editable=editable)


class DirectUrlValidationError(Exception):
    """Raised when direct_url.json has invalid structure or missing required fields."""


@dataclass
class DirectUrl:
    """
    PEP 610 direct_url.json metadata representation.

    See: https://peps.python.org/pep-0610/
    """

    url: str
    info: VcsInfo | ArchiveInfo | DirInfo
    subdirectory: str | None = None

    def is_editable(self) -> bool:
        """Check if this is an editable installation."""
        return isinstance(self.info, DirInfo) and self.info.editable


@dataclass
class VcsInfo:
    """
    Version control system information from direct_url.json.

    See PEP 610: https://peps.python.org/pep-0610/
    """

    vcs: str
    commit_id: str
    requested_revision: str | None = None


@dataclass
class ArchiveInfo:
    """
    Archive information from direct_url.json.

    See PEP 610: https://peps.python.org/pep-0610/
    """

    hash: str | None = None


@dataclass
class DirInfo:
    """
    Directory information from direct_url.json.

    See PEP 610: https://peps.python.org/pep-0610/
    """

    editable: bool = False


__all__ = [
    "ArchiveInfo",
    "DirInfo",
    "DirectUrl",
    "DirectUrlValidationError",
    "VcsInfo",
    "get_direct_url",
    "parse_direct_url_json",
]
