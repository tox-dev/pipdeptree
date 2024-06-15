from __future__ import annotations

from subprocess import CompletedProcess  # noqa: S404
from typing import TYPE_CHECKING

from pipdeptree.__main__ import main

if TYPE_CHECKING:
    from pathlib import Path

    import pytest
    from pytest_mock import MockFixture


def test_main_log_resolved(tmp_path: Path, mocker: MockFixture, capsys: pytest.CaptureFixture[str]) -> None:
    cmd = ["", "--python", "auto"]
    mocker.patch("pipdeptree.__main__.sys.argv", cmd)

    mocker.patch("pipdeptree._detect_env.detect_active_interpreter", return_value=str(tmp_path))
    mocker.patch("pipdeptree._detect_env.os.environ", {"VIRTUAL_ENV": str(tmp_path)})
    mocker.patch("pipdeptree._detect_env.Path.exists", return_value=True)

    valid_sys_path = str([str(tmp_path)])
    mock_subprocess_run = mocker.patch("subprocess.run")
    mock_subprocess_run.return_value = CompletedProcess(
        args=["python", "-c", "import sys; print(sys.path)"],
        returncode=0,
        stdout=valid_sys_path,
        stderr="",
    )

    main()

    captured = capsys.readouterr()

    combined_output = captured.out + captured.err

    assert f"Resolved Python: [{tmp_path!s}" in combined_output
