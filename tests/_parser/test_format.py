from __future__ import annotations

import json
from typing import TYPE_CHECKING
from unittest.mock import Mock

import pytest

from pipdeptree._parser import distribution_to_specifier
from pipdeptree._parser.vcs import VcsError, VcsResult

if TYPE_CHECKING:
    from pathlib import Path

    from pytest_mock import MockerFixture


@pytest.mark.parametrize(
    ("read_text_value", "expected"),
    [
        pytest.param(None, "mypackage==1.0.0", id="regular"),
        pytest.param(
            json.dumps({"url": "https://github.com/user/repo.git", "vcs_info": {"vcs": "git", "commit_id": "abc123"}}),
            "mypackage @ git+https://github.com/user/repo.git@abc123",
            id="direct-url-vcs",
        ),
        pytest.param(
            json.dumps({"url": "https://github.com/user/repo.git", "vcs_info": {"vcs": "git"}}),
            "mypackage @ git+https://github.com/user/repo.git",
            id="direct-url-vcs-no-commit-id",
        ),
        pytest.param(
            json.dumps({
                "url": "https://github.com/user/repo.git",
                "vcs_info": {"vcs": "git", "commit_id": "abc123"},
                "subdirectory": "src/pkg",
            }),
            "mypackage @ git+https://github.com/user/repo.git@abc123#subdirectory=src/pkg",
            id="direct-url-vcs-subdirectory",
        ),
        pytest.param(
            json.dumps({"url": "https://example.com/package.tar.gz", "archive_info": {"hash": "sha256=abc123"}}),
            "mypackage @ https://example.com/package.tar.gz#sha256=abc123",
            id="direct-url-archive-hash",
        ),
        pytest.param(
            json.dumps({"url": "https://example.com/package.tar.gz", "archive_info": {}}),
            "mypackage @ https://example.com/package.tar.gz",
            id="direct-url-archive-no-hash",
        ),
        pytest.param(
            json.dumps({
                "url": "https://example.com/package.tar.gz",
                "archive_info": {"hash": "sha256=abc123"},
                "subdirectory": "src/pkg",
            }),
            "mypackage @ https://example.com/package.tar.gz#sha256=abc123&subdirectory=src/pkg",
            id="direct-url-archive-hash-subdirectory",
        ),
        pytest.param(
            json.dumps({"url": "file:///home/user/project", "dir_info": {"editable": False}}),
            "mypackage @ file:///home/user/project",
            id="direct-url-dir",
        ),
        pytest.param(
            json.dumps({"url": "file:///home/user/project", "dir_info": {}, "subdirectory": "src/pkg"}),
            "mypackage @ file:///home/user/project#subdirectory=src/pkg",
            id="direct-url-dir-subdirectory",
        ),
    ],
)
def test_distribution_to_specifier(read_text_value: str | None, expected: str) -> None:
    distribution = Mock(metadata={"Name": "mypackage"}, version="1.0.0")
    distribution.read_text.return_value = read_text_value
    result = distribution_to_specifier(distribution)
    assert result == expected


def test_distribution_to_specifier_editable_no_vcs(mocker: MockerFixture) -> None:
    mocker.patch(
        "pipdeptree._parser.format.get_vcs_requirement",
        return_value=VcsResult(None, error=VcsError.NO_VCS),
    )
    distribution = Mock(metadata={"Name": "mypackage"}, version="1.0.0")
    distribution.read_text.return_value = json.dumps({"url": "file:///path/to/source", "dir_info": {"editable": True}})
    result = distribution_to_specifier(distribution)
    assert result == "# Editable install with no version control (mypackage==1.0.0)\n-e /path/to/source"


def test_distribution_to_specifier_editable_no_remote(mocker: MockerFixture) -> None:
    mocker.patch(
        "pipdeptree._parser.format.get_vcs_requirement",
        return_value=VcsResult(None, vcs_name="git", error=VcsError.NO_REMOTE),
    )
    distribution = Mock(metadata={"Name": "mypackage"}, version="1.0.0")
    distribution.read_text.return_value = json.dumps({"url": "file:///path/to/source", "dir_info": {"editable": True}})
    result = distribution_to_specifier(distribution)
    assert result == "# Editable git install with no remote (mypackage==1.0.0)\n-e /path/to/source"


