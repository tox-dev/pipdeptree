from __future__ import annotations

import json
from typing import TYPE_CHECKING
from unittest.mock import Mock

import pytest

from pipdeptree._parser import distribution_to_specifier
from pipdeptree._parser._direct_url import ArchiveInfo, DirectUrl, DirInfo, VcsInfo
from pipdeptree._parser._format import format_requirement

if TYPE_CHECKING:
    from pathlib import Path


@pytest.mark.parametrize(
    ("direct_url", "expected"),
    [
        pytest.param(
            DirectUrl(url="https://github.com/user/repo.git", info=VcsInfo(vcs="git", commit_id="abc123")),
            "mypackage @ git+https://github.com/user/repo.git@abc123",
            id="vcs",
        ),
        pytest.param(
            DirectUrl(
                url="https://github.com/user/repo.git",
                info=VcsInfo(vcs="git", commit_id="abc123"),
                subdirectory="src/pkg",
            ),
            "mypackage @ git+https://github.com/user/repo.git@abc123#subdirectory=src/pkg",
            id="vcs-with-subdirectory",
        ),
        pytest.param(
            DirectUrl(url="https://example.com/package.tar.gz", info=ArchiveInfo(hash="sha256=abc123")),
            "mypackage @ https://example.com/package.tar.gz#sha256=abc123",
            id="archive-with-hash",
        ),
        pytest.param(
            DirectUrl(url="https://example.com/package.tar.gz", info=ArchiveInfo()),
            "mypackage @ https://example.com/package.tar.gz",
            id="archive-without-hash",
        ),
        pytest.param(
            DirectUrl(
                url="https://example.com/package.tar.gz",
                info=ArchiveInfo(hash="sha256=abc123"),
                subdirectory="src/pkg",
            ),
            "mypackage @ https://example.com/package.tar.gz#sha256=abc123&subdirectory=src/pkg",
            id="archive-with-hash-and-subdirectory",
        ),
        pytest.param(
            DirectUrl(url="file:///home/user/project", info=DirInfo()),
            "mypackage @ file:///home/user/project",
            id="dir",
        ),
        pytest.param(
            DirectUrl(url="file:///home/user/project", info=DirInfo(), subdirectory="src/pkg"),
            "mypackage @ file:///home/user/project#subdirectory=src/pkg",
            id="dir-with-subdirectory",
        ),
    ],
)
def test_format_requirement(direct_url: DirectUrl, expected: str) -> None:
    result = format_requirement(direct_url, "mypackage")
    assert result == expected


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
            json.dumps({"url": "https://example.com/package.tar.gz", "archive_info": {"hash": "sha256=abc123"}}),
            "mypackage @ https://example.com/package.tar.gz#sha256=abc123",
            id="direct-url-archive",
        ),
        pytest.param(
            json.dumps({"url": "file:///home/user/project", "dir_info": {"editable": False}}),
            "mypackage @ file:///home/user/project",
            id="dir-not-editable",
        ),
    ],
)
def test_distribution_to_specifier(read_text_value: str | None, expected: str) -> None:
    distribution = Mock(metadata={"Name": "mypackage"}, version="1.0.0")
    distribution.read_text.return_value = read_text_value
    result = distribution_to_specifier(distribution)
    assert result == expected


def test_distribution_to_specifier_egg_link_fallback(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    site_dir = tmp_path / "site-packages"
    site_dir.mkdir()
    egg_link = site_dir / "mypackage.egg-link"
    egg_link.write_text("/path/to/source\n")
    monkeypatch.setattr("pipdeptree._parser._editable.site.getsitepackages", lambda: [str(site_dir)])
    monkeypatch.setattr("pipdeptree._parser._editable.site.getusersitepackages", lambda: None)
    monkeypatch.setattr("pipdeptree._parser._format.get_vcs_requirement", lambda _loc, _name: None)
    distribution = Mock(metadata={"Name": "mypackage"}, version="1.0.0")
    distribution.read_text.return_value = None
    result = distribution_to_specifier(distribution)
    assert result == "-e /path/to/source"


def test_distribution_to_specifier_editable_with_vcs(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "pipdeptree._parser._format.get_vcs_requirement",
        lambda _loc, _name: "git+https://github.com/user/repo@abc123#egg=mypackage",
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
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    site_dir = tmp_path / "site-packages"
    site_dir.mkdir()
    egg_link = site_dir / "mypackage.egg-link"
    egg_link.write_text("/path/to/source\n")
    monkeypatch.setattr("pipdeptree._parser._editable.site.getsitepackages", lambda: [str(site_dir)])
    monkeypatch.setattr("pipdeptree._parser._editable.site.getusersitepackages", lambda: None)
    distribution = Mock(metadata={"Name": "mypackage"}, version="1.0.0")
    distribution.read_text.return_value = json.dumps({"url": "file:///path/to/non-editable", "dir_info": {}})
    result = distribution_to_specifier(distribution)
    assert result == "mypackage @ file:///path/to/non-editable"
