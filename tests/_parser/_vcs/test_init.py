from __future__ import annotations

from typing import TYPE_CHECKING

from pipdeptree._parser._vcs import VcsError, VcsResult, get_vcs_requirement

if TYPE_CHECKING:
    from pathlib import Path

    from pytest_mock import MockerFixture
    from pytest_subprocess import FakeProcess


def test_vcs_result_dataclass() -> None:
    result = VcsResult(requirement=None, vcs_name="git", error=VcsError.NO_REMOTE)

    assert result.requirement is None
    assert result.vcs_name == "git"
    assert result.error == VcsError.NO_REMOTE


def test_get_vcs_requirement_no_vcs(tmp_path: Path, fp: FakeProcess) -> None:
    fp.register(["git", "rev-parse", "--show-toplevel"], returncode=1)

    result = get_vcs_requirement(str(tmp_path), "mypackage")

    assert result.requirement is None
    assert result.error == VcsError.NO_VCS


def test_get_vcs_requirement_empty_repo_root(tmp_path: Path, fp: FakeProcess) -> None:
    fp.register(["git", "rev-parse", "--show-toplevel"], stdout="")

    result = get_vcs_requirement(str(tmp_path), "mypackage")

    assert result.requirement is None
    assert result.error == VcsError.NO_VCS


def test_get_vcs_requirement_innermost_repo_wins(tmp_path: Path, fp: FakeProcess) -> None:
    outer = tmp_path / "outer"
    inner = outer / "inner"
    inner.mkdir(parents=True)
    (outer / ".hg").mkdir()
    fp.register(["git", "rev-parse", "--show-toplevel"], stdout=f"{inner}\n")
    fp.register(
        ["git", "config", "--get-regexp", r"remote\..*\.url"],
        stdout="remote.origin.url https://github.com/inner/repo.git\n",
    )
    fp.register(["git", "rev-parse", "HEAD"], stdout="abc123\n")

    result = get_vcs_requirement(str(inner), "mypackage")

    assert result.vcs_name == "git"
    assert result.requirement is not None
    assert "inner/repo" in result.requirement


def test_get_vcs_requirement_no_subdirectory_without_installable_dir(tmp_path: Path, fp: FakeProcess) -> None:
    subdir = tmp_path / "deep" / "nested"
    subdir.mkdir(parents=True)
    fp.register(["git", "rev-parse", "--show-toplevel"], stdout=f"{tmp_path}\n")
    fp.register(
        ["git", "config", "--get-regexp", r"remote\..*\.url"],
        stdout="remote.origin.url https://github.com/user/repo.git\n",
    )
    fp.register(["git", "rev-parse", "HEAD"], stdout="abc123\n")

    result = get_vcs_requirement(str(subdir), "mypackage")

    assert result.requirement is not None
    assert "&subdirectory=" not in result.requirement


def test_get_vcs_requirement_no_subdirectory_on_samefile_error(
    tmp_path: Path, fp: FakeProcess, mocker: MockerFixture
) -> None:
    subdir = tmp_path / "sub"
    subdir.mkdir()
    (subdir / "pyproject.toml").touch()
    fp.register(["git", "rev-parse", "--show-toplevel"], stdout=f"{tmp_path}\n")
    fp.register(
        ["git", "config", "--get-regexp", r"remote\..*\.url"],
        stdout="remote.origin.url https://github.com/user/repo.git\n",
    )
    fp.register(["git", "rev-parse", "HEAD"], stdout="abc123\n")
    mocker.patch("pathlib.Path.samefile", side_effect=OSError("broken"))

    result = get_vcs_requirement(str(subdir), "mypackage")

    assert result.requirement is not None
    assert "&subdirectory=" not in result.requirement
