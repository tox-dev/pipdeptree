from __future__ import annotations

import sys
from pathlib import Path
from subprocess import check_call  # noqa: S404


def test_main() -> None:
    check_call([sys.executable, "-m", "pipdeptree", "--help"])


def test_console() -> None:
    check_call([Path(sys.executable).parent / "pipdeptree", "--help"])
