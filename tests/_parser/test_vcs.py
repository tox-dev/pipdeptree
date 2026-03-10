from __future__ import annotations

import subprocess  # noqa: S404
from typing import TYPE_CHECKING
from unittest.mock import Mock

from pipdeptree._parser._vcs import get_vcs_requirement

if TYPE_CHECKING:
    from pathlib import Path

    import pytest


def test_get_vcs_requirement_with_git(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    git_dir = tmp_path / ".git"
    git_dir.mkdir()
    mock_run = Mock()
    mock_run.side_effect = [
        Mock(stdout="https://github.com/user/repo.git\n"),
        Mock(stdout="abc123def456\n"),
    ]
    monkeypatch.setattr("subprocess.run", mock_run)
    result = get_vcs_requirement(str(tmp_path), "mypackage")
    assert result == "git+https://github.com/user/repo.git@abc123def456#egg=mypackage"


def test_get_vcs_requirement_no_git_dir(tmp_path: Path) -> None:
    result = get_vcs_requirement(str(tmp_path), "mypackage")
    assert result is None


def test_get_vcs_requirement_no_remote(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    git_dir = tmp_path / ".git"
    git_dir.mkdir()
    mock_run = Mock(return_value=Mock(stdout=""))
    monkeypatch.setattr("subprocess.run", mock_run)
    result = get_vcs_requirement(str(tmp_path), "mypackage")
    assert result is None


def test_get_vcs_requirement_git_command_fails(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    git_dir = tmp_path / ".git"
    git_dir.mkdir()
    monkeypatch.setattr("subprocess.run", Mock(side_effect=subprocess.CalledProcessError(1, "git")))
    result = get_vcs_requirement(str(tmp_path), "mypackage")
    assert result is None


def test_get_vcs_requirement_git_timeout(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    git_dir = tmp_path / ".git"
    git_dir.mkdir()
    monkeypatch.setattr("subprocess.run", Mock(side_effect=subprocess.TimeoutExpired("git", 5)))
    result = get_vcs_requirement(str(tmp_path), "mypackage")
    assert result is None


def test_get_vcs_requirement_git_not_found(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    git_dir = tmp_path / ".git"
    git_dir.mkdir()
    monkeypatch.setattr("subprocess.run", Mock(side_effect=FileNotFoundError))
    result = get_vcs_requirement(str(tmp_path), "mypackage")
    assert result is None


def test_get_vcs_requirement_no_commit(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    git_dir = tmp_path / ".git"
    git_dir.mkdir()
    mock_run = Mock()
    mock_run.side_effect = [
        Mock(stdout="https://github.com/user/repo.git\n"),
        Mock(stdout=""),
    ]
    monkeypatch.setattr("subprocess.run", mock_run)
    result = get_vcs_requirement(str(tmp_path), "mypackage")
    assert result is None
