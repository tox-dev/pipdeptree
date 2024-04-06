from __future__ import annotations

import sys
from platform import python_implementation
from typing import TYPE_CHECKING

import pytest
import virtualenv

from pipdeptree.__main__ import main

if TYPE_CHECKING:
    from pathlib import Path


@pytest.mark.parametrize("args_joined", [True, False])
def test_custom_interpreter(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capfd: pytest.CaptureFixture[str],
    args_joined: bool,
) -> None:
    result = virtualenv.cli_run([str(tmp_path / "venv"), "--activators", ""])
    cmd = [sys.executable]
    monkeypatch.chdir(tmp_path)
    py = str(result.creator.exe.relative_to(tmp_path))
    cmd += [f"--python={result.creator.exe}"] if args_joined else ["--python", py]
    monkeypatch.setattr(sys, "argv", cmd)
    main()
    out, _ = capfd.readouterr()
    found = {i.split("==")[0] for i in out.splitlines()}
    implementation = python_implementation()
    if implementation == "CPython":
        expected = {"pip", "setuptools", "wheel"}
    elif implementation == "PyPy":
        expected = {"cffi", "greenlet", "pip", "readline", "setuptools", "wheel"}  # pragma: no cover
    else:
        raise ValueError(implementation)
    if sys.version_info >= (3, 12):
        expected -= {"setuptools", "wheel"}
    assert found == expected, out
