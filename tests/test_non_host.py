from __future__ import annotations

import sys
from platform import python_implementation
from typing import TYPE_CHECKING
from unittest.mock import Mock

import pytest
import virtualenv

from pipdeptree.__main__ import main

if TYPE_CHECKING:
    from pathlib import Path

    from pytest_mock import MockerFixture


@pytest.fixture(scope="session")
def expected_venv_pkgs() -> frozenset[str]:
    implementation = python_implementation()
    if implementation == "CPython":  # pragma: cpython cover
        expected = {"pip", "setuptools", "wheel"}
    elif implementation == "PyPy":  # pragma: pypy cover
        expected = {"cffi", "greenlet", "pip", "readline", "hpy", "setuptools", "wheel"}
    else:  # pragma: no cover
        raise ValueError(implementation)
    if sys.version_info >= (3, 12):  # pragma: >=3.12 cover
        expected -= {"setuptools", "wheel"}

    return frozenset(expected)


@pytest.mark.parametrize("args_joined", [True, False])
def test_custom_interpreter(
    tmp_path: Path,
    mocker: MockerFixture,
    monkeypatch: pytest.MonkeyPatch,
    capfd: pytest.CaptureFixture[str],
    args_joined: bool,
    expected_venv_pkgs: frozenset[str],
) -> None:
    # Delete $PYTHONPATH so that it cannot be passed to the custom interpreter process (since we don't know what
    # distribution metadata to expect when it's used).
    monkeypatch.delenv("PYTHONPATH", False)

    monkeypatch.chdir(tmp_path)
    result = virtualenv.cli_run([str(tmp_path / "venv"), "--activators", ""])
    py = str(result.creator.exe.relative_to(tmp_path))
    cmd = ["", f"--python={result.creator.exe}"] if args_joined else ["", "--python", py]
    cmd += ["--all", "--depth", "0"]
    mocker.patch("pipdeptree._discovery.sys.argv", cmd)
    main()
    out, _ = capfd.readouterr()
    found = {i.split("==")[0] for i in out.splitlines()}

    assert expected_venv_pkgs == found, out


def test_custom_interpreter_with_local_only(
    tmp_path: Path,
    mocker: MockerFixture,
    capfd: pytest.CaptureFixture[str],
) -> None:
    venv_path = str(tmp_path / "venv")
    result = virtualenv.cli_run([venv_path, "--system-site-packages", "--activators", ""])

    cmd = ["", f"--python={result.creator.exe}", "--local-only"]
    mocker.patch("pipdeptree._discovery.sys.prefix", venv_path)
    mocker.patch("pipdeptree._discovery.sys.argv", cmd)
    main()
    out, _ = capfd.readouterr()
    found = {i.split("==")[0] for i in out.splitlines()}
    expected = {"pip", "setuptools", "wheel"}
    if sys.version_info >= (3, 12):  # pragma: >=3.12 cover
        expected -= {"setuptools", "wheel"}
    assert expected == found, out


def test_custom_interpreter_with_user_only(
    tmp_path: Path, mocker: MockerFixture, capfd: pytest.CaptureFixture[str]
) -> None:
    # ensures there is no output when --user-only and --python are passed

    venv_path = str(tmp_path / "venv")
    result = virtualenv.cli_run([venv_path, "--activators", ""])

    cmd = ["", f"--python={result.creator.exe}", "--user-only"]
    mocker.patch("pipdeptree.__main__.sys.argv", cmd)
    main()
    out, err = capfd.readouterr()
    assert not err

    # Here we expect 1 element because print() adds a newline.
    found = out.splitlines()
    assert len(found) == 1
    assert not found[0]


def test_custom_interpreter_with_user_only_and_system_site_pkgs_enabled(
    tmp_path: Path,
    fake_dist: Path,
    mocker: MockerFixture,
    monkeypatch: pytest.MonkeyPatch,
    capfd: pytest.CaptureFixture[str],
) -> None:
    # ensures that we provide user site metadata when --user-only and --python are passed and the custom interpreter has
    # system site packages enabled

    # Make a fake user site directory since we don't know what to expect from the real one.
    fake_user_site = str(fake_dist.parent)
    mocker.patch("pipdeptree._discovery.site.getusersitepackages", Mock(return_value=fake_user_site))

    # Create a temporary virtual environment.
    venv_path = str(tmp_path / "venv")
    result = virtualenv.cli_run([venv_path, "--activators", ""])

    # Use $PYTHONPATH to add the fake user site into the custom interpreter's environment so that it will include it in
    # its sys.path.
    monkeypatch.setenv("PYTHONPATH", str(fake_user_site))

    cmd = ["", f"--python={result.creator.exe}", "--user-only"]
    mocker.patch("pipdeptree.__main__.sys.argv", cmd)
    main()

    out, err = capfd.readouterr()
    assert not err
    found = {i.split("==")[0] for i in out.splitlines()}
    expected = {"bar"}

    assert expected == found


def test_custom_interpreter_ensure_pythonpath_envar_is_honored(
    tmp_path: Path,
    mocker: MockerFixture,
    monkeypatch: pytest.MonkeyPatch,
    capfd: pytest.CaptureFixture[str],
    expected_venv_pkgs: frozenset[str],
) -> None:
    # ensures that we honor $PYTHONPATH when passing it to the custom interpreter process
    venv_path = str(tmp_path / "venv")
    result = virtualenv.cli_run([venv_path, "--activators", ""])

    another_path = tmp_path / "another-path"
    fake_dist = another_path / "foo-1.2.3.dist-info"
    fake_dist.mkdir(parents=True)
    fake_metadata = fake_dist / "METADATA"
    with fake_metadata.open("w") as f:
        f.write("Metadata-Version: 2.3\n" "Name: foo\n" "Version: 1.2.3\n")
    cmd = ["", f"--python={result.creator.exe}", "--all", "--depth", "0"]
    mocker.patch("pipdeptree._discovery.sys.argv", cmd)
    monkeypatch.setenv("PYTHONPATH", str(another_path))
    main()
    out, _ = capfd.readouterr()
    found = {i.split("==")[0] for i in out.splitlines()}
    assert {*expected_venv_pkgs, "foo"} == found, out
