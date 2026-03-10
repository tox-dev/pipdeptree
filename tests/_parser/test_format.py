from __future__ import annotations

import json
from typing import TYPE_CHECKING
from unittest.mock import Mock

import pytest

from pipdeptree._parser import distribution_to_specifier

if TYPE_CHECKING:
    from pathlib import Path


@pytest.mark.parametrize(
    ("read_text_value", "expected"),
    [
        pytest.param(None, "mypackage==1.0.0", id="regular"),
        pytest.param(
            json.dumps({"url": "file:///home/user/project", "dir_info": {"editable": True}}),
            "-e /home/user/project",
            id="editable",
        ),
        pytest.param(
            json.dumps({"url": "https://github.com/user/repo.git", "vcs_info": {"vcs": "git", "commit_id": "abc123"}}),
            "mypackage @ git+https://github.com/user/repo.git@abc123",
            id="direct-url-vcs",
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


def test_distribution_to_specifier_egg_link_fallback(mocker: pytest.MockerFixture, tmp_path: Path) -> None:
    site_dir = tmp_path / "site-packages"
    site_dir.mkdir()
    egg_link = site_dir / "mypackage.egg-link"
    egg_link.write_text("/path/to/source\n")
    mocker.patch("pipdeptree._parser._editable.site.getsitepackages", return_value=[str(site_dir)])
    mocker.patch("pipdeptree._parser._editable.site.getusersitepackages", return_value=None)
    mocker.patch("pipdeptree._parser._format.get_vcs_requirement", return_value=None)
    distribution = Mock(metadata={"Name": "mypackage"}, version="1.0.0")
    distribution.read_text.return_value = None
    result = distribution_to_specifier(distribution)
    assert result == "-e /path/to/source"


def test_distribution_to_specifier_editable_with_vcs(mocker: pytest.MockerFixture) -> None:
    mocker.patch(
        "pipdeptree._parser._format.get_vcs_requirement",
        return_value="git+https://github.com/user/repo@abc123#egg=mypackage",
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


def test_distribution_to_specifier_no_egg_link_when_direct_url_exists(
    mocker: pytest.MockerFixture, tmp_path: Path
) -> None:
    site_dir = tmp_path / "site-packages"
    site_dir.mkdir()
    egg_link = site_dir / "mypackage.egg-link"
    egg_link.write_text("/path/to/source\n")
    mocker.patch("pipdeptree._parser._editable.site.getsitepackages", return_value=[str(site_dir)])
    mocker.patch("pipdeptree._parser._editable.site.getusersitepackages", return_value=None)
    distribution = Mock(metadata={"Name": "mypackage"}, version="1.0.0")
    distribution.read_text.return_value = json.dumps({"url": "file:///path/to/non-editable", "dir_info": {}})
    result = distribution_to_specifier(distribution)
    assert result == "mypackage @ file:///path/to/non-editable"
