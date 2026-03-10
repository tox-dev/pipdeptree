from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from pipdeptree._parser._vcs import VcsError, get_vcs_requirement

from .conftest import _raise_file_not_found, _raise_timeout

if TYPE_CHECKING:
    from pathlib import Path

    from pytest_subprocess import FakeProcess


@pytest.mark.parametrize(
    ("remote_url", "expected_url"),
    [
        pytest.param("https://github.com/user/repo.git", "git+https://github.com/user/repo.git", id="https"),
        pytest.param("http://example.com/repo.git", "git+http://example.com/repo.git", id="http"),
        pytest.param("git://github.com/user/repo.git", "git+git://github.com/user/repo.git", id="git-protocol"),
        pytest.param("ssh://git@github.com/user/repo.git", "git+ssh://git@github.com/user/repo.git", id="ssh"),
        pytest.param("git@github.com:user/repo.git", "git+ssh://git@github.com/user/repo.git", id="scp-style"),
        pytest.param("github.com:user/repo.git", "git+ssh://github.com/user/repo.git", id="scp-no-user"),
    ],
)
def test_get_vcs_requirement_url_normalization(
    tmp_path: Path, fp: FakeProcess, remote_url: str, expected_url: str
) -> None:
    fp.register(["git", "rev-parse", "--show-toplevel"], stdout=f"{tmp_path}\n")
    fp.register(["git", "config", "--get-regexp", r"remote\..*\.url"], stdout=f"remote.origin.url {remote_url}\n")
    fp.register(["git", "rev-parse", "HEAD"], stdout="abc123\n")
    result = get_vcs_requirement(str(tmp_path), "mypackage")
    assert result.requirement == f"{expected_url}@abc123#egg=mypackage"
    assert result.vcs_name == "git"
    assert result.error == VcsError.NONE


@pytest.mark.parametrize(
    ("package_name", "expected_egg"),
    [
        pytest.param("my-package", "my_package", id="dash-to-underscore"),
        pytest.param("my_package", "my_package", id="already-underscore"),
        pytest.param("mypackage", "mypackage", id="no-special-chars"),
        pytest.param("zope-interface", "zope_interface", id="real-world-example"),
    ],
)
def test_get_vcs_requirement_egg_name_normalization(
    tmp_path: Path, fp: FakeProcess, package_name: str, expected_egg: str
) -> None:
    fp.register(["git", "rev-parse", "--show-toplevel"], stdout=f"{tmp_path}\n")
    fp.register(
        ["git", "config", "--get-regexp", r"remote\..*\.url"],
        stdout="remote.origin.url https://github.com/user/repo.git\n",
    )
    fp.register(["git", "rev-parse", "HEAD"], stdout="abc123\n")
    result = get_vcs_requirement(str(tmp_path), package_name)
    assert result.requirement == f"git+https://github.com/user/repo.git@abc123#egg={expected_egg}"


def test_get_vcs_requirement_with_subdirectory(tmp_path: Path, fp: FakeProcess) -> None:
    repo_root = tmp_path
    subdir = tmp_path / "src" / "pkg"
    subdir.mkdir(parents=True)
    (subdir / "pyproject.toml").touch()
    fp.register(["git", "rev-parse", "--show-toplevel"], stdout=f"{repo_root}\n")
    fp.register(
        ["git", "config", "--get-regexp", r"remote\..*\.url"],
        stdout="remote.origin.url https://github.com/user/repo.git\n",
    )
    fp.register(["git", "rev-parse", "HEAD"], stdout="abc123\n")
    result = get_vcs_requirement(str(subdir), "mypackage")
    assert result.requirement == "git+https://github.com/user/repo.git@abc123#egg=mypackage&subdirectory=src/pkg"


