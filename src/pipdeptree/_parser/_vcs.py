from __future__ import annotations

import os
import re
import subprocess  # noqa: S404
import xml.etree.ElementTree as ET  # noqa: S405
from dataclasses import dataclass
from enum import Enum, auto
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable


class VcsError(Enum):
    NONE = auto()
    NO_VCS = auto()
    NO_REMOTE = auto()
    INVALID_REMOTE = auto()
    COMMAND_NOT_FOUND = auto()


@dataclass
class VcsResult:
    requirement: str | None
    vcs_name: str | None = None
    error: VcsError = VcsError.NONE


def get_vcs_requirement(location: str, package_name: str) -> VcsResult:
    """
    Detect VCS and generate requirement string for editable install.

    Probes directory for git/hg/svn/bzr repositories (including parent directories),
    picks the innermost repo root (matching pip's get_backend_for_dir logic).

    :param location: Filesystem path to source directory
    :param package_name: Package name for egg fragment
    :returns: VcsResult with requirement string and diagnostic info
    """
    roots: dict[str, Callable[[str, str, str], VcsResult]] = {}
    if git_root := _get_git_repo_root(location):
        roots[git_root] = _get_git_requirement
    if hg_root := _find_marker_root(location, ".hg"):
        roots[hg_root] = _get_hg_requirement
    if svn_root := _find_marker_root(location, ".svn"):
        roots[svn_root] = _get_svn_requirement
    if bzr_root := _find_marker_root(location, ".bzr"):
        roots[bzr_root] = _get_bzr_requirement
    if not roots:
        return VcsResult(None, error=VcsError.NO_VCS)
    innermost = ""
    for root in roots:
        if len(root) > len(innermost):
            innermost = root
    return roots[innermost](location, package_name, innermost)


def _get_git_repo_root(location: str) -> str | None:
    """Find git repository root from any subdirectory."""
    try:
        repo_root = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],  # noqa: S607
            cwd=location,
            capture_output=True,
            text=True,
            check=True,
            timeout=5,
        ).stdout.strip()
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return None
    except FileNotFoundError:
        return None
    else:
        return repo_root or None


def _find_marker_root(location: str, marker: str) -> str | None:
    """Walk up from location looking for a directory containing marker (e.g. .hg, .svn, .bzr)."""
    current = Path(location).resolve()
    while True:
        if (current / marker).is_dir():
            return str(current)
        parent = current.parent
        if parent == current:
            return None
        current = parent


# --- git backend ---


def _get_git_requirement(location: str, package_name: str, repo_root: str) -> VcsResult:
    try:
        remote_url = _get_git_remote_url(repo_root)
        if remote_url is None:
            return VcsResult(None, vcs_name="git", error=VcsError.NO_REMOTE)
        if not (commit_id := _get_git_commit_id(repo_root)):
            return VcsResult(None, vcs_name="git", error=VcsError.NO_REMOTE)
    except FileNotFoundError:
        return VcsResult(None, vcs_name="git", error=VcsError.COMMAND_NOT_FOUND)
    normalized = _normalize_git_url(remote_url, repo_root)
    if normalized is None:
        return VcsResult(None, vcs_name="git", error=VcsError.INVALID_REMOTE)
    return _build_vcs_result(
        vcs_name="git",
        remote_url=normalized,
        commit_id=commit_id,
        package_name=package_name,
        location=location,
        repo_root=repo_root,
        always_prefix=True,
    )


def _get_git_remote_url(repo_root: str) -> str | None:
    """Get git remote URL, preferring origin."""
    try:
        remotes_output = subprocess.run(
            ["git", "config", "--get-regexp", r"remote\..*\.url"],  # noqa: S607
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        ).stdout.strip()
        if not remotes_output:
            return None
        remotes = remotes_output.splitlines()
        found_remote = remotes[0]
        for remote in remotes:
            if remote.startswith("remote.origin.url "):
                found_remote = remote
                break
        parts = found_remote.split(" ", 1)
        return parts[1].strip() if len(parts) >= 2 and parts[1].strip() else None
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return None


