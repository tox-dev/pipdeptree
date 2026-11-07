from __future__ import annotations

import os
import runpy
import sys
import sysconfig
from pathlib import Path
from typing import TYPE_CHECKING, Final

import pytest

if TYPE_CHECKING:
    from pytest_mock import MockerFixture


@pytest.mark.parametrize(
    ("environment", "implementation", "gil_disabled", "expected"),
    [
        pytest.param({"PIPDEPTREE_ABI3": "1"}, "cpython", 0, "true", id="abi3-cpython"),
        pytest.param({}, "cpython", 0, "false", id="unset"),
        pytest.param({"PIPDEPTREE_ABI3": "0"}, "cpython", 0, "false", id="disabled"),
        pytest.param({"PIPDEPTREE_ABI3": "1"}, "pypy", 0, "false", id="pypy"),
        pytest.param({"PIPDEPTREE_ABI3": "1"}, "cpython", 1, "false", id="free-threaded"),
    ],
)
def test_build_limited_api(
    monkeypatch: pytest.MonkeyPatch,
    mocker: MockerFixture,
    capsys: pytest.CaptureFixture[str],
    environment: dict[str, str],
    implementation: str,
    gil_disabled: int,
    expected: str,
) -> None:
    monkeypatch.setattr(os, "environ", environment)
    monkeypatch.setattr(sys.implementation, "name", implementation)
    monkeypatch.setattr(
        sysconfig, "get_config_var", mocker.create_autospec(sysconfig.get_config_var, return_value=gil_disabled)
    )
    script: Final = Path(__file__).resolve().parents[1] / "tools/limited_api.py"

    runpy.run_path(str(script), run_name="tools.limited_api")["main"]()

    assert capsys.readouterr().out == f"{expected}\n"