def test_get_vcs_requirement_no_subdirectory_when_at_root(tmp_path: Path, fp: FakeProcess) -> None:
    (tmp_path / "pyproject.toml").touch()
    fp.register(["git", "rev-parse", "--show-toplevel"], stdout=f"{tmp_path}\n")
    fp.register(
        ["git", "config", "--get-regexp", r"remote\..*\.url"],
        stdout="remote.origin.url https://github.com/user/repo.git\n",
    )
    fp.register(["git", "rev-parse", "HEAD"], stdout="abc123\n")
    result = get_vcs_requirement(str(tmp_path), "mypackage")
    assert result.requirement == "git+https://github.com/user/repo.git@abc123#egg=mypackage"
    assert "&subdirectory=" not in (result.requirement or "")


def test_get_vcs_requirement_local_path_remote(tmp_path: Path, fp: FakeProcess) -> None:
    local_repo = tmp_path / "local-repo.git"
    local_repo.mkdir()
    fp.register(["git", "rev-parse", "--show-toplevel"], stdout=f"{tmp_path}\n")
    fp.register(["git", "config", "--get-regexp", r"remote\..*\.url"], stdout=f"remote.origin.url {local_repo}\n")
    fp.register(["git", "rev-parse", "HEAD"], stdout="abc123\n")
    result = get_vcs_requirement(str(tmp_path), "mypackage")
    assert result.requirement == f"git+{local_repo.as_uri()}@abc123#egg=mypackage"


def test_get_vcs_requirement_relative_path_remote(tmp_path: Path, fp: FakeProcess) -> None:
    repo_dir = tmp_path / "project"
    repo_dir.mkdir()
    upstream = tmp_path / "upstream.git"
    upstream.mkdir()
    fp.register(["git", "rev-parse", "--show-toplevel"], stdout=f"{repo_dir}\n")
    fp.register(["git", "config", "--get-regexp", r"remote\..*\.url"], stdout="remote.origin.url ../upstream.git\n")
    fp.register(["git", "rev-parse", "HEAD"], stdout="abc123\n")
    result = get_vcs_requirement(str(repo_dir), "mypackage")
    assert result.requirement == f"git+{upstream.resolve().as_uri()}@abc123#egg=mypackage"


def test_get_vcs_requirement_prefers_origin(tmp_path: Path, fp: FakeProcess) -> None:
    fp.register(["git", "rev-parse", "--show-toplevel"], stdout=f"{tmp_path}\n")
    fp.register(
        ["git", "config", "--get-regexp", r"remote\..*\.url"],
        stdout="remote.upstream.url https://upstream.com/repo.git\nremote.origin.url https://origin.com/repo.git\n",
    )
    fp.register(["git", "rev-parse", "HEAD"], stdout="abc123\n")
    result = get_vcs_requirement(str(tmp_path), "mypackage")
    assert result.requirement == "git+https://origin.com/repo.git@abc123#egg=mypackage"


def test_get_vcs_requirement_falls_back_to_first_remote(tmp_path: Path, fp: FakeProcess) -> None:
    fp.register(["git", "rev-parse", "--show-toplevel"], stdout=f"{tmp_path}\n")
    fp.register(
        ["git", "config", "--get-regexp", r"remote\..*\.url"],
        stdout="remote.upstream.url https://upstream.com/repo.git\n",
    )
    fp.register(["git", "rev-parse", "HEAD"], stdout="abc123\n")
    result = get_vcs_requirement(str(tmp_path), "mypackage")
    assert result.requirement == "git+https://upstream.com/repo.git@abc123#egg=mypackage"


def test_get_vcs_requirement_no_remote(tmp_path: Path, fp: FakeProcess) -> None:
    fp.register(["git", "rev-parse", "--show-toplevel"], stdout=f"{tmp_path}\n")
    fp.register(["git", "config", "--get-regexp", r"remote\..*\.url"], stdout="")
    result = get_vcs_requirement(str(tmp_path), "mypackage")
    assert result.requirement is None
    assert result.error == VcsError.NO_REMOTE
    assert result.vcs_name == "git"


