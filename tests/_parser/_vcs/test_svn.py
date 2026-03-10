from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from pipdeptree._parser._vcs import VcsError, get_vcs_requirement

from .conftest import _raise_file_not_found

if TYPE_CHECKING:
    from pathlib import Path

    from pytest_mock import MockerFixture
    from pytest_subprocess import FakeProcess


@pytest.fixture
def svn_repo(tmp_path: Path) -> Path:
    (tmp_path / ".svn").mkdir()
    return tmp_path


_SVN_INFO_XML = """\
<?xml version="1.0" encoding="UTF-8"?>
<info>
  <entry revision="42">
    <url>https://svn.example.com/repo/trunk</url>
  </entry>
</info>
"""


def test_svn_basic(svn_repo: Path, fp: FakeProcess) -> None:
    fp.register(["git", "rev-parse", "--show-toplevel"], returncode=1)
    fp.register(["svn", "info", "--xml"], stdout=_SVN_INFO_XML)
    result = get_vcs_requirement(str(svn_repo), "mypackage")
    assert result.requirement == "svn+https://svn.example.com/repo/trunk@42#egg=mypackage"
    assert result.vcs_name == "svn"
    assert result.error == VcsError.NONE


def test_svn_command_fails(svn_repo: Path, fp: FakeProcess) -> None:
    fp.register(["git", "rev-parse", "--show-toplevel"], returncode=1)
    fp.register(["svn", "info", "--xml"], returncode=1)
    result = get_vcs_requirement(str(svn_repo), "mypackage")
    assert result.requirement is None
    assert result.error == VcsError.NO_REMOTE


def test_svn_invalid_xml(svn_repo: Path, fp: FakeProcess) -> None:
    fp.register(["git", "rev-parse", "--show-toplevel"], returncode=1)
    fp.register(["svn", "info", "--xml"], stdout="not xml at all")
    result = get_vcs_requirement(str(svn_repo), "mypackage")
    assert result.requirement is None
    assert result.error == VcsError.NO_REMOTE


def test_svn_missing_entry(svn_repo: Path, fp: FakeProcess) -> None:
    fp.register(["git", "rev-parse", "--show-toplevel"], returncode=1)
    fp.register(["svn", "info", "--xml"], stdout='<?xml version="1.0"?><info></info>')
    result = get_vcs_requirement(str(svn_repo), "mypackage")
    assert result.requirement is None
    assert result.error == VcsError.NO_REMOTE


def test_svn_missing_url_element(svn_repo: Path, fp: FakeProcess) -> None:
    fp.register(["git", "rev-parse", "--show-toplevel"], returncode=1)
    fp.register(
        ["svn", "info", "--xml"],
        stdout='<?xml version="1.0"?><info><entry revision="10"></entry></info>',
    )
    result = get_vcs_requirement(str(svn_repo), "mypackage")
    assert result.requirement is None


def test_svn_entries_fallback(tmp_path: Path, fp: FakeProcess) -> None:
    svn_dir = tmp_path / ".svn"
    svn_dir.mkdir()
    entries_content = "10\n\ndir\n42\nhttps://svn.example.com/repo/trunk\n"
    (svn_dir / "entries").write_text(entries_content)
    fp.register(["git", "rev-parse", "--show-toplevel"], returncode=1)
    fp.register(["svn", "info", "--xml"], returncode=1)
    result = get_vcs_requirement(str(tmp_path), "mypackage")
    assert result.requirement == "svn+https://svn.example.com/repo/trunk@42#egg=mypackage"


def test_svn_entries_xml_format_ignored(tmp_path: Path, fp: FakeProcess) -> None:
    svn_dir = tmp_path / ".svn"
    svn_dir.mkdir()
    (svn_dir / "entries").write_text("<?xml version='1.0'?><entries/>")
    fp.register(["git", "rev-parse", "--show-toplevel"], returncode=1)
    fp.register(["svn", "info", "--xml"], returncode=1)
    result = get_vcs_requirement(str(tmp_path), "mypackage")
    assert result.requirement is None
    assert result.error == VcsError.NO_REMOTE


def test_svn_entries_too_short(tmp_path: Path, fp: FakeProcess) -> None:
    svn_dir = tmp_path / ".svn"
    svn_dir.mkdir()
    (svn_dir / "entries").write_text("10\n\ndir\n")
    fp.register(["git", "rev-parse", "--show-toplevel"], returncode=1)
    fp.register(["svn", "info", "--xml"], returncode=1)
    result = get_vcs_requirement(str(tmp_path), "mypackage")
    assert result.requirement is None


def test_svn_entries_empty_url(tmp_path: Path, fp: FakeProcess) -> None:
    svn_dir = tmp_path / ".svn"
    svn_dir.mkdir()
    (svn_dir / "entries").write_text("10\n\ndir\n42\n\n")
    fp.register(["git", "rev-parse", "--show-toplevel"], returncode=1)
    fp.register(["svn", "info", "--xml"], returncode=1)
    result = get_vcs_requirement(str(tmp_path), "mypackage")
    assert result.requirement is None


def test_svn_entries_read_error(tmp_path: Path, fp: FakeProcess, mocker: MockerFixture) -> None:
    svn_dir = tmp_path / ".svn"
    svn_dir.mkdir()
    entries = svn_dir / "entries"
    entries.write_text("10\n\ndir\n42\nhttps://svn.example.com/repo/trunk\n")
    fp.register(["git", "rev-parse", "--show-toplevel"], returncode=1)
    fp.register(["svn", "info", "--xml"], returncode=1)
    mocker.patch("pathlib.Path.read_text", side_effect=OSError("Permission denied"))
    result = get_vcs_requirement(str(tmp_path), "mypackage")
    assert result.requirement is None
    assert result.error == VcsError.NO_REMOTE


def test_svn_command_not_found(svn_repo: Path, fp: FakeProcess) -> None:
    fp.register(["git", "rev-parse", "--show-toplevel"], returncode=1)
    fp.register(["svn", "info", "--xml"], callback=_raise_file_not_found)
    result = get_vcs_requirement(str(svn_repo), "mypackage")
    assert result.requirement is None
    assert result.error == VcsError.COMMAND_NOT_FOUND


def test_svn_with_subdirectory(tmp_path: Path, fp: FakeProcess) -> None:
    (tmp_path / ".svn").mkdir()
    subdir = tmp_path / "src" / "pkg"
    subdir.mkdir(parents=True)
    (subdir / "pyproject.toml").touch()
    fp.register(["git", "rev-parse", "--show-toplevel"], returncode=1)
    fp.register(["svn", "info", "--xml"], stdout=_SVN_INFO_XML)
    result = get_vcs_requirement(str(subdir), "mypackage")
    assert result.requirement == "svn+https://svn.example.com/repo/trunk@42#egg=mypackage"
    assert "&subdirectory=" not in (result.requirement or "")
