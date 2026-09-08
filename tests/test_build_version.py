from __future__ import annotations

import runpy
import subprocess  # ruff:ignore[suspicious-subprocess-import]  # Integration tests execute Git and the Cargo build script.
from pathlib import Path
from shutil import which
from typing import TYPE_CHECKING, Final
from unittest.mock import create_autospec

import pytest

if TYPE_CHECKING:
    from collections.abc import Callable

_ROOT: Final = Path(__file__).resolve().parents[1]


def test_build_version_override(
    build_version: Callable[[], str], repository: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _git(repository, "tag", "4.2.3")
    (repository / "PKG-INFO").write_text("Version: 4.1.0\n", encoding="utf-8")
    monkeypatch.setenv("PIPDEPTREE_VERSION", "5.0.0rc1")

    assert build_version() == "5.0.0rc1"


@pytest.mark.parametrize("release", [pytest.param("4.2.3", id="final"), pytest.param("4.3.0rc1", id="prerelease")])
def test_build_version_tag(build_version: Callable[[], str], repository: Path, release: str) -> None:
    _git(repository, "tag", release)
    (repository / "PKG-INFO").write_text("Version: 4.1.0\n", encoding="utf-8")

    assert build_version() == release


def test_build_version_after_tag(build_version: Callable[[], str], repository: Path) -> None:
    _git(repository, "tag", "4.2.3")
    _git(repository, "commit", "--allow-empty", "-m", "After release")

    assert build_version() == f"4.2.3.dev1+g{_git(repository, 'rev-parse', '--short', 'HEAD')}"


def test_build_version_gitfile(build_version: Callable[[], str], tmp_path: Path) -> None:
    _git(tmp_path, "init", "--separate-git-dir", str(tmp_path.parent / f"{tmp_path.name}.git"))
    _git(tmp_path, "commit", "--allow-empty", "-m", "Initial commit")
    _git(tmp_path, "tag", "4.2.3")

    assert build_version() == "4.2.3"


def test_build_version_without_release_tag(build_version: Callable[[], str], repository: Path) -> None:
    _git(repository, "tag", "unrelated")

    assert build_version() == "0.0.0"


def test_build_version_untagged_metadata(build_version: Callable[[], str], repository: Path) -> None:
    (repository / "PKG-INFO").write_text("Version: 4.2.3\n", encoding="utf-8")

    assert build_version() == "4.2.3"


@pytest.mark.parametrize(
    ("metadata", "expected"),
    [
        pytest.param("Metadata-Version: 2.4\nName: pipdeptree\nVersion: 4.2.3\n\nDescription", "4.2.3", id="sdist"),
        pytest.param("Version: 4.2.3.dev2+g1234567\n", "4.2.3.dev2+g1234567", id="development-sdist"),
        pytest.param("Name: pipdeptree\n", "0.0.0", id="missing-version"),
        pytest.param("Version: \n", "0.0.0", id="empty-version"),
        pytest.param("Name: pipdeptree\n\nVersion: 9.9.9\n", "0.0.0", id="description-is-not-metadata"),
    ],
)
def test_build_version_metadata(build_version: Callable[[], str], tmp_path: Path, metadata: str, expected: str) -> None:
    (tmp_path / "PKG-INFO").write_text(metadata, encoding="utf-8")

    assert build_version() == expected


def test_build_version_unknown(build_version: Callable[[], str]) -> None:
    assert build_version() == "0.0.0"


def test_build_version_without_git(
    build_version: Callable[[], str], repository: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _git(repository, "tag", "4.2.3")
    (repository / "PKG-INFO").write_text("Version: 4.1.0\n", encoding="utf-8")
    monkeypatch.setenv("PATH", "")

    assert build_version() == "4.1.0"


def test_build_version_parent_repository(build_version: Callable[[], str], tmp_path: Path) -> None:
    _git(tmp_path.parent, "init")
    _git(tmp_path.parent, "commit", "--allow-empty", "-m", "Parent repository")
    _git(tmp_path.parent, "tag", "--force", "9.9.9")
    (tmp_path / "PKG-INFO").write_text("Version: 4.2.3\n", encoding="utf-8")

    assert build_version() == "4.2.3"


@pytest.fixture(params=["meson", "cargo"])
def build_version(
    request: pytest.FixtureRequest,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    cargo_build_script: Path,
) -> Callable[[], str]:
    monkeypatch.delenv("PIPDEPTREE_VERSION", raising=False)
    if request.param == "meson":

        def meson_version() -> str:
            with monkeypatch.context() as context:
                context.setattr(
                    Path, "resolve", create_autospec(Path.resolve, return_value=tmp_path / "tools/version.py")
                )
                runpy.run_path(str(_ROOT / "tools/version.py"), run_name="tools.version")["main"]()
            return capsys.readouterr().out.strip()

        return meson_version

    def cargo_version() -> str:
        result: Final = subprocess.run(
            [str(cargo_build_script)], cwd=tmp_path, capture_output=True, text=True, check=True
        )
        return next(
            line.removeprefix("cargo:rustc-env=PIPDEPTREE_VERSION=")
            for line in result.stdout.splitlines()
            if line.startswith("cargo:rustc-env=PIPDEPTREE_VERSION=")
        )

    return cargo_version


@pytest.fixture(scope="session")
def cargo_build_script(tmp_path_factory: pytest.TempPathFactory) -> Path:
    rustc: Final = which("rustc")
    assert rustc is not None
    executable: Final = tmp_path_factory.mktemp("build-version") / "build-version.exe"
    subprocess.run([rustc, "--edition=2024", str(_ROOT / "build.rs"), "-o", str(executable)], check=True)
    return executable


@pytest.fixture
def repository(tmp_path: Path) -> Path:
    _git(tmp_path, "init")
    _git(tmp_path, "commit", "--allow-empty", "-m", "Initial commit")
    return tmp_path


def _git(root: Path, *args: str) -> str:
    git: Final = which("git")
    assert git is not None
    return subprocess.run(
        [git, "-c", "user.name=Test", "-c", "user.email=test@example.com", "-c", "commit.gpgsign=false", *args],
        cwd=root,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
