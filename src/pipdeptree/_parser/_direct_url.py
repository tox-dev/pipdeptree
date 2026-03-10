from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
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
    data = _load_and_validate_json(json_str)
    _validate_required_fields(data)
    info = _parse_info_block(data)
    return DirectUrl(
        url=data["url"],
        info=info,
        subdirectory=data.get("subdirectory"),
    )


def _load_and_validate_json(json_str: str) -> dict:
    """Load and validate JSON structure."""
    try:
        data = json.loads(json_str)
    except json.JSONDecodeError as e:
        msg = f"Invalid JSON: {e}"
        raise DirectUrlValidationError(msg) from e
    if not isinstance(data, dict):
        msg = "direct_url.json must be a JSON object"
        raise DirectUrlValidationError(msg)
    return data


def _validate_required_fields(data: dict) -> None:
    """Validate required fields and their types."""
    if "url" not in data:
        msg = "Missing required 'url' field"
        raise DirectUrlValidationError(msg)
    if not isinstance(data["url"], str):
        msg = "url must be a string"
        raise DirectUrlValidationError(msg)
    subdirectory = data.get("subdirectory")
    if subdirectory is not None and not isinstance(subdirectory, str):
        msg = "subdirectory must be a string"
        raise DirectUrlValidationError(msg)


def _parse_info_block(data: dict) -> VcsInfo | ArchiveInfo | DirInfo:
    """Parse and validate info block (vcs_info, archive_info, or dir_info)."""
    infos = []
    for key, parser in [
        ("vcs_info", _parse_vcs_info),
        ("archive_info", _parse_archive_info),
        ("dir_info", _parse_dir_info),
    ]:
        if key in data:
            if not isinstance(data[key], dict):
                msg = f"{key} must be a dict"
                raise DirectUrlValidationError(msg)
            infos.append(parser(data[key]))
    if not infos:
        msg = "Missing one of vcs_info, archive_info, or dir_info"
        raise DirectUrlValidationError(msg)
    if len(infos) > 1:
        msg = "More than one of vcs_info, archive_info, or dir_info specified"
        raise DirectUrlValidationError(msg)
    return infos[0]


def _parse_vcs_info(vcs_data: dict) -> VcsInfo:
    """Parse vcs_info dictionary into VcsInfo object."""
    if "vcs" not in vcs_data:
        msg = "Missing required vcs_info.vcs field"
        raise DirectUrlValidationError(msg)
    if not isinstance(vcs_data["vcs"], str):
        msg = "vcs_info.vcs must be a string"
        raise DirectUrlValidationError(msg)
    if "commit_id" not in vcs_data:
        msg = "Missing required vcs_info.commit_id field"
        raise DirectUrlValidationError(msg)
    if not isinstance(vcs_data["commit_id"], str):
        msg = "vcs_info.commit_id must be a string"
        raise DirectUrlValidationError(msg)
    requested_revision = vcs_data.get("requested_revision")
    if requested_revision is not None and not isinstance(requested_revision, str):
        msg = "vcs_info.requested_revision must be a string"
        raise DirectUrlValidationError(msg)
    return VcsInfo(
        vcs=vcs_data["vcs"],
        commit_id=vcs_data["commit_id"],
        requested_revision=requested_revision,
    )


def _parse_archive_info(archive_data: dict) -> ArchiveInfo:
    """Parse archive_info dictionary into ArchiveInfo object."""
    hash_value = archive_data.get("hash")
    if hash_value is not None:
        if not isinstance(hash_value, str):
            msg = "archive_info.hash must be a string"
            raise DirectUrlValidationError(msg)
        if "=" not in hash_value or len(hash_value.split("=", 1)) != 2:
            msg = f"invalid archive_info.hash format: {hash_value!r}"
            raise DirectUrlValidationError(msg)
    hashes: dict[str, str] = {}
    if raw_hashes := archive_data.get("hashes"):
        if not isinstance(raw_hashes, dict):
            msg = "archive_info.hashes must be a dict"
            raise DirectUrlValidationError(msg)
        hashes = {str(k): str(v) for k, v in raw_hashes.items()}
    if not hashes and hash_value:
        algo, digest = hash_value.split("=", 1)
        hashes = {algo: digest}
    return ArchiveInfo(hash=hash_value, hashes=hashes)


def _parse_dir_info(dir_data: dict) -> DirInfo:
    """Parse dir_info dictionary into DirInfo object."""
    editable = dir_data.get("editable", False)
    if not isinstance(editable, bool):
        msg = "dir_info.editable must be a boolean"
        raise DirectUrlValidationError(msg)
    return DirInfo(editable=editable)


class DirectUrlValidationError(ValueError):
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

    @property
    def redacted_url(self) -> str:
        """Strip user:pass@ credentials from URL, preserving git@ and ${VAR} patterns."""
        return _redact_url(self.url)


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
    hashes: dict[str, str] = field(default_factory=dict)


@dataclass
class DirInfo:
    """
    Directory information from direct_url.json.

    See PEP 610: https://peps.python.org/pep-0610/
    """

    editable: bool = False


_CREDENTIAL_RE = re.compile(r"([a-z+]+://)([^@]+)@", re.IGNORECASE)


def _redact_url(url: str) -> str:
    """Strip credentials from URL, preserving env vars (e.g. ${TOKEN}@)."""
    match = _CREDENTIAL_RE.match(url)
    if not match:
        return url
    userinfo = match.group(2)
    if userinfo.startswith("${"):
        return url
    if ":" in userinfo:
        return f"{match.group(1)}{url[match.end() :]}"
    return f"{match.group(1)}****@{url[match.end() :]}"


__all__ = [
    "ArchiveInfo",
    "DirInfo",
    "DirectUrl",
    "DirectUrlValidationError",
    "VcsInfo",
    "get_direct_url",
    "parse_direct_url_json",
]
