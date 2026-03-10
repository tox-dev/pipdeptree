from __future__ import annotations

import subprocess  # noqa: S404
from pathlib import Path


def get_vcs_requirement(location: str, package_name: str) -> str | None:
    """
    Detect VCS and generate requirement string for editable install.

    Probes directory for git repository and extracts remote URL and commit hash.
    Falls back to None if no VCS detected or extraction fails.

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

    Checks if directory is git repository, extracts origin URL and HEAD commit.

    :param location: Filesystem path to source directory
    :param package_name: Package name for egg fragment
    :returns: Git requirement string, or None if not git repo or extraction fails
    """
    git_dir = Path(location) / ".git"
    if not git_dir.exists():
        return None
    try:
        remote_url = subprocess.run(
            ["git", "config", "--get", "remote.origin.url"],  # noqa: S607
            cwd=location,
            capture_output=True,
            text=True,
            check=True,
            timeout=5,
        ).stdout.strip()
        if not remote_url:
            return None
        commit_id = subprocess.run(
            ["git", "rev-parse", "HEAD"],  # noqa: S607
            cwd=location,
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
        return f"git+{remote_url}@{commit_id}#egg={package_name}"


__all__ = ["get_vcs_requirement"]
