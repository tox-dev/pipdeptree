#!/usr/bin/env python3
"""
Derive the version from the git tags for the Meson build.

Meson calls this at configure time and uses the printed string as the project version, the way setuptools-scm derives
one from the latest tag. ``meson dist`` calls it again with ``--write`` to freeze the resolved version into the sdist's
VERSION file, so a wheel built from that sdist reports the right version without git history.
"""

from __future__ import annotations

import argparse
import os
import subprocess  # ruff:ignore[suspicious-subprocess-import]  # Reading the tags needs the git executable.
import sys
from pathlib import Path
from typing import Final

_ROOT: Final = Path(__file__).resolve().parent.parent
_VERSION_FILE: Final = "VERSION"


def main() -> None:
    parser = argparse.ArgumentParser(prog="version", description=__doc__)
    parser.add_argument("--write", action="store_true", help=f"write the version to {_VERSION_FILE} in the dist root")
    args = parser.parse_args()
    version = _resolve()
    if args.write:
        (Path(os.environ["MESON_DIST_ROOT"]) / _VERSION_FILE).write_text(f"{version}\n", encoding="utf-8")
    print(version)  # ruff:ignore[print]  # Meson reads the version off this output.


def _resolve() -> str:
    if (pretend := os.environ.get("PIPDEPTREE_VERSION")) is not None:
        return pretend  # A build with no history of its own, such as one cibuildwheel runs inside a container.
    if (from_git := _from_git()) is not None:
        return from_git
    if (_ROOT / ".git").exists():
        print(  # ruff:ignore[print]  # A stale version has to show in the build log.
            f"warning: no release tag reachable from HEAD, falling back to {_VERSION_FILE}; "
            "run git fetch --tags in a shallow clone",
            file=sys.stderr,
        )
    return (_ROOT / _VERSION_FILE).read_text(encoding="utf-8").strip()


def _from_git() -> str | None:
    if (described := _git("describe", "--tags", "--long", "--match", "[0-9]*")) is None:
        return None
    tag, distance, commit = described.rsplit("-", 2)
    return tag if int(distance) == 0 else f"{tag}.dev{distance}+{commit}"  # The commit already carries the leading g.


def _git(*args: str) -> str | None:
    try:
        completed = subprocess.run(  # ruff:ignore[subprocess-without-shell-equals-true]  # Fixed argument list.
            ["git", *args],  # ruff:ignore[start-process-with-partial-path]  # Git comes off PATH, as for any build.
            capture_output=True,
            text=True,
            cwd=_ROOT,
            check=False,
        )
    except FileNotFoundError:  # Git is absent, as in a container building from an unpacked sdist.
        return None
    return completed.stdout.strip() if completed.returncode == 0 else None


if __name__ == "__main__":
    main()


__all__: Final = []
