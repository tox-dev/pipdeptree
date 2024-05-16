from __future__ import annotations

from pathlib import Path
from subprocess import CompletedProcess  # noqa: S404
from typing import TYPE_CHECKING

import pytest

from pipdeptree._detect_env import detect_active_interpreter

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
