from __future__ import annotations

import sys
from subprocess import CompletedProcess, check_call  # noqa: S404
from typing import TYPE_CHECKING

from pipdeptree.__main__ import main

if TYPE_CHECKING:
    from pathlib import Path

    import pytest
    from pytest_console_scripts import ScriptRunner
    from pytest_mock import MockFixture


def test_main() -> None:
    check_call([sys.executable, "-m", "pipdeptree", "--help"])


def test_console(script_runner: ScriptRunner) -> None:
    result = script_runner.run(["pipdeptree", "--help"])
    assert result.success


def test_main_log_resolved(tmp_path: Path, mocker: MockFixture, capsys: pytest.CaptureFixture[str]) -> None:
    mocker.patch("sys.argv", ["", "--python", "auto"])
    mocker.patch("pipdeptree.__main__.detect_active_interpreter", return_value=str(tmp_path))
    mock_subprocess_run = mocker.patch("subprocess.run")
    valid_sys_path = str([str(tmp_path)])
    mock_subprocess_run.return_value = CompletedProcess(
        args=["python", "-c", "import sys; print(sys.path)"],
        returncode=0,
        stdout=valid_sys_path,
        stderr="",
    )

    main()

    captured = capsys.readouterr()
    assert captured.err.startswith(f"(resolved python: {tmp_path!s}")
