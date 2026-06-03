from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from pipdeptree.__main__ import main
from pipdeptree._cli import get_options
from pipdeptree._from_lock import FromLockError, load_lock
from pipdeptree._models import PackageDAG

if TYPE_CHECKING:
    from pathlib import Path

    from pytest_mock import MockerFixture

_CHAIN = """\
lock-version = "1.0"
created-by = "nab"
[[packages]]
name = "build"
version = "1.5.0"
[[packages.dependencies]]
name = "packaging"
[[packages.dependencies]]
name = "pyproject-hooks"
[[packages]]
name = "packaging"
version = "26.2"
[[packages]]
name = "pyproject-hooks"
version = "1.2.0"
"""


def _write(tmp_path: Path, body: str) -> Path:
    lock = tmp_path / "pylock.toml"
    lock.write_text(body, encoding="utf-8")
    return lock


@pytest.mark.parametrize(
    ("body", "expected_children", "expected_versions"),
    [
        pytest.param(
            _CHAIN,
            {"build": ["packaging", "pyproject-hooks"], "packaging": [], "pyproject-hooks": []},
            {"build": "1.5.0", "packaging": "26.2", "pyproject-hooks": "1.2.0"},
            id="chain-with-edges",
        ),
        pytest.param(
            'lock-version = "1.0"\n'
            "[[packages]]\n"
            'name = "packaging"\n'
            'version = "26.2"\n'
            "[[packages]]\n"
            'name = "wheel"\n'
            'version = "0.45.1"\n',
            {"packaging": [], "wheel": []},
            {"packaging": "26.2", "wheel": "0.45.1"},
            id="flat-no-edges",
        ),
    ],
)
def test_load_lock_builds_tree(
    tmp_path: Path,
    body: str,
    expected_children: dict[str, list[str]],
    expected_versions: dict[str, str],
) -> None:
    dag = PackageDAG.from_pkgs(load_lock(_write(tmp_path, body)))

    by_key = {str(pkg.key): pkg for pkg in dag}
    assert set(by_key) == set(expected_versions)
    for key, version in expected_versions.items():
        assert by_key[key].version == version
    for key, children in expected_children.items():
        assert sorted(child.key for child in dag.get_children(key)) == sorted(children)


def test_load_lock_pins_child_versions(tmp_path: Path) -> None:
    dag = PackageDAG.from_pkgs(load_lock(_write(tmp_path, _CHAIN)))

    by_child = {str(child.key): child for child in dag.get_children("build")}
    assert by_child["packaging"].version_spec == "==26.2"


def test_load_lock_canonicalizes_edge_name(tmp_path: Path) -> None:
    body = """\
[[packages]]
name = "parent"
version = "1.0"
[[packages.dependencies]]
name = "Foo_Bar"
[[packages]]
name = "foo-bar"
version = "2.0"
"""
    dag = PackageDAG.from_pkgs(load_lock(_write(tmp_path, body)))

    (child,) = dag.get_children("parent")
    assert child.key == "foo-bar"
    assert child.version_spec == "==2.0"


def test_load_lock_leaf_has_no_children(tmp_path: Path) -> None:
    body = '[[packages]]\nname = "solo"\nversion = "1.0"\n'

    dag = PackageDAG.from_pkgs(load_lock(_write(tmp_path, body)))

    assert dag.get_children("solo") == []


def test_load_lock_package_without_version(tmp_path: Path) -> None:
    body = """\
[[packages]]
name = "parent"
[[packages.dependencies]]
name = "child"
[[packages]]
name = "child"
"""
    dag = PackageDAG.from_pkgs(load_lock(_write(tmp_path, body)))

    by_key = {str(pkg.key): pkg for pkg in dag}
    assert not by_key["parent"].version
    # An unpinned edge stays unconstrained rather than crashing on the missing version.
    (child,) = dag.get_children("parent")
    assert child.version_spec is None


def test_load_lock_missing_file(tmp_path: Path) -> None:
    with pytest.raises(FromLockError, match="lock file does not exist"):
        load_lock(tmp_path / "absent.toml")


@pytest.mark.parametrize(
    ("body", "match"),
    [
        pytest.param("this is not = = toml", "malformed TOML", id="malformed-toml"),
        pytest.param('name = "x"\n', "missing 'packages' array", id="missing-packages"),
        pytest.param("packages = 3\n", "missing 'packages' array", id="packages-not-array"),
        pytest.param('[[packages]]\nversion = "1.0"\n', "missing 'name'", id="package-missing-name"),
    ],
)
def test_load_lock_malformed(tmp_path: Path, body: str, match: str) -> None:
    with pytest.raises(FromLockError, match=match):
        load_lock(_write(tmp_path, body))


def test_main_from_lock_renders_text_tree(
    tmp_path: Path, mocker: MockerFixture, capsys: pytest.CaptureFixture[str]
) -> None:
    lock = _write(tmp_path, _CHAIN)
    mocker.patch("pipdeptree.__main__.sys.argv", ["", "from-lock", str(lock)])

    assert main() == 0

    out, _ = capsys.readouterr()
    assert "build==1.5.0" in out
    assert "packaging" in out
    assert "pyproject-hooks" in out


def test_main_from_lock_json_output(tmp_path: Path, mocker: MockerFixture, capsys: pytest.CaptureFixture[str]) -> None:
    lock = _write(tmp_path, _CHAIN)
    mocker.patch("pipdeptree.__main__.sys.argv", ["", "from-lock", str(lock), "-o", "json"])

    assert main() == 0

    out, _ = capsys.readouterr()
    assert '"key": "build"' in out


def test_main_from_lock_error(tmp_path: Path, mocker: MockerFixture, capsys: pytest.CaptureFixture[str]) -> None:
    mocker.patch("pipdeptree.__main__.sys.argv", ["", "from-lock", str(tmp_path / "absent.toml")])

    assert main() == 1

    out, err = capsys.readouterr()
    assert not out
    assert "lock file does not exist" in err


def test_get_options_from_lock_parses() -> None:
    options = get_options(["from-lock", "pylock.toml"])

    assert options.command == "from-lock"
    assert options.lock == "pylock.toml"


def test_get_options_bare_keeps_lock_default() -> None:
    options = get_options([])

    assert options.command is None
    assert options.lock is None


@pytest.mark.parametrize(
    "flag",
    [
        pytest.param("--metadata", id="metadata"),
        pytest.param("--license", id="license"),
        pytest.param("--computed", id="computed"),
    ],
)
def test_from_lock_rejects_installed_only_flags(flag: str) -> None:
    with pytest.raises(SystemExit) as exc:
        get_options(["from-lock", "pylock.toml", flag, "size"])
    assert exc.value.code == 2