def _get_git_commit_id(repo_root: str) -> str | None:
    """Get current git commit ID."""
    try:
        commit_id = subprocess.run(
            ["git", "rev-parse", "HEAD"],  # noqa: S607
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=True,
            timeout=5,
        ).stdout.strip()
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return None
    else:
        return commit_id or None


def _normalize_git_url(url: str, repo_root: str) -> str | None:
    """
    Normalize git URL to standard format matching pip's behavior.

    Returns None for URLs that don't match any known pattern.
    """
    if re.match(r"\w+://", url):
        return url
    path = Path(url) if _is_local_path(url) else Path(repo_root) / url
    if path.exists():
        return path.resolve().as_uri()
    if match := re.match(
        r"""
        ^
        (?P<user>\w+@)?    # Optional user, e.g. 'git@'
        (?P<host>[^/:]+):  # Server, e.g. 'github.com'
        (?P<path>\w[^:]*)  # Server-side path starting with alphanumeric (not Windows C:)
        $
        """,
        url,
        re.VERBOSE,
    ):
        return f"ssh://{match.group('user') or ''}{match.group('host')}/{match.group('path')}"
    return None


def _is_local_path(path: str) -> bool:
    """Check if path is a local filesystem path (starts with os.sep or has drive letter)."""
    if path.startswith(os.sep):
        return True
    return len(path) >= 2 and path[1] == ":" and path[0].isalpha()


# --- shared builder (first used by git, reused by hg/svn/bzr) ---


def _build_vcs_result(  # noqa: PLR0913, PLR0917
    vcs_name: str,
    remote_url: str,
    commit_id: str,
    package_name: str,
    location: str,
    repo_root: str,
    *,
    always_prefix: bool,
    include_subdirectory: bool = True,
) -> VcsResult:
    """Build VcsResult with requirement string from components."""
    safe_package_name = _normalize_egg_name(package_name)
    if always_prefix or not remote_url.lower().startswith(f"{vcs_name}:"):
        url = f"{vcs_name}+{remote_url}"
    else:
        url = remote_url
    result = f"{url}@{commit_id}#egg={safe_package_name}"
    if include_subdirectory and (subdirectory := _find_project_root(location, repo_root)):
        result += f"&subdirectory={subdirectory}"
    return VcsResult(result, vcs_name=vcs_name)


def _normalize_egg_name(name: str) -> str:
    return name.replace("-", "_")


def _find_project_root(location: str, repo_root: str) -> str | None:
    """
    Walk up from location to find the installable project root.

    Matches pip's find_path_to_project_root_from_repo_root:
    walks UP from location looking for pyproject.toml or setup.py.
    """
    current = Path(location).resolve()
    abs_root = Path(repo_root).resolve()
    while not _is_installable_dir(current):
        parent = Path(current).parent
        if parent == current:
            return None
        current = parent
    try:
        if Path(abs_root).samefile(current):
            return None
    except (ValueError, OSError):
        return None
    return os.path.relpath(current, abs_root)


def _is_installable_dir(path: str | Path) -> bool:
    p = Path(path)
    return p.is_dir() and ((p / "pyproject.toml").is_file() or (p / "setup.py").is_file())


# --- hg backend ---


def _get_hg_requirement(location: str, package_name: str, repo_root: str) -> VcsResult:
    try:
        remote_url = _get_hg_remote_url(repo_root)
        if remote_url is None:
            return VcsResult(None, vcs_name="hg", error=VcsError.NO_REMOTE)
        if _is_local_path(remote_url):
            remote_url = Path(remote_url).as_uri()
        if not (commit_id := _get_hg_commit_id(repo_root)):
            return VcsResult(None, vcs_name="hg", error=VcsError.NO_REMOTE)
    except FileNotFoundError:
        return VcsResult(None, vcs_name="hg", error=VcsError.COMMAND_NOT_FOUND)
    return _build_vcs_result(
        vcs_name="hg",
        remote_url=remote_url,
        commit_id=commit_id,
        package_name=package_name,
        location=location,
        repo_root=repo_root,
        always_prefix=False,
    )


def _get_hg_remote_url(repo_root: str) -> str | None:
    try:
        url = subprocess.run(
            ["hg", "showconfig", "paths.default"],  # noqa: S607
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=True,
            timeout=5,
        ).stdout.strip()
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return None
    else:
        return url or None


