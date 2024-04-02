from __future__ import annotations

import site
import sys
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import Mock

import virtualenv

from pipdeptree.__main__ import main

if TYPE_CHECKING:
    import pytest


def test_local_only(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capfd: pytest.CaptureFixture[str]) -> None:
    venv_path = str(tmp_path / "venv")
    result = virtualenv.cli_run([venv_path, "--activators", ""])
    venv_site_packages = site.getsitepackages([venv_path])
    fake_dist = Path(venv_site_packages[0]) / "foo-1.2.5.dist-info"
    fake_dist.mkdir()
    fake_metadata = Path(fake_dist) / "METADATA"
    with fake_metadata.open("w") as f:
        f.write("Metadata-Version: 2.3\n" "Name: foo\n" "Version: 1.2.5\n")

    cmd = [str(result.creator.exe.parent / "python3"), "--local-only"]
    monkeypatch.setattr(sys, "prefix", venv_path)
    monkeypatch.setattr(sys, "argv", cmd)
    main()
    out, _ = capfd.readouterr()
    found = {i.split("==")[0] for i in out.splitlines()}
    expected = {"foo", "pip", "setuptools", "wheel"}
    if sys.version_info >= (3, 12):
        expected -= {"setuptools", "wheel"}  # pragma: no cover

    assert found == expected


def test_user_only(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capfd: pytest.CaptureFixture[str]) -> None:
    fake_dist = Path(tmp_path) / "foo-1.2.5.dist-info"
    fake_dist.mkdir()
    fake_metadata = Path(fake_dist) / "METADATA"
    with Path(fake_metadata).open("w") as f:
        f.write("Metadata-Version: 2.3\n" "Name: foo\n" "Version: 1.2.5\n")

    monkeypatch.setattr(site, "getusersitepackages", Mock(return_value=str(tmp_path)))
    cmd = [sys.executable, "--user-only"]
    monkeypatch.setattr(sys, "argv", cmd)
    main()
    out, _ = capfd.readouterr()
    found = {i.split("==")[0] for i in out.splitlines()}
    expected = {"foo"}

    assert found == expected
