from __future__ import annotations

import sys
from typing import TYPE_CHECKING

import pytest

from pipdeptree.__main__ import _resolve_python, main

if TYPE_CHECKING:
    from pathlib import Path

    from pytest_mock import MockFixture


def test_resolve_python_default_uses_detected_env(
    tmp_path: Path, mocker: MockFixture, capsys: pytest.CaptureFixture[str]
) -> None:
    mocker.patch("pipdeptree.__main__.find_active_interpreter", return_value=str(tmp_path))

    assert _resolve_python(None, log_resolved=True) == str(tmp_path)

    assert capsys.readouterr().err == f"(resolved python: {tmp_path})\n"


def test_resolve_python_default_note_silent_without_log(
    tmp_path: Path, mocker: MockFixture, capsys: pytest.CaptureFixture[str]
) -> None:
    # The programmatic API resolves without log_resolved, so notebooks get no stderr note.
    mocker.patch("pipdeptree.__main__.find_active_interpreter", return_value=str(tmp_path))

    assert _resolve_python(None) == str(tmp_path)

    captured = capsys.readouterr()
    assert not captured.out
    assert not captured.err


def test_resolve_python_default_falls_back_silently(mocker: MockFixture, capsys: pytest.CaptureFixture[str]) -> None:
    mocker.patch("pipdeptree.__main__.find_active_interpreter", return_value=None)

    assert _resolve_python(None) == sys.executable

    captured = capsys.readouterr()
    assert not captured.out
    assert not captured.err


def test_resolve_python_auto_uses_strict_detection(
    tmp_path: Path, mocker: MockFixture, capsys: pytest.CaptureFixture[str]
) -> None:
    mocker.patch("pipdeptree.__main__.detect_active_interpreter", return_value=str(tmp_path))

    assert _resolve_python("auto", log_resolved=True) == str(tmp_path)

    assert capsys.readouterr().err == f"(resolved python: {tmp_path})\n"


def test_resolve_python_auto_fails_when_none_found(mocker: MockFixture, capsys: pytest.CaptureFixture[str]) -> None:
    mocker.patch("pipdeptree._detect_env.find_active_interpreter", return_value=None)

    with pytest.raises(SystemExit):
        _resolve_python("auto")

    assert "Unable to detect virtual environment." in capsys.readouterr().err


def test_resolve_python_explicit_path_passthrough(capsys: pytest.CaptureFixture[str]) -> None:
    assert _resolve_python("/explicit/python") == "/explicit/python"

    captured = capsys.readouterr()
    assert not captured.out
    assert not captured.err


def test_main_default_falls_back_to_sys_executable(mocker: MockFixture, capsys: pytest.CaptureFixture[str]) -> None:
    mocker.patch("pipdeptree.__main__.sys.argv", ["pipdeptree"])
    mocker.patch("pipdeptree.__main__.find_active_interpreter", return_value=None)
    get_installed = mocker.patch("pipdeptree.__main__.get_installed_distributions", return_value=[])

    assert main() == 0

    assert get_installed.call_args.kwargs["interpreter"] == sys.executable
    assert "Unable to detect virtual environment." not in capsys.readouterr().err
