from __future__ import annotations

import os
import subprocess  # ruff: ignore[suspicious-subprocess-import] # peak RSS needs a child process
import sys
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pathlib import Path


@pytest.mark.skipif(sys.platform != "linux", reason="ru_maxrss counts KiB only on Linux")
@pytest.mark.parametrize("extras", [pytest.param("explicit", id="explicit"), pytest.param("active", id="active")])
def test_extras_requirement_memory_ignores_activating_extra_count(  # pragma: win32 no cover
    tmp_path: Path, extras: str
) -> None:
    requested = ",".join(f"r{index}" for index in range(20_000))
    activating = " or ".join(f"extra == 'a{index}'" for index in range(100))
    hostile = _peak_rss_mib(tmp_path / "hostile", ["hostile[a0]", f"hostile[{requested}]; {activating}"], extras)
    control = _peak_rss_mib(
        tmp_path / "control",
        ["hostile[a0]", f"hostile[{requested}]; extra == 'a0'", f"hostile[a0]; {activating}"],
        extras,
    )

    assert hostile - control < 32


def _peak_rss_mib(root: Path, requires: list[str], extras: str) -> float:  # pragma: win32 no cover
    dist_info = root / "hostile-1.dist-info"
    dist_info.mkdir(parents=True)
    lines = ["Name: hostile", "Version: 1", *(f"Requires-Dist: {require}" for require in requires)]
    (dist_info / "METADATA").write_text("".join(f"{line}\n" for line in lines))
    command = [sys.executable, "-m", "pipdeptree", "--path", str(root), "--warn", "silence", "--extras", extras]
    process = subprocess.Popen(command, stdout=subprocess.DEVNULL)
    _, status, usage = os.wait4(process.pid, 0)
    # os.wait4 reaped the child behind Popen's back; without the exit code Popen warns that it still runs
    process.returncode = os.waitstatus_to_exitcode(status)
    assert process.returncode == 0
    return usage.ru_maxrss / 1024
