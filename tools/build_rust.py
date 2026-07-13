"""Meson delegates dependency resolution and compilation to Cargo."""

from __future__ import annotations

import os
import shutil
import subprocess  # noqa: S404  # Meson supplies the Cargo executable.
import sys
from pathlib import Path
from typing import Final


def main() -> None:
    cargo, source, destination, artifact, features = sys.argv[1:]
    output = Path(destination)
    target = output.parent / "cargo-target"
    environment = {**os.environ, "CARGO_TARGET_DIR": str(target)}
    command = [
        cargo,
        "build",
        "--manifest-path",
        str(Path(source) / "Cargo.toml"),
        "--release",
        "--locked",
        "--no-default-features",
        "--features",
        features,
    ]
    code = subprocess.run(command, env=environment, check=False).returncode  # noqa: S603  # Meson supplies Cargo.
    if code != 0:
        msg = f"Cargo exited with status {code}"
        raise RuntimeError(msg)
    shutil.copyfile(_artifact(target, artifact), output)


def _artifact(target: Path, name: str) -> Path:
    matches = list(target.glob(f"**/release/{name}"))
    if len(matches) != 1:
        msg = f"expected one Cargo artifact named {name}, found {len(matches)}"
        raise RuntimeError(msg)
    return matches[0]


if __name__ == "__main__":
    main()


__all__: Final = []
