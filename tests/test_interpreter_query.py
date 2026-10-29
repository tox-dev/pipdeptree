from __future__ import annotations

import sys
import venv
from pathlib import Path
from typing import TYPE_CHECKING, Final

import pytest

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence


@pytest.mark.parametrize("module", [pytest.param("json", id="json"), pytest.param("platform", id="platform")])
def test_query_ignores_module_in_working_directory(
    entry_point: Callable[[Sequence[str] | None], int | None],
    interpreter: Path,
    working_directory: Path,
    module: str,
) -> None:
    marker: Final = working_directory / "imported"
    (working_directory / f"{module}.py").write_text(f"open({str(marker)!r}, 'w').close()\n")

    code: Final = entry_point(["--python", str(interpreter), "--freeze"])

    assert (code, marker.exists()) == (0, False)


def test_query_ignores_distribution_in_working_directory(
    entry_point: Callable[[Sequence[str] | None], int | None],
    interpreter: Path,
    working_directory: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    dist_info: Final = working_directory / "planted-1.dist-info"
    dist_info.mkdir()
    (dist_info / "METADATA").write_text("Name: planted\nVersion: 1\n")

    code: Final = entry_point(["--python", str(interpreter), "--freeze"])

    assert (code, "planted" in capsys.readouterr().out) == (0, False)


@pytest.mark.parametrize(
    ("variable", "scripts"),
    [
        pytest.param("VIRTUAL_ENV", "Scripts" if sys.platform == "win32" else "bin", id="venv"),
        pytest.param("CONDA_PREFIX", "." if sys.platform == "win32" else "bin", id="conda"),
    ],
)
def test_detection_ignores_empty_environment_variable(
    entry_point: Callable[[Sequence[str] | None], int | None],
    working_directory: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    variable: str,
    scripts: str,
) -> None:
    (working_directory / scripts).mkdir(exist_ok=True)
    (working_directory / scripts / ("python.exe" if sys.platform == "win32" else "python")).write_text("")
    for name in ("VIRTUAL_ENV", "CONDA_PREFIX"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv(variable, "")

    code: Final = entry_point(["--packages", "pipdeptree", "--depth", "0"])

    assert (code, capsys.readouterr().out.startswith("pipdeptree==")) == (0, True)


@pytest.fixture
def interpreter(tmp_path: Path) -> Path:
    venv.create(tmp_path / "venv", with_pip=False)
    return tmp_path / "venv" / ("Scripts" if sys.platform == "win32" else "bin") / Path(sys.executable).name


@pytest.fixture
def working_directory(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    directory: Final = tmp_path / "work"
    directory.mkdir()
    monkeypatch.chdir(directory)
    return directory