def test_get_vcs_requirement_empty_remote_url(tmp_path: Path, fp: FakeProcess) -> None:
    fp.register(["git", "rev-parse", "--show-toplevel"], stdout=f"{tmp_path}\n")
    fp.register(["git", "config", "--get-regexp", r"remote\..*\.url"], stdout="remote.origin.url \n")
    result = get_vcs_requirement(str(tmp_path), "mypackage")
    assert result.requirement is None
    assert result.error == VcsError.NO_REMOTE


def test_get_vcs_requirement_no_commit(tmp_path: Path, fp: FakeProcess) -> None:
    fp.register(["git", "rev-parse", "--show-toplevel"], stdout=f"{tmp_path}\n")
    fp.register(
        ["git", "config", "--get-regexp", r"remote\..*\.url"],
        stdout="remote.origin.url https://github.com/user/repo.git\n",
    )
    fp.register(["git", "rev-parse", "HEAD"], stdout="")
    result = get_vcs_requirement(str(tmp_path), "mypackage")
    assert result.requirement is None
    assert result.error == VcsError.NO_REMOTE


def test_get_vcs_requirement_remote_command_fails(tmp_path: Path, fp: FakeProcess) -> None:
    fp.register(["git", "rev-parse", "--show-toplevel"], stdout=f"{tmp_path}\n")
    fp.register(["git", "config", "--get-regexp", r"remote\..*\.url"], returncode=1)
    result = get_vcs_requirement(str(tmp_path), "mypackage")
    assert result.requirement is None


def test_get_vcs_requirement_commit_command_fails(tmp_path: Path, fp: FakeProcess) -> None:
    fp.register(["git", "rev-parse", "--show-toplevel"], stdout=f"{tmp_path}\n")
    fp.register(
        ["git", "config", "--get-regexp", r"remote\..*\.url"],
        stdout="remote.origin.url https://github.com/user/repo.git\n",
    )
    fp.register(["git", "rev-parse", "HEAD"], returncode=1)
    result = get_vcs_requirement(str(tmp_path), "mypackage")
    assert result.requirement is None


def test_get_vcs_requirement_git_timeout(tmp_path: Path, fp: FakeProcess) -> None:
    fp.register(["git", "rev-parse", "--show-toplevel"], callback=_raise_timeout)
    result = get_vcs_requirement(str(tmp_path), "mypackage")
    assert result.requirement is None


def test_get_vcs_requirement_git_not_found(tmp_path: Path, fp: FakeProcess) -> None:
    fp.register(["git", "rev-parse", "--show-toplevel"], callback=_raise_file_not_found)
    result = get_vcs_requirement(str(tmp_path), "mypackage")
    assert result.requirement is None


def test_get_vcs_requirement_invalid_remote(tmp_path: Path, fp: FakeProcess) -> None:
    fp.register(["git", "rev-parse", "--show-toplevel"], stdout=f"{tmp_path}\n")
    fp.register(["git", "config", "--get-regexp", r"remote\..*\.url"], stdout="remote.origin.url :invalid:url:format\n")
    fp.register(["git", "rev-parse", "HEAD"], stdout="abc123\n")
    result = get_vcs_requirement(str(tmp_path), "mypackage")
    assert result.requirement is None
    assert result.error == VcsError.INVALID_REMOTE
    assert result.vcs_name == "git"


def test_get_vcs_requirement_remote_timeout(tmp_path: Path, fp: FakeProcess) -> None:
    fp.register(["git", "rev-parse", "--show-toplevel"], stdout=f"{tmp_path}\n")
    fp.register(["git", "config", "--get-regexp", r"remote\..*\.url"], callback=_raise_timeout)
    result = get_vcs_requirement(str(tmp_path), "mypackage")
    assert result.requirement is None


def test_get_vcs_requirement_remote_not_found(tmp_path: Path, fp: FakeProcess) -> None:
    fp.register(["git", "rev-parse", "--show-toplevel"], stdout=f"{tmp_path}\n")
    fp.register(["git", "config", "--get-regexp", r"remote\..*\.url"], callback=_raise_file_not_found)
    result = get_vcs_requirement(str(tmp_path), "mypackage")
    assert result.requirement is None