def test_distribution_to_specifier_editable_invalid_remote(mocker: MockerFixture) -> None:
    mocker.patch(
        "pipdeptree._parser.format.get_vcs_requirement",
        return_value=VcsResult(None, vcs_name="git", error=VcsError.INVALID_REMOTE),
    )
    distribution = Mock(metadata={"Name": "mypackage"}, version="1.0.0")
    distribution.read_text.return_value = json.dumps({"url": "file:///path/to/source", "dir_info": {"editable": True}})
    result = distribution_to_specifier(distribution)
    expected_comment = "# Editable git install (mypackage==1.0.0) with either a deleted local remote or invalid URI:"
    assert result == f"{expected_comment}\n-e /path/to/source"


def test_distribution_to_specifier_editable_command_not_found(mocker: MockerFixture) -> None:
    mocker.patch(
        "pipdeptree._parser.format.get_vcs_requirement",
        return_value=VcsResult(None, error=VcsError.COMMAND_NOT_FOUND),
    )
    distribution = Mock(metadata={"Name": "mypackage"}, version="1.0.0")
    distribution.read_text.return_value = json.dumps({"url": "file:///path/to/source", "dir_info": {"editable": True}})
    result = distribution_to_specifier(distribution)
    assert result == "-e /path/to/source"


def test_distribution_to_specifier_egg_link_fallback(mocker: MockerFixture, tmp_path: Path) -> None:
    site_dir = tmp_path / "site-packages"
    site_dir.mkdir()
    egg_link = site_dir / "mypackage.egg-link"
    egg_link.write_text("/path/to/source\n")
    mocker.patch("pipdeptree._parser.editable.sys.path", [])
    mocker.patch("pipdeptree._parser.editable.site.getsitepackages", return_value=[str(site_dir)])
    mocker.patch("pipdeptree._parser.editable.site.getusersitepackages", return_value=None)
    mocker.patch(
        "pipdeptree._parser.format.get_vcs_requirement",
        return_value=VcsResult(None, error=VcsError.NO_VCS),
    )
    distribution = Mock(metadata={"Name": "mypackage"}, version="1.0.0")
    distribution.read_text.return_value = None
    result = distribution_to_specifier(distribution)
    assert "# Editable install with no version control (mypackage==1.0.0)" in result
    assert "-e /path/to/source" in result


def test_distribution_to_specifier_editable_with_vcs(mocker: MockerFixture) -> None:
    mocker.patch(
        "pipdeptree._parser.format.get_vcs_requirement",
        return_value=VcsResult("git+https://github.com/user/repo@abc123#egg=mypackage", vcs_name="git"),
    )
    distribution = Mock(metadata={"Name": "mypackage"}, version="1.0.0")
    distribution.read_text.return_value = json.dumps({"url": "file:///path/to/source", "dir_info": {"editable": True}})
    result = distribution_to_specifier(distribution)
    assert result == "-e git+https://github.com/user/repo@abc123#egg=mypackage"


def test_distribution_to_specifier_invalid_version() -> None:
    distribution = Mock(metadata={"Name": "mypackage"}, version="not-a-valid-version")
    distribution.read_text.return_value = None
    result = distribution_to_specifier(distribution)
    assert result == "mypackage===not-a-valid-version"


def test_distribution_to_specifier_no_egg_link_when_direct_url_exists(mocker: MockerFixture, tmp_path: Path) -> None:
    site_dir = tmp_path / "site-packages"
    site_dir.mkdir()
    egg_link = site_dir / "mypackage.egg-link"
    egg_link.write_text("/path/to/source\n")
    mocker.patch("pipdeptree._parser.editable.sys.path", [])
    mocker.patch("pipdeptree._parser.editable.site.getsitepackages", return_value=[str(site_dir)])
    mocker.patch("pipdeptree._parser.editable.site.getusersitepackages", return_value=None)
    distribution = Mock(metadata={"Name": "mypackage"}, version="1.0.0")
    distribution.read_text.return_value = json.dumps({"url": "file:///path/to/non-editable", "dir_info": {}})
    result = distribution_to_specifier(distribution)
    assert result == "mypackage @ file:///path/to/non-editable"


def test_distribution_to_specifier_credential_redaction() -> None:
    distribution = Mock(metadata={"Name": "mypackage"}, version="1.0.0")
    distribution.read_text.return_value = json.dumps({
        "url": "https://user:secret@example.com/package.tar.gz",
        "archive_info": {},
    })
    result = distribution_to_specifier(distribution)
    assert "user:secret" not in result
    assert result == "mypackage @ https://example.com/package.tar.gz"
