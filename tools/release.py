#!/usr/bin/env python3
"""Preview a release locally, or dispatch the protected GitHub workflow."""

from __future__ import annotations

import argparse
import os
import subprocess  # ruff:ignore[suspicious-subprocess-import]  # Local tools and the workflow CLI are process boundaries.
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Final

_ROOT: Final = Path(__file__).resolve().parent.parent


def main() -> None:
    """Keep local checks separate from the protected write path."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bump", choices=("auto", "major", "minor", "patch"), default="auto")
    parser.add_argument("--dispatch", action="store_true", help="start the protected GitHub release workflow")
    args = parser.parse_args()
    repository: Final = "tox-dev/pipdeptree"
    if args.dispatch:
        _run(
            "gh",
            "workflow",
            "run",
            "prepare-release.yaml",
            "--repo",
            repository,
            "--ref",
            "main",
            "-f",
            f"bump={args.bump}",
        )
        return

    with TemporaryDirectory(prefix="pipdeptree-release-") as temporary_directory:
        source = Path(temporary_directory) / "source"
        _run("git", "clone", "--quiet", "--no-local", str(_ROOT), str(source))
        tags = _run("git", "tag", "--list", cwd=source, capture_output=True).stdout
        version = _run(
            "release-creator",
            "tags",
            "--next",
            args.bump,
            "--directory",
            "docs/changelog",
            cwd=source,
            stdin_text=tags,
            capture_output=True,
        ).stdout.strip()
        previous = _run(
            "release-creator", "tags", version, "--previous", cwd=source, stdin_text=tags, capture_output=True
        ).stdout.strip()
        _run(
            "release-creator",
            "fragments",
            "--directory",
            "docs/changelog",
            "--repository",
            repository,
            cwd=source,
        )
        _run("towncrier", "build", "--yes", "--version", version, cwd=source)
        _run(
            "release-creator",
            "contributors",
            "--changelog",
            "docs/changelog.rst",
            "--version",
            version,
            "--repository",
            repository,
            cwd=source,
        )
        try:
            _run("prek", "run", "docstrfmt", "--files", "docs/changelog.rst", cwd=source)
        except subprocess.CalledProcessError:
            _run("prek", "run", "docstrfmt", "--files", "docs/changelog.rst", cwd=source)
        _run("prek", "run", "--all-files", cwd=source)
        note_args = [
            "release-creator",
            "notes",
            "--changelog",
            "docs/changelog.rst",
            "--tag",
            version,
            "--repository",
            repository,
            "--artifact-url",
            f"https://pypi.org/project/pipdeptree/{version}/",
        ]
        if previous:
            note_args.extend(("--previous", previous))
        notes = _run(*note_args, cwd=source, capture_output=True).stdout
        build_environment: Final = Path(temporary_directory) / "build"
        _run("uv", "venv", "--python", "3.15", str(build_environment), cwd=source)
        _run(
            "uv",
            "pip",
            "sync",
            "--preview-features",
            "pylock",
            "--python",
            str(build_environment),
            "--require-hashes",
            "pylock.build.toml",
            cwd=source,
        )
        epoch: Final = _run("git", "log", "-1", "--format=%ct", cwd=source, capture_output=True).stdout.strip()
        _run(
            "uv",
            "build",
            "--sdist",
            "--wheel",
            "--python",
            str(build_environment),
            "--out-dir",
            "dist",
            "--no-build-isolation",
            cwd=source,
            env=dict(os.environ, PIPDEPTREE_VERSION=version, SOURCE_DATE_EPOCH=epoch),
        )
        _run(sys.executable, "tools/check_release_wheels.py", "dist", cwd=source)
        sys.stdout.write(notes)


def _run(
    *command: str,
    cwd: Path = _ROOT,
    stdin_text: str | None = None,
    capture_output: bool = False,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # ruff:ignore[subprocess-without-shell-equals-true]  # Arguments never pass through a shell.
        command,
        cwd=cwd,
        input=stdin_text,
        capture_output=capture_output,
        stdout=None if capture_output else sys.stderr,
        text=True,
        check=True,
        shell=False,
        env=env,
    )


if __name__ == "__main__":
    main()


__all__ = [
    "main",
]
