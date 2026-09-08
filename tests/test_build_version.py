from __future__ import annotations

import runpy
import subprocess  # ruff:ignore[suspicious-subprocess-import]  # Integration tests need real Git and Cargo processes.
from pathlib import Path
from shutil import which
from typing import TYPE_CHECKING, Final
from unittest.mock import create_autospec

import pytest

if TYPE_CHECKING:
    from collections.abc import Callable


@pytest.mark.usefixtures("repository", "package_metadata")
@pytest.mark.parametrize(
    ("release", "override", "expected"),
    [
        pytest.param("4.2.3", None, "4.2.3", id="release"),
        pytest.param("4.3.0rc1", None, "4.3.0rc1", id="prerelease"),
        pytest.param("4.2.3", "5.0.0rc1", "5.0.0rc1", id="override"),
    ],
)
def test_build_version_tag(
    build_version: Callable[[], str],
    git: Callable[..., str],
    monkeypatch: pytest.MonkeyPatch,
    release: str,
    override: str | None,
    expected: str,
) -> None:
    git("tag", release)
    if override is not None:
        monkeypatch.setenv("PIPDEPTREE_VERSION", override)

    assert build_version() == expected


@pytest.mark.usefixtures("repository")
def test_build_version_after_tag(build_version: Callable[[], str], git: Callable[..., str]) -> None:
    git("tag", "4.2.3")
    git("commit", "--allow-empty", "-m", "After release")

    assert build_version() == f"4.2.3.dev1+g{git('rev-parse', '--short', 'HEAD')}"


@pytest.mark.usefixtures("repository")
def test_build_version_without_release_tag(build_version: Callable[[], str], git: Callable[..., str]) -> None:
    git("tag", "unrelated")

    assert build_version() == "0.0.0"


@pytest.mark.parametrize(
    ("metadata", "expected"),
    [
        pytest.param("Metadata-Version: 2.4\nName: pipdeptree\nVersion: 4.2.3\n\nDescription", "4.2.3", id="sdist"),
        pytest.param("Version: 4.2.3.dev2+g1234567\n", "4.2.3.dev2+g1234567", id="development-sdist"),
        pytest.param("Name: pipdeptree\n", "0.0.0", id="missing-version"),
        pytest.param("Version: \n", "0.0.0", id="empty-version"),
        pytest.param("Name: pipdeptree\n\nVersion: 9.9.9\n", "0.0.0", id="description-is-not-metadata"),
        pytest.param(None, "0.0.0", id="missing-metadata"),
    ],
)
def test_build_version_metadata(
    build_version: Callable[[], str], tmp_path: Path, metadata: str | None, expected: str
) -> None:
    if metadata is not None:
        (tmp_path / "PKG-INFO").write_text(metadata, encoding="utf-8")

    assert build_version() == expected


@pytest.mark.usefixtures("repository", "package_metadata")
@pytest.mark.parametrize("git_available", [pytest.param(True, id="untagged"), pytest.param(False, id="missing-git")])
def test_build_version_metadata_fallback(
    build_version: Callable[[], str],
    git: Callable[..., str],
    monkeypatch: pytest.MonkeyPatch,
    *,
    git_available: bool,
) -> None:
    if not git_available:
        git("tag", "4.2.3")
        monkeypatch.setenv("PATH", "")

    assert build_version() == "4.1.0"


@pytest.mark.usefixtures("parent_repository", "package_metadata")
def test_build_version_parent_repository(build_version: Callable[[], str]) -> None:
    assert build_version() == "4.1.0"


@pytest.fixture(params=[pytest.param("meson", id="meson"), pytest.param("cargo", id="cargo")])
def build_version(
    request: pytest.FixtureRequest,
    meson_version: Callable[[], str],
    cargo_version: Callable[[], str],
    monkeypatch: pytest.MonkeyPatch,
) -> Callable[[], str]:
    monkeypatch.delenv("PIPDEPTREE_VERSION", raising=False)
    return {"meson": meson_version, "cargo": cargo_version}[request.param]


@pytest.fixture
def meson_version(
    project_root: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> Callable[[], str]:
    def resolve() -> str:
        with monkeypatch.context() as context:
            context.setattr(Path, "resolve", create_autospec(Path.resolve, return_value=tmp_path / "tools/version.py"))
            runpy.run_path(str(project_root / "tools/version.py"), run_name="tools.version")["main"]()
        return capsys.readouterr().out.strip()

    return resolve


@pytest.fixture(scope="session")
def project_root() -> Path:
    return Path(__file__).resolve().parents[1]


@pytest.fixture
def cargo_version(cargo_build_script: Path, tmp_path: Path) -> Callable[[], str]:
    def resolve() -> str:
        result: Final = subprocess.run(
            [str(cargo_build_script)], cwd=tmp_path, capture_output=True, text=True, check=True
        )
        return next(
            line.split("=", 2)[2]
            for line in result.stdout.splitlines()
            if line.startswith("cargo:rustc-env=PIPDEPTREE_VERSION=")
        )

    return resolve


@pytest.fixture(scope="session")
def cargo_build_script(project_root: Path, tmp_path_factory: pytest.TempPathFactory) -> Path:
    rustc: Final = which("rustc")
    assert rustc is not None
    executable: Final = tmp_path_factory.mktemp("build-version") / "build-version.exe"
    subprocess.run([rustc, "--edition=2024", str(project_root / "build.rs"), "-o", str(executable)], check=True)
    return executable


@pytest.fixture(params=[pytest.param(False, id="git-directory"), pytest.param(True, id="git-file")])
def repository(request: pytest.FixtureRequest, git: Callable[..., str], tmp_path: Path) -> None:
    if request.param:
        git("init", "--separate-git-dir", str(tmp_path.parent / f"{tmp_path.name}.git"))
    else:
        git("init")
    git("commit", "--allow-empty", "-m", "Initial commit")


@pytest.fixture
def git(tmp_path: Path) -> Callable[..., str]:
    executable: Final = which("git")
    assert executable is not None

    def run(*args: str) -> str:
        return subprocess.run(
            [
                executable,
                "-c",
                "user.name=Test",
                "-c",
                "user.email=test@example.com",
                "-c",
                "commit.gpgsign=false",
                *args,
            ],
            cwd=tmp_path,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()

    return run


@pytest.fixture
def package_metadata(tmp_path: Path) -> None:
    (tmp_path / "PKG-INFO").write_text("Version: 4.1.0\n", encoding="utf-8")


@pytest.fixture
def parent_repository(git: Callable[..., str], tmp_path: Path) -> None:
    git("-C", str(tmp_path.parent), "init")
    git("-C", str(tmp_path.parent), "commit", "--allow-empty", "-m", "Parent repository")
    git("-C", str(tmp_path.parent), "tag", "--force", "9.9.9")
