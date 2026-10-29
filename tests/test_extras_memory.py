from __future__ import annotations

import os
import subprocess  # ruff: ignore[suspicious-subprocess-import] # peak RSS needs a child process
import sys
from typing import TYPE_CHECKING, Final

import pytest

if TYPE_CHECKING:
    from pathlib import Path

_REQUESTED: Final = ",".join(f"r{index}" for index in range(20_000))
_ACTIVATING: Final = " or ".join(f"extra == 'a{index}'" for index in range(100))


def _peak_rss_mib(root: Path, requires: list[str], extras: str) -> float:  # pragma: win32 no cover
    dist_info = root / "hostile-1.dist-info"
    dist_info.mkdir(parents=True)
    lines = ["Name: hostile", "Version: 1", *(f"Requires-Dist: {require}" for require in requires)]
    (dist_info / "METADATA").write_text("\n".join(lines) + "\n")
    command = [sys.executable, "-m", "pipdeptree", "--path", str(root), "--warn", "silence", "--extras", extras]
    process = subprocess.Popen(command, stdout=subprocess.DEVNULL)
    _, status, usage = os.wait4(process.pid, 0)
    process.returncode = os.waitstatus_to_exitcode(status)
    assert process.returncode == 0
    return usage.ru_maxrss / 1024


@pytest.mark.skipif(sys.platform != "linux", reason="ru_maxrss counts KiB only on Linux")
@pytest.mark.parametrize("extras", ["explicit", "active"])
def test_requirement_is_stored_once_for_all_activating_extras(  # pragma: win32 no cover
    tmp_path: Path, extras: str
) -> None:
    hostile = _peak_rss_mib(tmp_path / "hostile", ["hostile[a0]", f"hostile[{_REQUESTED}]; {_ACTIVATING}"], extras)
    control = _peak_rss_mib(
        tmp_path / "control",
        ["hostile[a0]", f"hostile[{_REQUESTED}]; extra == 'a0'", f"hostile[a0]; {_ACTIVATING}"],
        extras,
    )

    assert hostile - control < 32
