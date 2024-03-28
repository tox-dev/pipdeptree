from __future__ import annotations

import subprocess  # noqa: S404
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import virtualenv

from pipdeptree.__main__ import main

if TYPE_CHECKING:
    import pytest


def test_local_only(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capfd: pytest.CaptureFixture[str],
) -> None:
    prefix = str(tmp_path / "venv")
    result = virtualenv.cli_run([str(tmp_path / "venv"), "--activators", ""])
    pip_path = str(result.creator.exe.parent / "pip")
    subprocess.run(
        [pip_path, "install", "wrapt", "--prefix", prefix],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    cmd = [str(result.creator.exe.parent / "python3")]
    monkeypatch.chdir(tmp_path)
    cmd += ["--local-only"]
    monkeypatch.setattr(sys, "prefix", [str(tmp_path / "venv")])
    monkeypatch.setattr(sys, "argv", cmd)
    main()
    out, _ = capfd.readouterr()
    found = {i.split("==")[0] for i in out.splitlines()}
    expected = {"wrapt", "pip", "setuptools", "wheel"}

    if sys.version_info >= (3, 12):
        expected -= {"setuptools", "wheel"}

    assert found == expected


def test_user_only() -> None:
    subprocess.check_call([Path(sys.executable).parent / "pipdeptree", "--user-only"])
