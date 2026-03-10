from __future__ import annotations

import subprocess  # noqa: S404
from typing import TYPE_CHECKING
from unittest.mock import Mock

import pytest

from pipdeptree._parser._vcs import (
    _build_vcs_requirement,
    _get_subdirectory,
    _normalize_egg_name,
    _normalize_git_url,
    get_vcs_requirement,
)

if TYPE_CHECKING:
    from pathlib import Path


def test_get_vcs_requirement_with_git(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    git_dir = tmp_path / ".git"
    git_dir.mkdir()
    mock_run = Mock()
    mock_run.side_effect = [
        Mock(stdout=str(tmp_path) + "\n"),
        Mock(stdout="remote.origin.url https://github.com/user/repo.git\n"),
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
        Mock(stdout="remote.origin.url https://github.com/user/repo.git\n"),
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


def test_get_vcs_requirement_empty_repo_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("subprocess.run", Mock(return_value=Mock(stdout="")))
    result = get_vcs_requirement(str(tmp_path), "mypackage")
    assert result is None


def test_get_vcs_requirement_prefers_origin(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    mock_run = Mock()
    mock_run.side_effect = [
        Mock(stdout=str(tmp_path) + "\n"),
        Mock(
            stdout="remote.upstream.url https://upstream.com/repo.git\nremote.origin.url https://origin.com/repo.git\n"
        ),
        Mock(stdout="abc123\n"),
    ]
    monkeypatch.setattr("subprocess.run", mock_run)
    result = get_vcs_requirement(str(tmp_path), "mypackage")
    assert result == "git+https://origin.com/repo.git@abc123#egg=mypackage"


def test_get_vcs_requirement_falls_back_to_first_remote(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    mock_run = Mock()
    mock_run.side_effect = [
        Mock(stdout=str(tmp_path) + "\n"),
        Mock(stdout="remote.upstream.url https://upstream.com/repo.git\n"),
        Mock(stdout="abc123\n"),
    ]
    monkeypatch.setattr("subprocess.run", mock_run)
    result = get_vcs_requirement(str(tmp_path), "mypackage")
    assert result == "git+https://upstream.com/repo.git@abc123#egg=mypackage"


def test_get_vcs_requirement_empty_remote_url(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    mock_run = Mock()
    mock_run.side_effect = [
        Mock(stdout=str(tmp_path) + "\n"),
        Mock(stdout="remote.origin.url \n"),
    ]
    monkeypatch.setattr("subprocess.run", mock_run)
    result = get_vcs_requirement(str(tmp_path), "mypackage")
    assert result is None


def test_get_vcs_requirement_remote_command_fails(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    mock_run = Mock()
    mock_run.side_effect = [
        Mock(stdout=str(tmp_path) + "\n"),
        subprocess.CalledProcessError(1, "git"),
    ]
    monkeypatch.setattr("subprocess.run", mock_run)
    result = get_vcs_requirement(str(tmp_path), "mypackage")
    assert result is None


def test_get_vcs_requirement_commit_command_fails(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    mock_run = Mock()
    mock_run.side_effect = [
        Mock(stdout=str(tmp_path) + "\n"),
        Mock(stdout="remote.origin.url https://github.com/user/repo.git\n"),
        subprocess.CalledProcessError(1, "git"),
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
        Mock(stdout="remote.origin.url https://github.com/user/repo.git\n"),
        Mock(stdout=""),
    ]
    monkeypatch.setattr("subprocess.run", mock_run)
    result = get_vcs_requirement(str(tmp_path), "mypackage")
    assert result is None


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        pytest.param("ssh://bob@server/foo/bar.git", "ssh://bob@server/foo/bar.git", id="ssh-with-user"),
        pytest.param("git://bob@server/foo/bar.git", "git://bob@server/foo/bar.git", id="git-protocol"),
        pytest.param("ssh://server/foo/bar.git", "ssh://server/foo/bar.git", id="ssh-no-user"),
        pytest.param("git@example.com:foo/bar.git", "ssh://git@example.com/foo/bar.git", id="scp-git-user"),
        pytest.param("example.com:foo.git", "ssh://example.com/foo.git", id="scp-no-user"),
        pytest.param("https://example.com/foo", "https://example.com/foo", id="https"),
        pytest.param("http://example.com/foo/bar.git", "http://example.com/foo/bar.git", id="http"),
        pytest.param("https://bob@example.com/foo", "https://bob@example.com/foo", id="https-with-user"),
    ],
)
def test_normalize_git_url(url: str, expected: str) -> None:
    result = _normalize_git_url(url)
    assert result == expected


def test_build_vcs_requirement_with_git_protocol(tmp_path: Path) -> None:
    result = _build_vcs_requirement(
        remote_url="git://github.com/user/repo.git",
        commit_id="abc123",
        package_name="my-package",
        location=str(tmp_path),
        repo_root=str(tmp_path),
    )
    assert result == "git://github.com/user/repo.git@abc123#egg=my_package"


def test_build_vcs_requirement_with_https(tmp_path: Path) -> None:
    result = _build_vcs_requirement(
        remote_url="https://github.com/user/repo.git",
        commit_id="abc123",
        package_name="my-package",
        location=str(tmp_path),
        repo_root=str(tmp_path),
    )
    assert result == "git+https://github.com/user/repo.git@abc123#egg=my_package"


def test_normalize_git_url_local_path(tmp_path: Path) -> None:
    repo = tmp_path / "project.git"
    repo.mkdir()
    result = _normalize_git_url(str(repo))
    assert result == repo.as_uri()


@pytest.mark.parametrize(
    "url",
    [
        pytest.param("c:/piffle/wiffle/waffle/poffle.git", id="windows-forward-slash"),
        pytest.param(r"c:\faffle\waffle\woffle\piffle.git", id="windows-backslash"),
        pytest.param("/muffle/fuffle/pufffle/fluffle.git", id="unix-absolute-path"),
    ],
)
def test_normalize_git_url_rejects_non_scp_paths(url: str) -> None:
    result = _normalize_git_url(url)
    assert result == url


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
