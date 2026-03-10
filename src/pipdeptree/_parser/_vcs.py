from __future__ import annotations

import re
import subprocess  # noqa: S404
from pathlib import Path


def get_vcs_requirement(location: str, package_name: str) -> str | None:
    """
    Detect VCS and generate requirement string for editable install.

    Probes directory for git repository (including parent directories) and extracts
    remote URL and commit hash. Falls back to None if no VCS detected or extraction fails.

    :param location: Filesystem path to source directory
    :param package_name: Package name for egg fragment
    :returns: VCS requirement string like "git+https://...@commit#egg=name", or None if not VCS
    """
    if git_req := _get_git_requirement(location, package_name):
        return git_req
    return None


def _get_git_requirement(location: str, package_name: str) -> str | None:
    """
    Get git requirement string for editable install.

    Uses git rev-parse --show-toplevel to find repository root from any subdirectory,
    then extracts origin URL and HEAD commit. Normalizes SCP-style and local URLs.

    :param location: Filesystem path to source directory (can be subdirectory of repo)
    :param package_name: Package name for egg fragment
    :returns: Git requirement string, or None if not git repo or extraction fails
    """
    try:
        repo_root = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],  # noqa: S607
            cwd=location,
            capture_output=True,
            text=True,
            check=True,
            timeout=5,
        ).stdout.strip()
        if not repo_root:
            return None
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
        return None
    try:
        remote_url = subprocess.run(
            ["git", "config", "--get", "remote.origin.url"],  # noqa: S607
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=True,
            timeout=5,
        ).stdout.strip()
        if not remote_url:
            return None
        commit_id = subprocess.run(
            ["git", "rev-parse", "HEAD"],  # noqa: S607
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=True,
            timeout=5,
        ).stdout.strip()
        if not commit_id:
            return None
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
        return None
    else:
        normalized_url = _normalize_git_url(remote_url)
        safe_package_name = _normalize_egg_name(package_name)
        subdirectory = _get_subdirectory(location, repo_root)
        result = f"git+{normalized_url}@{commit_id}#egg={safe_package_name}"
        if subdirectory:
            result += f"&subdirectory={subdirectory}"
        return result


def _normalize_git_url(url: str) -> str:
    """
    Normalize git URL to standard format.

    Converts SCP-style URLs (git@github.com:user/repo.git) to standard URLs,
    and handles git:// URLs without adding git+ prefix.

    :param url: Raw git URL from remote.origin.url
    :returns: Normalized URL suitable for pip requirement
    """
    if url.startswith("git://"):
        return url[6:]
    scp_pattern = re.compile(r"^(?:[\w.-]+@)?([^:]+):(.+)$")
    if match := scp_pattern.match(url):
        host, path = match.groups()
        if not path.startswith("/"):
            return f"ssh://{host}/{path}"
    if url.startswith("file://"):
        return url
    if url.startswith(("http://", "https://", "ssh://")):
        return url
    if Path(url).exists():
        return f"file://{Path(url).resolve()}"
    return url


def _normalize_egg_name(name: str) -> str:
    """
    Normalize package name for egg fragment.

    Replaces - with _ to match setuptools egg naming conventions.

    :param name: Package name
    :returns: Normalized name for #egg= fragment
    """
    return name.replace("-", "_")


def _get_subdirectory(location: str, repo_root: str) -> str | None:
    """
    Calculate subdirectory path relative to repository root.

    :param location: Absolute path to package location
    :param repo_root: Absolute path to repository root
    :returns: Relative subdirectory path, or None if at root
    """
    try:
        location_path = Path(location).resolve()
        repo_root_path = Path(repo_root).resolve()
        relative = location_path.relative_to(repo_root_path)
        if str(relative) != ".":
            return str(relative)
    except (ValueError, OSError):
        pass
    return None


__all__ = ["get_vcs_requirement"]