def _get_hg_commit_id(repo_root: str) -> str | None:
    try:
        commit_id = subprocess.run(
            ["hg", "parents", "--template={node}"],  # noqa: S607
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=True,
            timeout=5,
        ).stdout.strip()
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return None
    else:
        return commit_id or None


# --- svn backend ---


def _get_svn_requirement(location: str, package_name: str, repo_root: str) -> VcsResult:
    try:
        svn_info = _get_svn_info(location)
    except FileNotFoundError:
        return VcsResult(None, vcs_name="svn", error=VcsError.COMMAND_NOT_FOUND)
    if svn_info is None:
        entries = _get_svn_entries_fallback(location)
        if entries is None:
            return VcsResult(None, vcs_name="svn", error=VcsError.NO_REMOTE)
        remote_url, revision = entries
    else:
        remote_url, revision = svn_info
    return _build_vcs_result(
        vcs_name="svn",
        remote_url=remote_url,
        commit_id=revision,
        package_name=package_name,
        location=location,
        repo_root=repo_root,
        always_prefix=True,
        include_subdirectory=False,
    )


def _get_svn_info(location: str) -> tuple[str, str] | None:
    """Parse svn info --xml to extract URL and revision."""
    try:
        xml_output = subprocess.run(
            ["svn", "info", "--xml"],  # noqa: S607
            cwd=location,
            capture_output=True,
            text=True,
            check=True,
            timeout=5,
        ).stdout
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return None
    try:
        root = ET.fromstring(xml_output)  # noqa: S314
    except ET.ParseError:
        return None
    entry = root.find(".//entry")
    if entry is None:
        return None
    revision = entry.get("revision", "")
    url_elem = entry.find("url")
    if url_elem is None or not url_elem.text:
        return None
    return url_elem.text, revision


def _get_svn_entries_fallback(location: str) -> tuple[str, str] | None:
    """Parse legacy .svn/entries file (pre-1.7 SVN) for URL and revision."""
    entries_path = Path(location) / ".svn" / "entries"
    if not entries_path.is_file():
        return None
    try:
        data = entries_path.read_text(encoding="utf-8")
    except OSError:
        return None
    if data.startswith("<?xml"):
        return None
    lines = data.splitlines()
    if len(lines) < 5:
        return None
    revision = lines[3].strip()
    url = lines[4].strip()
    if not url:
        return None
    return url, revision


# --- bzr backend ---


def _get_bzr_requirement(location: str, package_name: str, repo_root: str) -> VcsResult:
    try:
        remote_url = _get_bzr_remote_url(repo_root)
        if remote_url is None:
            return VcsResult(None, vcs_name="bzr", error=VcsError.NO_REMOTE)
        if _is_local_path(remote_url):
            remote_url = Path(remote_url).as_uri()
        if not (revision := _get_bzr_revision(repo_root)):
            return VcsResult(None, vcs_name="bzr", error=VcsError.NO_REMOTE)
    except FileNotFoundError:
        return VcsResult(None, vcs_name="bzr", error=VcsError.COMMAND_NOT_FOUND)
    return _build_vcs_result(
        vcs_name="bzr",
        remote_url=remote_url,
        commit_id=revision,
        package_name=package_name,
        location=location,
        repo_root=repo_root,
        always_prefix=False,
        include_subdirectory=False,
    )


def _get_bzr_remote_url(repo_root: str) -> str | None:
    """Parse `bzr info` output for checkout/parent branch URL."""
    try:
        output = subprocess.run(
            ["bzr", "info"],  # noqa: S607
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=True,
            timeout=5,
        ).stdout
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return None
    for line in output.splitlines():
        stripped = line.strip()
        for prefix in ("checkout of branch: ", "parent branch: "):
            if stripped.startswith(prefix):
                return stripped[len(prefix) :].strip() or None
    return None


def _get_bzr_revision(repo_root: str) -> str | None:
    try:
        output = subprocess.run(
            ["bzr", "revno"],  # noqa: S607
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=True,
            timeout=5,
        ).stdout.strip()
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return None
    lines = output.splitlines()
    return lines[-1].strip() if lines else None


__all__ = [
    "VcsError",
    "VcsResult",
    "get_vcs_requirement",
]
