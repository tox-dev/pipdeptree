from __future__ import annotations

import json
import os
from typing import TYPE_CHECKING
from unittest.mock import Mock

import pytest

from pipdeptree._parser._editable import get_editable_location

if TYPE_CHECKING:
    from pathlib import Path


@pytest.mark.parametrize(
    ("url", "expected_location"),
    [
        pytest.param("file:///home/user/project", "/home/user/project", id="unix-path"),
        pytest.param("file:///home/user/my%20project", "/home/user/my project", id="path-with-spaces"),
        pytest.param("file://localhost/home/user/project", "/home/user/project", id="localhost"),
    ],
)
def test_get_editable_location_url_conversion(url: str, expected_location: str) -> None:
    dist = Mock(metadata={"Name": "mypackage"})
    dist.read_text.return_value = json.dumps({"url": url, "dir_info": {"editable": True}})
    result = get_editable_location(dist)
    assert result == expected_location


@pytest.mark.skipif(os.name != "nt", reason="UNC paths are Windows-only")
def test_get_editable_location_unc_path() -> None:  # pragma: win32 cover
    dist = Mock(metadata={"Name": "mypackage"})  # pragma: win32 cover
    dist.read_text.return_value = json.dumps({  # pragma: win32 cover
        "url": "file://server/share/path",  # pragma: win32 cover
        "dir_info": {"editable": True},  # pragma: win32 cover
    })  # pragma: win32 cover
    result = get_editable_location(dist)  # pragma: win32 cover
    assert result == r"\\server\share\path"  # pragma: win32 cover


@pytest.mark.skipif(os.name != "nt", reason="Windows drive letter correction is Windows-only")
def test_get_editable_location_windows_drive() -> None:  # pragma: win32 cover
    dist = Mock(metadata={"Name": "mypackage"})  # pragma: win32 cover
    dist.read_text.return_value = json.dumps({  # pragma: win32 cover
        "url": "file:///C:/Users/test/project",  # pragma: win32 cover
        "dir_info": {"editable": True},  # pragma: win32 cover
    })  # pragma: win32 cover
    result = get_editable_location(dist)  # pragma: win32 cover
    assert result == r"C:\Users\test\project"  # pragma: win32 cover


def test_get_editable_location_from_egg_link_site_packages(mocker: pytest.MockerFixture, tmp_path: Path) -> None:
    site_dir = tmp_path / "site-packages"
    site_dir.mkdir()
    egg_link = site_dir / "mypackage.egg-link"
    egg_link.write_text("/path/to/source\n")
    dist = Mock(metadata={"Name": "mypackage"})
    dist.read_text.return_value = None
    mocker.patch("pipdeptree._parser._editable.site.getsitepackages", return_value=[str(site_dir)])
    mocker.patch("pipdeptree._parser._editable.site.getusersitepackages", return_value=None)
    result = get_editable_location(dist)
    assert result == "/path/to/source"


def test_get_editable_location_from_egg_link_user_site(mocker: pytest.MockerFixture, tmp_path: Path) -> None:
    user_site = tmp_path / "user-site"
    user_site.mkdir()
    egg_link = user_site / "mypackage.egg-link"
    egg_link.write_text("/path/to/source\n")
    dist = Mock(metadata={"Name": "mypackage"})
    dist.read_text.return_value = None
    mocker.patch("pipdeptree._parser._editable.site.getsitepackages", return_value=[])
    mocker.patch("pipdeptree._parser._editable.site.getusersitepackages", return_value=str(user_site))
    result = get_editable_location(dist)
    assert result == "/path/to/source"


def test_get_editable_location_egg_link_multiline(mocker: pytest.MockerFixture, tmp_path: Path) -> None:
    site_dir = tmp_path / "site-packages"
    site_dir.mkdir()
    egg_link = site_dir / "pkg.egg-link"
    egg_link.write_text("/path/to/source\nextra line\n")
    dist = Mock(metadata={"Name": "pkg"})
    dist.read_text.return_value = None
    mocker.patch("pipdeptree._parser._editable.site.getsitepackages", return_value=[str(site_dir)])
    mocker.patch("pipdeptree._parser._editable.site.getusersitepackages", return_value=None)
    result = get_editable_location(dist)
    assert result == "/path/to/source"


def test_get_editable_location_not_editable() -> None:
    dist = Mock(metadata={"Name": "mypackage"})
    dist.read_text.return_value = None
    result = get_editable_location(dist)
    assert result is None


def test_get_editable_location_dir_info_not_editable() -> None:
    dist = Mock(metadata={"Name": "mypackage"})
    dist.read_text.return_value = json.dumps({
        "url": "file:///home/user/project",
        "dir_info": {"editable": False},
    })
    result = get_editable_location(dist)
    assert result is None


def test_get_editable_location_egg_link_not_found(mocker: pytest.MockerFixture, tmp_path: Path) -> None:
    site_dir = tmp_path / "site-packages"
    user_site = tmp_path / "user-site"
    dist = Mock(metadata={"Name": "nonexistent"})
    dist.read_text.return_value = None
    mocker.patch("pipdeptree._parser._editable.site.getsitepackages", return_value=[str(site_dir)])
    mocker.patch("pipdeptree._parser._editable.site.getusersitepackages", return_value=str(user_site))
    result = get_editable_location(dist)
    assert result is None
