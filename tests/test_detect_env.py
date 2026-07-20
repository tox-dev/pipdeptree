from __future__ import annotations

import os
from pathlib import Path
from subprocess import CompletedProcess  # ruff:ignore[suspicious-subprocess-import]
from typing import TYPE_CHECKING

import pytest

from pipdeptree._detect_env import (
    detect_active_interpreter,
    determine_bin_dir,
    determine_interpreter_file_name,
    find_active_interpreter,
)

if TYPE_CHECKING:
    from pytest_mock import MockFixture


@pytest.mark.parametrize(("env_var"), ["VIRTUAL_ENV", "CONDA_PREFIX"])
def test_detect_active_interpreter_using_env_vars(tmp_path: Path, mocker: MockFixture, env_var: str) -> None:
    mocker.patch("pipdeptree._detect_env.os.environ", {env_var: str(tmp_path)})
    mocker.patch("pipdeptree._detect_env.Path.exists", return_value=True)

    actual_path = detect_active_interpreter()

    assert actual_path.startswith(str(tmp_path))


def test_detect_active_interpreter_poetry(tmp_path: Path, mocker: MockFixture) -> None:
    faked_result = CompletedProcess("", 0, stdout=str(tmp_path))
    mocker.patch("pipdeptree._detect_env.subprocess.run", return_value=faked_result)
    mocker.patch("pipdeptree._detect_env.os.environ", {})

    actual_path = detect_active_interpreter()

    assert str(tmp_path) == actual_path


def test_detect_active_interpreter_non_supported_python_implementation(
    tmp_path: Path,
    mocker: MockFixture,
) -> None:
    mocker.patch("pipdeptree._detect_env.os.environ", {"VIRTUAL_ENV": str(tmp_path)})
    mocker.patch("pipdeptree._detect_env.Path.exists", return_value=True)
    mocker.patch("pipdeptree._detect_env.platform.python_implementation", return_value="NotSupportedPythonImpl")

    with pytest.raises(SystemExit):
        detect_active_interpreter()


def test_detect_active_interpreter_non_existent_path(
    mocker: MockFixture,
) -> None:
    fake_path = str(Path(*("i", "dont", "exist")))
    mocker.patch("pipdeptree._detect_env.os.environ", {"VIRTUAL_ENV": fake_path})

    with pytest.raises(SystemExit):
        detect_active_interpreter()


def test_detect_active_interpreter_continue_when_other_detections_fail(tmp_path: Path, mocker: MockFixture) -> None:
    # ensures that we fallback to another virtual env detection in case a detection (in this scenario virtualenv) points
    # to a non-existent path
    non_existent_path = Path("/i/dont/exist")
    mocker.patch(
        "pipdeptree._detect_env.os.environ.get",
        side_effect=lambda key: non_existent_path if key == "VIRTUAL_ENV" else str(tmp_path),
    )
    fake_conda_python_dir = tmp_path
    if os.name == "posix":  # pragma: posix cover
        fake_conda_python_dir /= determine_bin_dir()
        fake_conda_python_dir.mkdir()
    interpreter_file = determine_interpreter_file_name()
    assert interpreter_file
    fake_conda_python_interpreter_path = fake_conda_python_dir / interpreter_file
    fake_conda_python_interpreter_path.write_text("This is a fake Python interpreter", encoding="utf-8")

    detected_path = detect_active_interpreter()

    assert detected_path == str(fake_conda_python_interpreter_path)


def test_find_active_interpreter_returns_path_when_detected(tmp_path: Path, mocker: MockFixture) -> None:
    mocker.patch("pipdeptree._detect_env.os.environ", {"VIRTUAL_ENV": str(tmp_path)})
    mocker.patch("pipdeptree._detect_env.Path.exists", return_value=True)

    detected = find_active_interpreter()

    assert detected is not None
    assert detected.startswith(str(tmp_path))


def test_find_active_interpreter_returns_none_when_nothing_detected(mocker: MockFixture) -> None:
    mocker.patch("pipdeptree._detect_env.os.environ", {})
    mocker.patch("pipdeptree._detect_env.subprocess.run", side_effect=FileNotFoundError)

    assert find_active_interpreter() is None
