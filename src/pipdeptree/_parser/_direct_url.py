from __future__ import annotations

import json
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

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
    return DirectUrl(
        url=data["url"],
        vcs_info=_parse_vcs_info(data["vcs_info"])
        if "vcs_info" in data and isinstance(data["vcs_info"], dict)
        else None,
        archive_info=(
            ArchiveInfo(hash_value=data["archive_info"].get("hash"))
            if "archive_info" in data and isinstance(data["archive_info"], dict)
            else None
        ),
        dir_info=(
            DirInfo(editable=data["dir_info"].get("editable", False))
            if "dir_info" in data and isinstance(data["dir_info"], dict)
            else None
        ),
        subdirectory=data.get("subdirectory"),
    )


def _parse_vcs_info(vcs_data: dict) -> VcsInfo:
    """Parse vcs_info dictionary into VcsInfo object."""
    return VcsInfo(
        vcs=vcs_data.get("vcs", ""),
        commit_id=vcs_data.get("commit_id", ""),
        requested_revision=vcs_data.get("requested_revision"),
        resolved_revision=vcs_data.get("resolved_revision"),
        resolved_revision_type=(
            vcs_data.get("resolved_revision_type")
            if vcs_data.get("resolved_revision_type") in {"branch", "tag"}
            else None
        ),
    )


class DirectUrlValidationError(Exception):
    """Raised when direct_url.json has invalid structure or missing required fields."""


@dataclass
class DirectUrl:
    """
    PEP 610 direct_url.json metadata representation.

    See: https://peps.python.org/pep-0610/
    """

    url: str
    dir_info: DirInfo | None = None
    vcs_info: VcsInfo | None = None
    archive_info: ArchiveInfo | None = None
    subdirectory: str | None = None

    @property
    def info_type(self) -> Literal["vcs", "archive", "dir"] | None:
        """Return the type of direct URL (vcs, archive, or dir)."""
        if self.vcs_info:
            return "vcs"
        if self.archive_info:
            return "archive"
        if self.dir_info:
            return "dir"
        return None

    def is_editable(self) -> bool:
        """Check if this is an editable installation."""
        return bool(self.dir_info and self.dir_info.editable)


@dataclass
class VcsInfo:
    """
    Version control system information from direct_url.json.

    See PEP 610: https://peps.python.org/pep-0610/
    """

    vcs: str
    commit_id: str
    requested_revision: str | None = None
    resolved_revision: str | None = None
    resolved_revision_type: Literal["branch", "tag"] | None = None


@dataclass
class ArchiveInfo:
    """
    Archive information from direct_url.json.

    See PEP 610: https://peps.python.org/pep-0610/
    """

    hash_value: str | None = None


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
