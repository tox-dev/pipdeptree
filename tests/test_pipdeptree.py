from __future__ import annotations

import sys
from importlib import metadata
from subprocess import CompletedProcess, check_call  # noqa: S404
from typing import TYPE_CHECKING

import pytest

from pipdeptree.__main__ import main

if TYPE_CHECKING:
    from pathlib import Path

    from pytest_mock import MockFixture


def test_main() -> None:
    check_call([sys.executable, "-m", "pipdeptree", "--help"])


def test_console_script() -> None:
    try:
        dist = metadata.distribution("pipdeptree")
    except Exception as e:  # noqa: BLE001 # pragma: no cover
        pytest.fail(f"Unexpected error when retrieving pipdeptree metadata: {e}")

    entry_points = dist.entry_points
    assert len(entry_points) == 1

    if sys.version_info >= (3, 11):  # pragma: >=3.11
        entry_point = entry_points["pipdeptree"]
    else:
        entry_point = entry_points[0]

    try:
        pipdeptree = entry_point.load()
    except Exception as e:  # noqa: BLE001 # pragma: no cover
        pytest.fail(f"Unexpected error: {e}")

    with pytest.raises(SystemExit, match="0"):
        pipdeptree(["", "--help"])


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


def test_main_include_and_exclude_overlap(mocker: MockFixture, capsys: pytest.CaptureFixture[str]) -> None:
    cmd = ["", "--packages", "a,b,c", "--exclude", "a"]
    mocker.patch("pipdeptree.__main__.sys.argv", cmd)

    main()

    captured = capsys.readouterr()
    assert "Cannot have --packages and --exclude contain the same entries" in captured.err
