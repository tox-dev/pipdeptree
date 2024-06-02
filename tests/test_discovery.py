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


def test_user_only(fake_dist: Path, mocker: MockerFixture, capfd: pytest.CaptureFixture[str]) -> None:
    # Make a fake user site.
    fake_user_site = str(fake_dist.parent)
    mocker.patch("pipdeptree._discovery.site.getusersitepackages", Mock(return_value=fake_user_site))

    # Add fake user site directory into a fake sys.path (normal environments will have the user site in sys.path).
    fake_sys_path = [*sys.path, fake_user_site]
    mocker.patch("pipdeptree._discovery.sys.path", fake_sys_path)

    cmd = ["", "--user-only"]
    mocker.patch("pipdeptree.__main__.sys.argv", cmd)
    main()

    out, err = capfd.readouterr()
    assert not err
    found = {i.split("==")[0] for i in out.splitlines()}
    expected = {"bar"}

    assert found == expected


def test_user_only_when_in_virtual_env(
    tmp_path: Path, mocker: MockerFixture, capfd: pytest.CaptureFixture[str]
) -> None:
    # ensures that we follow `pip list` by not outputting anything when --user-only is set and pipdeptree is running in
    # a virtual environment

    # Create a virtual environment and mock sys.path to point to the venv's site packages.
    venv_path = str(tmp_path / "venv")
    virtualenv.cli_run([venv_path, "--activators", ""])
    venv_site_packages = site.getsitepackages([venv_path])
    mocker.patch("pipdeptree._discovery.sys.path", venv_site_packages)
    mocker.patch("pipdeptree._discovery.sys.prefix", venv_path)

    cmd = ["", "--user-only"]
    mocker.patch("pipdeptree.__main__.sys.argv", cmd)
    main()

    out, err = capfd.readouterr()
    assert not err

    # Here we expect 1 element because print() adds a newline.
    found = out.splitlines()
    assert len(found) == 1
    assert not found[0]


def test_user_only_when_in_virtual_env_and_system_site_pkgs_enabled(
    tmp_path: Path, fake_dist: Path, mocker: MockerFixture, capfd: pytest.CaptureFixture[str]
) -> None:
    # ensures that we provide user site metadata when --user-only is set and we're in a virtual env with system site
    # packages enabled

    # Make a fake user site directory since we don't know what to expect from the real one.
    fake_user_site = str(fake_dist.parent)
    mocker.patch("pipdeptree._discovery.site.getusersitepackages", Mock(return_value=fake_user_site))

    # Create a temporary virtual environment. Add the fake user site to path (since user site packages should normally
    # be there).
    venv_path = str(tmp_path / "venv")
    virtualenv.cli_run([venv_path, "--system-site-packages", "--activators", ""])
    venv_site_packages = site.getsitepackages([venv_path])
    mock_path = sys.path + venv_site_packages + [fake_user_site]
    mocker.patch("pipdeptree._discovery.sys.path", mock_path)
    mocker.patch("pipdeptree._discovery.sys.prefix", venv_path)

    cmd = ["", "--user-only"]
    mocker.patch("pipdeptree.__main__.sys.argv", cmd)
    main()

    out, err = capfd.readouterr()
    assert not err
    found = {i.split("==")[0] for i in out.splitlines()}
    expected = {"bar"}

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


def test_invalid_metadata(
    mocker: MockerFixture, capfd: pytest.CaptureFixture[str], fake_dist_with_invalid_metadata: Path
) -> None:
    fake_site_dir = str(fake_dist_with_invalid_metadata.parent)
    mocked_sys_path = [fake_site_dir]
    mocker.patch("pipdeptree._discovery.sys.path", mocked_sys_path)

    dists = get_installed_distributions()

    assert len(dists) == 0
    out, err = capfd.readouterr()
    assert not out
    assert err == (
        "Warning!!! Missing or invalid metadata found in the following site dirs:\n"
        f"{fake_site_dir}\n"
        "------------------------------------------------------------------------\n"
    )
