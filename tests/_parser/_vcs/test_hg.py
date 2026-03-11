from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from pipdeptree._parser._vcs import VcsError, get_vcs_requirement

from .conftest import raise_file_not_found

if TYPE_CHECKING:
    from pathlib import Path

    from pytest_subprocess import FakeProcess


@pytest.fixture
def hg_repo(tmp_path: Path) -> Path:
    (tmp_path / ".hg").mkdir()
    return tmp_path


def test_hg_basic(hg_repo: Path, fp: FakeProcess) -> None:
    fp.register(["git", "rev-parse", "--show-toplevel"], returncode=1)
    fp.register(["hg", "showconfig", "paths.default"], stdout="https://hg.example.com/repo\n")
    fp.register(["hg", "parents", "--template={node}"], stdout="abcdef1234567890\n")

    result = get_vcs_requirement(str(hg_repo), "mypackage")

    assert result.requirement == "hg+https://hg.example.com/repo@abcdef1234567890#egg=mypackage"
    assert result.vcs_name == "hg"
    assert result.error == VcsError.NONE


def test_hg_protocol_no_prefix(hg_repo: Path, fp: FakeProcess) -> None:
    fp.register(["git", "rev-parse", "--show-toplevel"], returncode=1)
    fp.register(["hg", "showconfig", "paths.default"], stdout="hg://hg.example.com/repo\n")
    fp.register(["hg", "parents", "--template={node}"], stdout="abc123\n")

    result = get_vcs_requirement(str(hg_repo), "mypackage")

    assert result.requirement == "hg://hg.example.com/repo@abc123#egg=mypackage"


def test_hg_no_remote(hg_repo: Path, fp: FakeProcess) -> None:
    fp.register(["git", "rev-parse", "--show-toplevel"], returncode=1)
    fp.register(["hg", "showconfig", "paths.default"], returncode=1)

    result = get_vcs_requirement(str(hg_repo), "mypackage")

    assert result.requirement is None
    assert result.error == VcsError.NO_REMOTE
    assert result.vcs_name == "hg"


def test_hg_empty_remote(hg_repo: Path, fp: FakeProcess) -> None:
    fp.register(["git", "rev-parse", "--show-toplevel"], returncode=1)
    fp.register(["hg", "showconfig", "paths.default"], stdout="")

    result = get_vcs_requirement(str(hg_repo), "mypackage")

    assert result.requirement is None
    assert result.error == VcsError.NO_REMOTE


def test_hg_no_commit(hg_repo: Path, fp: FakeProcess) -> None:
    fp.register(["git", "rev-parse", "--show-toplevel"], returncode=1)
    fp.register(["hg", "showconfig", "paths.default"], stdout="https://hg.example.com/repo\n")
    fp.register(["hg", "parents", "--template={node}"], returncode=1)

    result = get_vcs_requirement(str(hg_repo), "mypackage")

    assert result.requirement is None
    assert result.error == VcsError.NO_REMOTE


def test_hg_command_not_found(hg_repo: Path, fp: FakeProcess) -> None:
    fp.register(["git", "rev-parse", "--show-toplevel"], returncode=1)
    fp.register(["hg", "showconfig", "paths.default"], callback=raise_file_not_found)

    result = get_vcs_requirement(str(hg_repo), "mypackage")

    assert result.requirement is None
    assert result.error == VcsError.COMMAND_NOT_FOUND


def test_hg_local_path_remote(hg_repo: Path, fp: FakeProcess) -> None:
    fp.register(["git", "rev-parse", "--show-toplevel"], returncode=1)
    fp.register(["hg", "showconfig", "paths.default"], stdout=f"{hg_repo}/upstream\n")
    fp.register(["hg", "parents", "--template={node}"], stdout="abc123\n")

    result = get_vcs_requirement(str(hg_repo), "mypackage")

    expected_url = (hg_repo / "upstream").as_uri()
    assert result.requirement == f"hg+{expected_url}@abc123#egg=mypackage"


def test_hg_shared_repo_dotfile(tmp_path: Path, fp: FakeProcess) -> None:
    (tmp_path / ".hg").write_text("/shared/repo/.hg")
    fp.register(["git", "rev-parse", "--show-toplevel"], returncode=1)
    fp.register(["hg", "showconfig", "paths.default"], stdout="https://hg.example.com/repo\n")
    fp.register(["hg", "parents", "--template={node}"], stdout="abc123\n")

    result = get_vcs_requirement(str(tmp_path), "mypackage")

    assert result.requirement == "hg+https://hg.example.com/repo@abc123#egg=mypackage"
    assert result.vcs_name == "hg"


def test_hg_with_subdirectory(tmp_path: Path, fp: FakeProcess) -> None:
    (tmp_path / ".hg").mkdir()
    subdir = tmp_path / "src" / "pkg"
    subdir.mkdir(parents=True)
    (subdir / "setup.py").touch()
    fp.register(["git", "rev-parse", "--show-toplevel"], returncode=1)
    fp.register(["hg", "showconfig", "paths.default"], stdout="https://hg.example.com/repo\n")
    fp.register(["hg", "parents", "--template={node}"], stdout="abc123\n")

    result = get_vcs_requirement(str(subdir), "mypackage")

    assert result.requirement == "hg+https://hg.example.com/repo@abc123#egg=mypackage&subdirectory=src/pkg"
