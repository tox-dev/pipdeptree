from __future__ import annotations

import sys
from subprocess import CompletedProcess, check_call  # noqa: S404
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

    from pytest_console_scripts import ScriptRunner
    from pytest_mock import MockFixture


def test_main() -> None:
    check_call([sys.executable, "-m", "pipdeptree", "--help"])


def test_console(script_runner: ScriptRunner) -> None:
    result = script_runner.run(["pipdeptree", "--help"])
    assert result.success


def test_main_log_resolved(tmp_path: Path, mocker: MockFixture, script_runner: ScriptRunner) -> None:
    valid_sys_path = str([str(tmp_path)])

    mocker.patch("pipdeptree._detect_env.detect_active_interpreter", return_value=str(tmp_path))
    mocker.patch("pipdeptree._detect_env.os.environ", {"VIRTUAL_ENV": str(tmp_path)})
    mocker.patch("pipdeptree._detect_env.Path.exists", return_value=True)

    mock_subprocess_run = mocker.patch("subprocess.run")
    mock_subprocess_run.return_value = CompletedProcess(
        args=["python", "-c", "import sys; print(sys.path)"],
        returncode=0,
        stdout=valid_sys_path,
        stderr="",
    )

    result = script_runner.run(["pipdeptree", "--python", "auto"])
    assert result.stderr
    assert result.stderr.startswith(f"(resolved python: {tmp_path!s}")
