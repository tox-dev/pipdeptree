from __future__ import annotations

import sys
from subprocess import check_call  # noqa: S404
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pytest_console_scripts import ScriptRunner


def test_main() -> None:
    check_call([sys.executable, "-m", "pipdeptree", "--help"])


def test_console(script_runner: ScriptRunner) -> None:
    result = script_runner.run("pipdeptree", "--help")
    assert result.success
