#!/usr/bin/env python3
"""Resolve the build version without importing the package or its native extension."""

from __future__ import annotations

import os
import subprocess  # ruff:ignore[suspicious-subprocess-import]  # Reading the tags needs the git executable.
from pathlib import Path
from typing import Final

_ROOT: Final = Path(__file__).resolve().parent.parent


def main() -> None:
    print(_resolve())  # ruff:ignore[print]  # Meson reads the version off this output.


def _resolve() -> str:
    if (pretend := os.environ.get("PIPDEPTREE_VERSION")) is not None:
        return pretend  # A build with no history of its own, such as one cibuildwheel runs inside a container.
    if (from_git := _from_git()) is not None:
        return from_git
    if (metadata := _ROOT / "PKG-INFO").is_file():
        for line in metadata.read_text(encoding="utf-8").splitlines():
            if not line:
                break
            if line.startswith("Version:") and (version := line.removeprefix("Version:").strip()):
                return version
    return "0.0.0"


def _from_git() -> str | None:
    if not (_ROOT / ".git").exists():
        return None
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
