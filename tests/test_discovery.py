from __future__ import annotations

import site
import sys
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import Mock

import virtualenv

from pipdeptree.__main__ import main
from pipdeptree._discovery import get_installed_distributions

if TYPE_CHECKING:
    import pytest
    from pytest_mock import MockerFixture


def test_local_only(tmp_path: Path, mocker: MockerFixture, capfd: pytest.CaptureFixture[str]) -> None:
    venv_path = str(tmp_path / "venv")
    result = virtualenv.cli_run([venv_path, "--activators", ""])
    venv_site_packages = site.getsitepackages([venv_path])
    fake_dist = Path(venv_site_packages[0]) / "foo-1.2.5.dist-info"
    fake_dist.mkdir()
    fake_metadata = Path(fake_dist) / "METADATA"
    with fake_metadata.open("w") as f:
        f.write("Metadata-Version: 2.3\n" "Name: foo\n" "Version: 1.2.5\n")

    cmd = [str(result.creator.exe.parent / "python3"), "--local-only"]
    mocker.patch("pipdeptree._discovery.sys.prefix", venv_path)
    sys_path = sys.path.copy()
    mock_path = sys_path + venv_site_packages
    mocker.patch("pipdeptree._discovery.sys.path", mock_path)
    mocker.patch("pipdeptree._discovery.sys.argv", cmd)
    main()
    out, _ = capfd.readouterr()
    found = {i.split("==")[0] for i in out.splitlines()}
    expected = {"foo", "pip", "setuptools", "wheel"}
    if sys.version_info >= (3, 12):
        expected -= {"setuptools", "wheel"}  # pragma: no cover

    assert found == expected


def test_user_only(tmp_path: Path, mocker: MockerFixture, capfd: pytest.CaptureFixture[str]) -> None:
    fake_dist = Path(tmp_path) / "foo-1.2.5.dist-info"
    fake_dist.mkdir()
    fake_metadata = Path(fake_dist) / "METADATA"
    with Path(fake_metadata).open("w") as f:
        f.write("Metadata-Version: 2.3\n" "Name: foo\n" "Version: 1.2.5\n")

    cmd = [sys.executable, "--user-only"]
    mocker.patch("pipdeptree._discovery.site.getusersitepackages", Mock(return_value=str(tmp_path)))
    mocker.patch("pipdeptree._discovery.sys.argv", cmd)
    main()
    out, _ = capfd.readouterr()
    found = {i.split("==")[0] for i in out.splitlines()}
    expected = {"foo"}

    assert found == expected


def test_duplicate_metadata(mocker: MockerFixture, capfd: pytest.CaptureFixture[str]) -> None:
    mocker.patch(
        "pipdeptree._discovery.distributions",
        Mock(
            return_value=[
                Mock(metadata={"Name": "foo"}, version="1.2.5", locate_file=Mock(return_value="/path/1")),
                Mock(metadata={"Name": "foo"}, version="5.9.0", locate_file=Mock(return_value="/path/2")),
            ]
        ),
    )

    dists = get_installed_distributions()
    assert len(dists) == 1
    # we expect it to use the first distribution found
    assert dists[0].version == "1.2.5"

    _, err = capfd.readouterr()
    expected = (
        'Warning!!! Duplicate package metadata found:\n"/path/2"\n  foo                              5.9.0       '
        '     (using 1.2.5, "/path/1")\nNOTE: This warning isn\'t a failure warning.\n---------------------------------'
        "---------------------------------------\n"
    )
    assert err == expected
