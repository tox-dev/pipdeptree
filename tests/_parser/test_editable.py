from __future__ import annotations

import json
import os
from typing import TYPE_CHECKING
from unittest.mock import Mock

import pytest

from pipdeptree._parser._editable import (
    find_egg_link,
    get_editable_location,
    read_egg_link_location,
    url_to_path,
)

if TYPE_CHECKING:
    from pathlib import Path


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        pytest.param("file:///home/user/project", "/home/user/project", id="unix-path"),
        pytest.param("file:///home/user/my%20project", "/home/user/my project", id="path-with-spaces"),
        pytest.param("file://localhost/home/user/project", "/home/user/project", id="localhost"),
    ],
)
def test_url_to_path(url: str, expected: str) -> None:
    result = url_to_path(url)
    assert result == expected


@pytest.mark.skipif(os.name != "nt", reason="UNC paths are Windows-only")
def test_url_to_path_unc() -> None:  # pragma: win32 cover
    result = url_to_path("file://server/share/path")  # pragma: win32 cover
    assert result == r"\\server\share\path"  # pragma: win32 cover


@pytest.mark.skipif(os.name != "nt", reason="Windows drive letter correction is Windows-only")
def test_url_to_path_windows_drive() -> None:  # pragma: win32 cover
    result = url_to_path("file:///C:/Users/test/project")  # pragma: win32 cover
    assert result == r"C:\Users\test\project"  # pragma: win32 cover


@pytest.mark.skipif(os.name == "nt", reason="Non-local URLs rejected on non-Windows")
def test_url_to_path_non_local_rejected() -> None:
    with pytest.raises(ValueError, match="non-local file URIs are not supported"):
        url_to_path("file://remote-host/path")


def test_url_to_path_invalid_scheme() -> None:
    with pytest.raises(ValueError, match="You can only turn file: urls into filenames"):
        url_to_path("https://example.com/path")


def test_find_egg_link_not_found(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    site_dir = tmp_path / "site-packages"
    user_site = tmp_path / "user-site"
    monkeypatch.setattr("pipdeptree._parser._editable.site.getsitepackages", lambda: [str(site_dir)])
    monkeypatch.setattr("pipdeptree._parser._editable.site.getusersitepackages", lambda: str(user_site))
    result = find_egg_link("nonexistent")
    assert result is None


def test_find_egg_link_found_in_site_packages(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    site_dir = tmp_path / "site-packages"
    site_dir.mkdir()
    egg_link = site_dir / "mypackage.egg-link"
    egg_link.write_text("/path/to/source\n")

    monkeypatch.setattr("pipdeptree._parser._editable.site.getsitepackages", lambda: [str(site_dir)])
    monkeypatch.setattr("pipdeptree._parser._editable.site.getusersitepackages", lambda: None)

    result = find_egg_link("mypackage")
    assert result == egg_link


def test_find_egg_link_found_in_user_site(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    user_site = tmp_path / "user-site"
    user_site.mkdir()
    egg_link = user_site / "mypackage.egg-link"
    egg_link.write_text("/path/to/source\n")

    monkeypatch.setattr("pipdeptree._parser._editable.site.getsitepackages", list)
    monkeypatch.setattr("pipdeptree._parser._editable.site.getusersitepackages", lambda: str(user_site))

    result = find_egg_link("mypackage")
    assert result == egg_link


def test_find_egg_link_no_getsitepackages(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    user_site = tmp_path / "user-site"
    user_site.mkdir()
    egg_link = user_site / "pkg.egg-link"
    egg_link.write_text("/path/to/source\n")

    monkeypatch.delattr("pipdeptree._parser._editable.site.getsitepackages", raising=False)
    monkeypatch.setattr("pipdeptree._parser._editable.site.getusersitepackages", lambda: str(user_site))

    result = find_egg_link("pkg")
    assert result == egg_link


def test_read_egg_link_location(tmp_path: Path) -> None:
    egg_link = tmp_path / "test.egg-link"
    egg_link.write_text("/path/to/source\nextra line\n")
    result = read_egg_link_location(egg_link)
    assert result == "/path/to/source"


def test_get_editable_location_from_direct_url() -> None:
    dist = Mock(metadata={"Name": "mypackage"})
    dist.read_text.return_value = json.dumps({
        "url": "file:///home/user/project",
        "dir_info": {"editable": True},
    })
    result = get_editable_location(dist)
    assert result == "/home/user/project"


def test_get_editable_location_from_egg_link(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    site_dir = tmp_path / "site-packages"
    site_dir.mkdir()
    egg_link = site_dir / "mypackage.egg-link"
    egg_link.write_text("/path/to/source\n")

    dist = Mock(metadata={"Name": "mypackage"})
    dist.read_text.return_value = None

    monkeypatch.setattr("pipdeptree._parser._editable.site.getsitepackages", lambda: [str(site_dir)])
    monkeypatch.setattr("pipdeptree._parser._editable.site.getusersitepackages", lambda: None)

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
