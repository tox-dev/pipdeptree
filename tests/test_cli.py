from __future__ import annotations

import json
import runpy
import sys
import tempfile
import webbrowser
from functools import partial
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, create_autospec

import pytest

from pipdeptree import __version__

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence
    from pathlib import Path


@pytest.mark.parametrize(
    ("args", "expected"),
    [
        pytest.param(["--encoding", "ascii"], "root==1", id="text"),
        pytest.param(["--output", "rich"], "root==1", id="rich"),
        pytest.param(["--output", "rich", "--encoding", "ascii"], "`-- ", id="rich-ascii"),
        pytest.param(["--json"], '"package_name": "root"', id="json"),
        pytest.param(["--json-tree"], '"dependencies"', id="json-tree"),
        pytest.param(["--mermaid"], "flowchart TD", id="mermaid"),
        pytest.param(["--graph-output", "dot"], "digraph {", id="graphviz"),
        pytest.param(["--freeze"], "root==1", id="freeze"),
        pytest.param(["--reverse"], "child==1", id="reverse"),
        pytest.param(["--summary"], "total packages:", id="summary"),
        pytest.param(["--summary", "--output", "json"], '"total_packages": 4', id="summary-json"),
        pytest.param(["--summary", "--output", "rich"], "environment summary", id="summary-rich"),
        pytest.param(["--all", "--depth", "0"], "orphan==1", id="all"),
        pytest.param(["--packages", "root[feature]", "--extras", "explicit"], "optional", id="extras"),
        pytest.param(
            ["--metadata", "license", "--computed", "size,size-raw", "--json"],
            '"computed"',
            id="metadata",
        ),
    ],
)
def test_cli_formats(
    entry_point: Callable[[Sequence[str] | None], int | None],
    package_path: Path,
    capsys: pytest.CaptureFixture[str],
    args: list[str],
    expected: str,
) -> None:
    code = entry_point(["--path", str(package_path), "--warn", "silence", *args])

    assert (code, expected in capsys.readouterr().out) == (0, True)


