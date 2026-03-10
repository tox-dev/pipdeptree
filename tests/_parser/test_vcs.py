from __future__ import annotations

import subprocess  # noqa: S404
from typing import TYPE_CHECKING
from unittest.mock import Mock

import pytest

from pipdeptree._parser._vcs import _get_subdirectory, _normalize_egg_name, _normalize_git_url, get_vcs_requirement

if TYPE_CHECKING:
    from pathlib import Path


def test_get_vcs_requirement_with_git(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    git_dir = tmp_path / ".git"
    git_dir.mkdir()
    mock_run = Mock()
    mock_run.side_effect = [
        Mock(stdout=str(tmp_path) + "\n"),
        Mock(stdout="https://github.com/user/repo.git\n"),
        Mock(stdout="abc123def456\n"),
    ]
    monkeypatch.setattr("subprocess.run", mock_run)
    result = get_vcs_requirement(str(tmp_path), "mypackage")
    assert result == "git+https://github.com/user/repo.git@abc123def456#egg=mypackage"


def test_get_vcs_requirement_with_subdirectory(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo_root = tmp_path
    subdir = tmp_path / "src" / "pkg"
    subdir.mkdir(parents=True)
    mock_run = Mock()
    mock_run.side_effect = [
        Mock(stdout=str(repo_root) + "\n"),
        Mock(stdout="https://github.com/user/repo.git\n"),
        Mock(stdout="abc123\n"),
    ]
    monkeypatch.setattr("subprocess.run", mock_run)
    result = get_vcs_requirement(str(subdir), "mypackage")
    assert result == "git+https://github.com/user/repo.git@abc123#egg=mypackage&subdirectory=src/pkg"


def test_get_vcs_requirement_no_git_repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("subprocess.run", Mock(side_effect=subprocess.CalledProcessError(1, "git")))
    result = get_vcs_requirement(str(tmp_path), "mypackage")
    assert result is None


def test_get_vcs_requirement_no_remote(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    mock_run = Mock()
    mock_run.side_effect = [
        Mock(stdout=str(tmp_path) + "\n"),
        Mock(stdout=""),
    ]
    monkeypatch.setattr("subprocess.run", mock_run)
    result = get_vcs_requirement(str(tmp_path), "mypackage")
    assert result is None


def test_get_vcs_requirement_git_command_fails(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("subprocess.run", Mock(side_effect=subprocess.CalledProcessError(1, "git")))
    result = get_vcs_requirement(str(tmp_path), "mypackage")
    assert result is None


def test_get_vcs_requirement_git_timeout(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("subprocess.run", Mock(side_effect=subprocess.TimeoutExpired("git", 5)))
    result = get_vcs_requirement(str(tmp_path), "mypackage")
    assert result is None


def test_get_vcs_requirement_git_not_found(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("subprocess.run", Mock(side_effect=FileNotFoundError))
    result = get_vcs_requirement(str(tmp_path), "mypackage")
    assert result is None


def test_get_vcs_requirement_no_commit(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    mock_run = Mock()
    mock_run.side_effect = [
        Mock(stdout=str(tmp_path) + "\n"),
        Mock(stdout="https://github.com/user/repo.git\n"),
        Mock(stdout=""),
    ]
    monkeypatch.setattr("subprocess.run", mock_run)
    result = get_vcs_requirement(str(tmp_path), "mypackage")
    assert result is None


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        pytest.param("https://github.com/user/repo.git", "https://github.com/user/repo.git", id="https"),
        pytest.param("git@github.com:user/repo.git", "ssh://github.com/user/repo.git", id="scp-style"),
        pytest.param("user@host.com:path/repo.git", "ssh://host.com/path/repo.git", id="scp-with-user"),
        pytest.param("git://github.com/user/repo.git", "github.com/user/repo.git", id="git-protocol"),
        pytest.param("file:///local/path/repo", "file:///local/path/repo", id="file-url"),
        pytest.param("ssh://git@github.com/user/repo.git", "ssh://git@github.com/user/repo.git", id="ssh-url"),
    ],
)
def test_normalize_git_url(url: str, expected: str) -> None:
    result = _normalize_git_url(url)
    assert result == expected


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        pytest.param("my-package", "my_package", id="dash-to-underscore"),
        pytest.param("my_package", "my_package", id="already-underscore"),
        pytest.param("mypackage", "mypackage", id="no-special-chars"),
        pytest.param("my-multi-part-name", "my_multi_part_name", id="multiple-dashes"),
    ],
)
def test_normalize_egg_name(name: str, expected: str) -> None:
    result = _normalize_egg_name(name)
    assert result == expected


def test_get_subdirectory(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    subdir = repo_root / "src" / "pkg"
    subdir.mkdir(parents=True)
    result = _get_subdirectory(str(subdir), str(repo_root))
    assert result == "src/pkg"


def test_get_subdirectory_at_root(tmp_path: Path) -> None:
    result = _get_subdirectory(str(tmp_path), str(tmp_path))
    assert result is None


def test_get_subdirectory_invalid_paths() -> None:
    result = _get_subdirectory("/unrelated/path", "/repo/root")
    assert result is None
