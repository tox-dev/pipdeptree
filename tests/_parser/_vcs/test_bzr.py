from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from pipdeptree._parser._vcs import VcsError, get_vcs_requirement

from .conftest import raise_file_not_found

if TYPE_CHECKING:
    from pathlib import Path

    from pytest_subprocess import FakeProcess


@pytest.fixture
def bzr_repo(tmp_path: Path) -> Path:
    (tmp_path / ".bzr").mkdir()
    return tmp_path


def test_bzr_checkout_branch(bzr_repo: Path, fp: FakeProcess) -> None:
    fp.register(["git", "rev-parse", "--show-toplevel"], returncode=1)
    fp.register(
        ["bzr", "info"],
        stdout="  checkout of branch: https://bzr.example.com/repo\n",
    )
    fp.register(["bzr", "revno"], stdout="42\n")

    result = get_vcs_requirement(str(bzr_repo), "mypackage")

    assert result.requirement == "bzr+https://bzr.example.com/repo@42#egg=mypackage"
    assert result.vcs_name == "bzr"
    assert result.error == VcsError.NONE


def test_bzr_parent_branch(bzr_repo: Path, fp: FakeProcess) -> None:
    fp.register(["git", "rev-parse", "--show-toplevel"], returncode=1)
    fp.register(
        ["bzr", "info"],
        stdout="  parent branch: https://bzr.example.com/parent\n",
    )
    fp.register(["bzr", "revno"], stdout="10\n")

    result = get_vcs_requirement(str(bzr_repo), "mypackage")

    assert result.requirement == "bzr+https://bzr.example.com/parent@10#egg=mypackage"


def test_bzr_protocol_no_prefix(bzr_repo: Path, fp: FakeProcess) -> None:
    fp.register(["git", "rev-parse", "--show-toplevel"], returncode=1)
    fp.register(["bzr", "info"], stdout="  checkout of branch: bzr://bzr.example.com/repo\n")
    fp.register(["bzr", "revno"], stdout="5\n")

    result = get_vcs_requirement(str(bzr_repo), "mypackage")

    assert result.requirement == "bzr://bzr.example.com/repo@5#egg=mypackage"


def test_bzr_no_remote(bzr_repo: Path, fp: FakeProcess) -> None:
    fp.register(["git", "rev-parse", "--show-toplevel"], returncode=1)
    fp.register(["bzr", "info"], stdout="Standalone tree\n")

    result = get_vcs_requirement(str(bzr_repo), "mypackage")

    assert result.requirement is None
    assert result.error == VcsError.NO_REMOTE
    assert result.vcs_name == "bzr"


def test_bzr_info_fails(bzr_repo: Path, fp: FakeProcess) -> None:
    fp.register(["git", "rev-parse", "--show-toplevel"], returncode=1)
    fp.register(["bzr", "info"], returncode=1)

    result = get_vcs_requirement(str(bzr_repo), "mypackage")

    assert result.requirement is None
    assert result.error == VcsError.NO_REMOTE


def test_bzr_revno_fails(bzr_repo: Path, fp: FakeProcess) -> None:
    fp.register(["git", "rev-parse", "--show-toplevel"], returncode=1)
    fp.register(["bzr", "info"], stdout="  checkout of branch: https://bzr.example.com/repo\n")
    fp.register(["bzr", "revno"], returncode=1)

    result = get_vcs_requirement(str(bzr_repo), "mypackage")

    assert result.requirement is None
    assert result.error == VcsError.NO_REMOTE


def test_bzr_command_not_found(bzr_repo: Path, fp: FakeProcess) -> None:
    fp.register(["git", "rev-parse", "--show-toplevel"], returncode=1)
    fp.register(["bzr", "info"], callback=raise_file_not_found)

    result = get_vcs_requirement(str(bzr_repo), "mypackage")

    assert result.requirement is None
    assert result.error == VcsError.COMMAND_NOT_FOUND


def test_bzr_local_path_remote(bzr_repo: Path, fp: FakeProcess) -> None:
    fp.register(["git", "rev-parse", "--show-toplevel"], returncode=1)
    fp.register(["bzr", "info"], stdout=f"  checkout of branch: {bzr_repo}/upstream\n")
    fp.register(["bzr", "revno"], stdout="5\n")

    result = get_vcs_requirement(str(bzr_repo), "mypackage")

    expected_url = (bzr_repo / "upstream").as_uri()
    assert result.requirement == f"bzr+{expected_url}@5#egg=mypackage"


def test_bzr_with_subdirectory(tmp_path: Path, fp: FakeProcess) -> None:
    (tmp_path / ".bzr").mkdir()
    subdir = tmp_path / "sub" / "pkg"
    subdir.mkdir(parents=True)
    (subdir / "setup.py").touch()
    fp.register(["git", "rev-parse", "--show-toplevel"], returncode=1)
    fp.register(["bzr", "info"], stdout="  checkout of branch: https://bzr.example.com/repo\n")
    fp.register(["bzr", "revno"], stdout="7\n")

    result = get_vcs_requirement(str(subdir), "mypackage")

    assert result.requirement == "bzr+https://bzr.example.com/repo@7#egg=mypackage"
    assert "&subdirectory=" not in (result.requirement or "")
