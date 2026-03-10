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
    then extracts remote URL and HEAD commit. Checks all remotes, preferring origin.
    Normalizes SCP-style and local URLs to match pip's behavior.

    :param location: Filesystem path to source directory (can be subdirectory of repo)
    :param package_name: Package name for egg fragment
    :returns: Git requirement string, or None if not git repo or extraction fails
    """
    if not (repo_root := _get_repo_root(location)):
        return None
    if not (remote_url := _get_remote_url(repo_root)):
        return None
    if not (commit_id := _get_commit_id(repo_root)):
        return None
    return _build_vcs_requirement(
        remote_url=remote_url,
        commit_id=commit_id,
        package_name=package_name,
        location=location,
        repo_root=repo_root,
    )


def _get_repo_root(location: str) -> str | None:
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
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
        return None
    else:
        return repo_root or None


def _get_remote_url(repo_root: str) -> str | None:
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
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
        return None


def _get_commit_id(repo_root: str) -> str | None:
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
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
        return None
    else:
        return commit_id or None


def _build_vcs_requirement(
    remote_url: str,
    commit_id: str,
    package_name: str,
    location: str,
    repo_root: str,
) -> str:
    """Build VCS requirement string from components."""
    normalized_url = _normalize_git_url(remote_url)
    safe_package_name = _normalize_egg_name(package_name)
    if not normalized_url.lower().startswith("git:"):
        normalized_url = f"git+{normalized_url}"
    result = f"{normalized_url}@{commit_id}#egg={safe_package_name}"
    if subdirectory := _get_subdirectory(location, repo_root):
        result += f"&subdirectory={subdirectory}"
    return result


def _normalize_git_url(url: str) -> str:
    """
    Normalize git URL to standard format matching pip's behavior.

    Converts SCP-style URLs (git@github.com:user/repo.git) to ssh:// URLs,
    preserving the user. Keeps git://, http://, https://, ssh:// URLs as-is.
    Converts local paths to file:// URLs using proper URI encoding.

    Based on pip's _git_remote_to_pip_url implementation.

    :param url: Raw git URL from remote config
    :returns: Normalized URL suitable for pip requirement
    """
    if re.match(r"\w+://", url):
        return url
    if Path(url).exists():
        return Path(url).as_uri()
    if match := re.match(
        r"""^
        (\w+@)?      # Optional user, e.g. 'git@'
        ([^/:]+):    # Server, e.g. 'github.com'
        (\w[^:]*)    # Server-side path starting with alphanumeric (not Windows paths like C:)
        $""",
        url,
        re.VERBOSE,
    ):
        return match.expand(r"ssh://\1\2/\3")
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
