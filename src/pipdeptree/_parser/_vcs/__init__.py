from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from ._bzr import _get_bzr_requirement
from ._git import _get_git_repo_root, _get_git_requirement
from ._hg import _get_hg_requirement
from ._shared import VcsError, VcsResult
from ._svn import _get_svn_requirement

if TYPE_CHECKING:
    from collections.abc import Callable


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


__all__ = [
    "VcsError",
    "VcsResult",
    "get_vcs_requirement",
]