def test_cli_uses_sys_argv(
    entry_point: Callable[[Sequence[str] | None], int | None],
    package_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(sys, "argv", ["pipdeptree", "--path", str(package_path), "--packages", "root"])

    assert (entry_point(None), capsys.readouterr().out.startswith("root==1")) == (0, True)


@pytest.mark.parametrize(
    ("flag", "expected"),
    [
        pytest.param("-h", "Usage:", id="short-help"),
        pytest.param("--help", "Usage:", id="help"),
    ],
)
def test_cli_informational_flags(
    entry_point: Callable[[Sequence[str] | None], int | None],
    flag: str,
    expected: str,
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit, match="0"):
        entry_point([flag])

    assert expected in capsys.readouterr().out


@pytest.mark.parametrize("flag", [pytest.param("-v", id="short"), pytest.param("--version", id="long")])
def test_cli_bare_version(
    entry_point: Callable[[Sequence[str] | None], int | None],
    flag: str,
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit, match="0"):
        entry_point([flag])

    assert capsys.readouterr().out == f"{__version__}\n"


def test_cli_error(
    entry_point: Callable[[Sequence[str] | None], int | None], capsys: pytest.CaptureFixture[str]
) -> None:
    code = entry_point(["--output", "unknown"])
    captured = capsys.readouterr()

    assert (code, captured.out, '"unknown" is not a known output format' in captured.err) == (2, "", True)


def test_cli_missing_filter(
    entry_point: Callable[[Sequence[str] | None], int | None],
    package_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    code = entry_point(["--path", str(package_path), "--packages", "missing"])

    assert (code, "No packages matched" in capsys.readouterr().err) == (0, True)


@pytest.mark.parametrize(
    ("format_args", "expected"),
    [
        pytest.param(["--graph-output", "png"], b"\x89PNG", id="graph-output"),
        pytest.param(["--graph-output=png"], b"\x89PNG", id="graph-output-inline"),
        pytest.param(["--output", "graphviz-png"], b"\x89PNG", id="output"),
        pytest.param(["--output=graphviz-png"], b"\x89PNG", id="output-inline"),
        pytest.param(["-o", "graphviz-png"], b"\x89PNG", id="short-output"),
        pytest.param(["-ographviz-png"], b"\x89PNG", id="short-output-attached"),
        pytest.param(["-ro", "graphviz-png"], b"\x89PNG", id="short-output-clustered"),
        pytest.param(["--graph-output", "pdf"], b"%PDF", id="pdf"),
        pytest.param(["--graph-output", "svg"], b"<?xml", id="svg"),
    ],
)
def test_cli_graphviz_binary(
    entry_point: Callable[[Sequence[str] | None], int | None],
    package_path: Path,
    capsysbinary: pytest.CaptureFixture[bytes],
    format_args: list[str],
    expected: bytes,
) -> None:
    code = entry_point(["--path", str(package_path), *format_args])

    assert (code, capsysbinary.readouterr().out.startswith(expected)) == (0, True)


@pytest.mark.parametrize(
    ("graphviz_format", "opened", "warned", "expected"),
    [
        pytest.param("png", True, False, b"\x89PNG", id="png-opened"),
        pytest.param("png", False, True, b"\x89PNG", id="png-not-opened"),
    ],
)
def test_cli_graphviz_binary_terminal(
    entry_point: Callable[[Sequence[str] | None], int | None],
    package_path: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsysbinary: pytest.CaptureFixture[bytes],
    *,
    graphviz_format: str,
    opened: bool,
    warned: bool,
    expected: bytes,
) -> None:
    named_temporary_file = tempfile.NamedTemporaryFile
    opener = create_autospec(webbrowser.open, return_value=opened)
    monkeypatch.setattr(tempfile, "NamedTemporaryFile", partial(named_temporary_file, dir=tmp_path))
    monkeypatch.setattr(webbrowser, "open", opener)
    monkeypatch.setattr(sys.stdout, "isatty", lambda: True)

    code = entry_point(["--path", str(package_path), "--graph-output", graphviz_format])
    captured = capsysbinary.readouterr()
    image = next(tmp_path.glob(f"*.{graphviz_format}"))

    assert (
        code,
        captured.out,
        image.read_bytes().startswith(expected),
        b"Could not open file" in captured.err,
        opener.call_args.args,
    ) == (0, b"", True, warned, (str(image),))


@pytest.fixture
def terminal_browser(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    opener = create_autospec(webbrowser.open, return_value=True)
    monkeypatch.setattr(webbrowser, "open", opener)
    monkeypatch.setattr(sys.stdout, "isatty", lambda: True)
    return opener


def test_cli_graphviz_text_terminal(
    entry_point: Callable[[Sequence[str] | None], int | None],
    package_path: Path,
    terminal_browser: MagicMock,
    capsys: pytest.CaptureFixture[str],
) -> None:
    code = entry_point(["--path", str(package_path), "--graph-output", "svg"])

    assert (code, capsys.readouterr().out.startswith("<?xml"), terminal_browser.called) == (0, True, False)


def test_cli_help_with_graphviz_format(
    entry_point: Callable[[Sequence[str] | None], int | None],
    terminal_browser: MagicMock,
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit, match="0"):
        entry_point(["--graph-output", "png", "--help"])

    assert ("Usage:" in capsys.readouterr().out, terminal_browser.called) == (True, False)


def test_cli_lock(
    entry_point: Callable[[Sequence[str] | None], int | None],
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    lock = tmp_path / "pylock.toml"
    lock.write_text('[[packages]]\nname = "locked"\nversion = "1"\n')

    assert (entry_point(["from-lock", str(lock)]), "locked==1" in capsys.readouterr().out) == (0, True)


def test_module_entrypoint(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setattr(sys, "argv", ["pipdeptree", "--version"])

    with pytest.raises(SystemExit, match="0"):
        runpy.run_module("pipdeptree", run_name="__main__")

    assert capsys.readouterr().out == f"{__version__}\n"


def test_cli_json_is_valid(
    entry_point: Callable[[Sequence[str] | None], int | None],
    package_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    code = entry_point(["--path", str(package_path), "--json"])

    assert (code, len(json.loads(capsys.readouterr().out))) == (0, 4)


def test_cli_uses_implementation_version_marker(
    entry_point: Callable[[Sequence[str] | None], int | None],
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    implementation = sys.implementation.version
    suffix = (
        "" if implementation.releaselevel == "final" else f"{implementation.releaselevel[0]}{implementation.serial}"
    )
    version = f"{implementation.major}.{implementation.minor}.{implementation.micro}{suffix}"
    root = tmp_path / "root-1.dist-info"
    root.mkdir()
    (root / "METADATA").write_text(
        f"Name: root\nVersion: 1\nRequires-Dist: child; implementation_version == '{version}'\n"
    )
    child = tmp_path / "child-1.dist-info"
    child.mkdir()
    (child / "METADATA").write_text("Name: child\nVersion: 1\n")

    code = entry_point(["--path", str(tmp_path), "--packages", "root"])

    assert (code, "child" in capsys.readouterr().out) == (0, True)


@pytest.mark.parametrize(
    ("environment", "tty", "colored"),
    [
        pytest.param({}, True, True, id="terminal"),
        pytest.param({"TERM": "dumb"}, True, False, id="dumb"),
        pytest.param({"NO_COLOR": ""}, True, False, id="no-color"),
        pytest.param({}, False, False, id="pipe"),
        pytest.param({"FORCE_COLOR": "1"}, False, True, id="force-color"),
        pytest.param({"FORCE_COLOR": "1", "NO_COLOR": ""}, True, False, id="force-color-overridden"),
    ],
)
def test_cli_terminal_color(
    entry_point: Callable[[Sequence[str] | None], int | None],
    package_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    environment: dict[str, str],
    *,
    tty: bool,
    colored: bool,
) -> None:
    monkeypatch.setattr(sys.stdout, "isatty", lambda: tty)
    for name in ("TERM", "NO_COLOR", "FORCE_COLOR"):
        monkeypatch.delenv(name, raising=False)
    for name, value in environment.items():
        monkeypatch.setenv(name, value)

    code = entry_point(["--path", str(package_path), "--warn", "silence", "--output", "rich", "--depth", "0"])

    assert (code, "\x1b[" in capsys.readouterr().out) == (0, colored)


def test_cli_defaults_to_text_on_terminals(
    entry_point: Callable[[Sequence[str] | None], int | None],
    package_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(sys.stdout, "isatty", lambda: True)
    monkeypatch.delenv("TERM", raising=False)
    monkeypatch.delenv("NO_COLOR", raising=False)

    code = entry_point(["--path", str(package_path), "--warn", "silence"])
    out = capsys.readouterr().out

    assert (code, "\x1b[" in out, "└──" in out) == (0, False, True)
