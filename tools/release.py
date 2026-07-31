#!/usr/bin/env python3
"""
Cut a release: build the changelog, commit it on the upstream main branch, and tag it.

The tag push triggers the publish workflow, and the build reads its version from that tag, so nothing in the tree
names the version. Each step lands upstream only once the ones before it went through.
"""

from __future__ import annotations

import argparse
import re
import subprocess  # ruff:ignore[suspicious-subprocess-import]  # Tagging and the release API need git and gh.
from pathlib import Path
from typing import Final

_ROOT: Final = Path(__file__).resolve().parent.parent
_UPSTREAM_SLUG: Final = "tox-dev/pipdeptree"
_RELEASE_TAG: Final = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")


def main() -> None:
    parser = argparse.ArgumentParser(prog="release", description=__doc__)
    target = parser.add_mutually_exclusive_group()
    target.add_argument("--bump", choices=["major", "minor", "patch"], default="patch", help="how to pick the version")
    target.add_argument("--version", help="release this exact version instead of bumping")
    args = parser.parse_args()

    if _capture("git", "status", "--porcelain"):
        msg = "the working tree is dirty; commit or stash before releasing"
        raise RuntimeError(msg)

    upstream = _upstream()
    _run("git", "fetch", "--tags", "--force", upstream)
    tags = _capture("git", "tag").splitlines()
    version = args.version or _next(tags, args.bump)
    if version in tags:
        msg = f"tag {version} already exists"
        raise RuntimeError(msg)
    _release(upstream, version)


def _upstream() -> str:
    remotes = _capture("git", "remote").splitlines()
    # A fork's origin points at the fork, so go by the slug rather than by remote name.
    for remote in remotes:
        if _UPSTREAM_SLUG in _capture("git", "remote", "get-url", remote):
            return remote
    msg = f"no remote points at {_UPSTREAM_SLUG}, found {remotes}"
    raise RuntimeError(msg)


def _next(tags: list[str], bump: str) -> str:
    releases = [(int(found[1]), int(found[2]), int(found[3])) for tag in tags if (found := _RELEASE_TAG.match(tag))]
    major, minor, patch = max(releases, default=(0, 0, 0))
    if bump == "major":
        return f"{major + 1}.0.0"
    if bump == "minor":
        return f"{major}.{minor + 1}.0"
    return f"{major}.{minor}.{patch + 1}"


def _release(upstream: str, version: str) -> None:
    _run("git", "switch", "--force-create", f"release-{version}", f"{upstream}/main")
    _run("towncrier", "build", "--yes", "--version", version)
    _run("git", "commit", "--all", "--message", f"release {version}")
    _run("git", "push", upstream, "HEAD:main")
    _run("git", "tag", "--annotate", "--message", f"release {version}", version)
    _run("git", "push", upstream, f"refs/tags/{version}")
    _run("gh", "release", "create", version, "--title", version, "--generate-notes", "--verify-tag")


def _run(*command: str, check: bool = True) -> None:
    subprocess.run(  # ruff:ignore[subprocess-without-shell-equals-true]  # Fixed argument list.
        command,
        cwd=_ROOT,
        check=check,
    )


def _capture(*command: str) -> str:
    result = subprocess.run(  # ruff:ignore[subprocess-without-shell-equals-true]  # Fixed argument list.
        command,
        cwd=_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


if __name__ == "__main__":
    main()


__all__: Final = []
