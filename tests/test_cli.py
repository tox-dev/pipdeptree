from __future__ import annotations

import io
import json
import os
import re
import runpy
import shutil
import subprocess  # ruff: ignore[suspicious-subprocess-import] # pip only runs as a child process
import sys
import tarfile
import tempfile
import textwrap
import venv
import webbrowser
import zipfile
from functools import partial
from typing import TYPE_CHECKING, Final
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


@pytest.mark.parametrize(
    ("tty", "no_color", "expected_width"),
    [
        pytest.param(True, False, 40, id="terminal"),
        pytest.param(True, True, 40, id="terminal-no-color"),
        pytest.param(False, False, 69, id="redirected"),
    ],
)
def test_cli_summary_terminal_width(
    entry_point: Callable[[Sequence[str] | None], int | None],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    expected_width: int,
    *,
    tty: bool,
    no_color: bool,
) -> None:
    (tmp_path / "demo-1.dist-info").mkdir()
    (tmp_path / "demo-1.dist-info" / "METADATA").write_text(
        "Name: demo\nVersion: 1\nLicense-Expression: MIT OR Apache-2.0 OR BSD-3-Clause\n"
    )
    monkeypatch.setattr(sys.stdout, "isatty", lambda: tty)
    monkeypatch.setattr(
        shutil, "get_terminal_size", create_autospec(shutil.get_terminal_size, return_value=os.terminal_size((40, 24)))
    )
    monkeypatch.delenv("TERM", raising=False)
    monkeypatch.delenv("FORCE_COLOR", raising=False)
    if no_color:
        monkeypatch.setenv("NO_COLOR", "1")
    else:
        monkeypatch.delenv("NO_COLOR", raising=False)

    code: Final = entry_point(["--path", str(tmp_path), "--warn", "silence", "--summary", "-o", "rich"])
    lines: Final = re.sub(r"\x1b\[[0-9;]*m", "", capsys.readouterr().out).splitlines()

    assert (code, {len(line) for line in lines}) == (0, {expected_width})


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


@pytest.mark.parametrize(
    "errors", [pytest.param("strict", id="strict"), pytest.param("surrogateescape", id="surrogateescape")]
)
def test_cli_escapes_characters_stdout_cannot_encode(
    entry_point: Callable[[Sequence[str] | None], int | None],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    errors: str,
) -> None:
    for directory, name, version in (("app-2.0", "app", "2.0"), ("demo-0.1", "demoé", "0.1")):
        (tmp_path / f"{directory}.dist-info").mkdir()
        (tmp_path / f"{directory}.dist-info" / "METADATA").write_text(
            f"Name: {name}\nVersion: {version}\n", encoding="utf-8"
        )
    output: Final = io.BytesIO()
    monkeypatch.setattr(sys, "stdout", io.TextIOWrapper(output, encoding="ascii", errors=errors, write_through=True))

    code = entry_point(["--path", str(tmp_path)])

    assert (code, output.getvalue()) == (0, f"app==2.0{os.linesep}demo\\xe9==0.1{os.linesep}".encode())


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
def browser(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    opener = create_autospec(webbrowser.open, return_value=True)
    monkeypatch.setattr(webbrowser, "open", opener)
    return opener


@pytest.mark.parametrize(
    ("format_args", "expected"),
    [
        pytest.param(["--graph-output", "svg"], b"<?xml", id="svg"),
        pytest.param(
            ["--metadata", "Summary", "--graph-output", "ps"], "(café)".encode("latin-1"), id="ps-latin-1-label"
        ),
    ],
)
def test_cli_graphviz_text_terminal(
    entry_point: Callable[[Sequence[str] | None], int | None],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    browser: MagicMock,
    capsysbinary: pytest.CaptureFixture[bytes],
    format_args: list[str],
    expected: bytes,
) -> None:
    (tmp_path / "demo-1.dist-info").mkdir()
    (tmp_path / "demo-1.dist-info" / "METADATA").write_text("Name: demo\nVersion: 1\nSummary: café\n", encoding="utf-8")
    monkeypatch.setattr(sys.stdout, "isatty", lambda: True)

    code = entry_point(["--path", str(tmp_path), *format_args])

    assert (code, expected in capsysbinary.readouterr().out, browser.called) == (0, True, False)


def test_cli_help_with_graphviz_format(
    entry_point: Callable[[Sequence[str] | None], int | None],
    monkeypatch: pytest.MonkeyPatch,
    browser: MagicMock,
    capsys: pytest.CaptureFixture[str],
) -> None:
    # pytest installs the capture stream only when the test body starts, so a fixture cannot patch it.
    monkeypatch.setattr(sys.stdout, "isatty", lambda: True)

    with pytest.raises(SystemExit, match="0"):
        entry_point(["--graph-output", "png", "--help"])

    assert ("Usage:" in capsys.readouterr().out, browser.called) == (True, False)


def test_cli_lock(
    entry_point: Callable[[Sequence[str] | None], int | None],
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    lock = tmp_path / "pylock.toml"
    lock.write_text('[[packages]]\nname = "locked"\nversion = "1"\n')

    assert (entry_point(["from-lock", str(lock)]), "locked==1" in capsys.readouterr().out) == (0, True)


def test_cli_index_empty_project(
    entry_point: Callable[[Sequence[str] | None], int | None],
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    project: Final = tmp_path / "pyproject.toml"
    project.write_text('[project]\nname = "empty"\nversion = "1"\ndependencies = []\n')

    code: Final = entry_point(["from-index", "--pyproject", str(project), "--json"])
    captured: Final = capsys.readouterr()

    assert (code, json.loads(captured.out), captured.err) == (0, [], "")


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        pytest.param(["member"], "member==2\n", id="generated"),
        pytest.param(["--pyproject", "project/pyproject.toml"], "member==1\n", id="pyproject"),
    ],
)
def test_cli_index_workspace_above_project(
    entry_point: Callable[[Sequence[str] | None], int | None],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    source: list[str],
    expected: str,
) -> None:
    (tmp_path / "nab.toml").write_text('[workspace]\nmembers = ["member"]\n')
    for name, dependencies in (("member", []), ("project", ["member"])):
        (tmp_path / name).mkdir()
        (tmp_path / name / "pyproject.toml").write_text(
            f'[project]\nname = "{name}"\nversion = "1"\ndependencies = {dependencies}\n'
        )
    index: Final = tmp_path / "index"
    index.mkdir()
    with zipfile.ZipFile(index / "member-2-py3-none-any.whl", "w") as wheel:
        wheel.writestr("member-2.dist-info/METADATA", "Metadata-Version: 2.1\nName: member\nVersion: 2\n")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("NAB_CACHE_DIR", str(tmp_path / "cache"))
    for name in ("TMPDIR", "TMP", "TEMP"):
        monkeypatch.setenv(name, str(tmp_path))

    code: Final = entry_point(["from-index", *source, "--index-url", index.as_uri()])

    assert (code, capsys.readouterr().out) == (0, expected)


def test_cli_index_local_source_leaves_index_sdist_unbuilt(
    entry_point: Callable[[Sequence[str] | None], int | None],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    built: Final = tmp_path / "built"
    _write_dynamic_project(tmp_path / "remote-1", "remote", built, "hooks")
    index: Final = tmp_path / "index"
    index.mkdir()
    with tarfile.open(index / "remote-1.tar.gz", "w:gz") as archive:
        archive.add(tmp_path / "remote-1", "remote-1")
    local: Final = tmp_path / "local"
    local.mkdir()
    (local / "pyproject.toml").write_text('[project]\nname = "local"\nversion = "1"\ndependencies = ["remote"]\n')
    monkeypatch.setenv("NAB_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.chdir(tmp_path)

    entry_point(["from-index", "./local", "--index-url", index.as_uri()])

    assert (built.exists(), "remote: every version in range was rejected" in capsys.readouterr().err) == (False, True)


@pytest.mark.parametrize(
    ("mode", "expected"),
    [
        pytest.param("silence", (0, False), id="silence"),
        pytest.param("suppress", (0, True), id="suppress"),
        pytest.param("fail", (1, True), id="fail"),
    ],
)
def test_cli_index_warns_about_requirements_index_option(
    entry_point: Callable[[Sequence[str] | None], int | None],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    mode: str,
    expected: tuple[int, bool],
) -> None:
    requirements: Final = tmp_path / "requirements.txt"
    requirements.write_text("-i https://private.example/simple\n")
    monkeypatch.setenv("NAB_CACHE_DIR", str(tmp_path / "cache"))

    code: Final = entry_point(["--warn", mode, "from-index", "--requirements", str(requirements)])
    warning: Final = ":1: from-index ignores -i in requirements files; pass --index-url on the command line\n"

    assert (code, capsys.readouterr().err.endswith(warning)) == expected


@pytest.mark.parametrize(
    "backend_path",
    [
        pytest.param("hooks", id="subdirectory"),
        pytest.param(".", id="project-root"),
    ],
)
def test_cli_index_builds_dynamic_local_source(
    entry_point: Callable[[Sequence[str] | None], int | None],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    backend_path: str,
) -> None:
    _write_dynamic_project(tmp_path / "local", "local", tmp_path / "built", backend_path)
    index: Final = tmp_path / "index"
    index.mkdir()
    monkeypatch.setenv("NAB_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.chdir(tmp_path)

    code: Final = entry_point(["from-index", "./local", "--index-url", index.as_uri()])

    assert (code, capsys.readouterr().out) == (0, "local==1\n")


@pytest.mark.parametrize(
    "source",
    [
        pytest.param(lambda root: [str(root / "local")], id="absolute"),
        pytest.param(lambda _: [f".{os.sep}local"], id="relative"),
        pytest.param(lambda _: ["--requirements", "requirements.txt"], id="requirements-file"),
    ],
)
def test_cli_index_local_source_native_path(
    entry_point: Callable[[Sequence[str] | None], int | None],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    source: Callable[[Path], list[str]],
) -> None:
    (tmp_path / "local").mkdir()
    (tmp_path / "local" / "pyproject.toml").write_text('[project]\nname = "local"\nversion = "1"\n')
    (tmp_path / "requirements.txt").write_text(f"{tmp_path / 'local'}\n")
    index: Final = tmp_path / "index"
    index.mkdir()
    monkeypatch.setenv("NAB_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.chdir(tmp_path)

    code: Final = entry_point(["from-index", *source(tmp_path), "--index-url", index.as_uri()])

    assert (code, capsys.readouterr().out) == (0, "local==1\n")


@pytest.mark.parametrize(
    ("content", "expected"),
    [
        pytest.param("demo ==\n", "{path}:1: invalid requirement\n", id="invalid-line"),
        pytest.param("-r requirements.txt\n", "recursive requirements include: {path}\n", id="recursive"),
    ],
)
def test_cli_index_requirements_error_names_plain_path(
    entry_point: Callable[[Sequence[str] | None], int | None],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    content: str,
    expected: str,
) -> None:
    requirements: Final = tmp_path / "requirements.txt"
    requirements.write_text(content)
    monkeypatch.chdir(tmp_path)

    code: Final = entry_point(["from-index", "--requirements", "requirements.txt"])

    assert (code, capsys.readouterr().err) == (1, expected.format(path=requirements.resolve()))


def _write_dynamic_project(directory: Path, name: str, marker: Path, backend_path: str) -> None:
    (directory / backend_path).mkdir(parents=True)
    (directory / "pyproject.toml").write_text(
        f'[build-system]\nrequires = []\nbuild-backend = "backend"\nbackend-path = ["{backend_path}"]\n'
        f'[project]\nname = "{name}"\nversion = "1"\ndynamic = ["dependencies"]\n'
    )
    (directory / "PKG-INFO").write_text(f"Metadata-Version: 2.1\nName: {name}\nVersion: 1\n")
    (directory / backend_path / "backend.py").write_text(
        f"import os\nopen({str(marker)!r}, 'w').close()\n"
        "def prepare_metadata_for_build_wheel(metadata_directory, config_settings=None):\n"
        f"    os.mkdir(os.path.join(metadata_directory, '{name}-1.dist-info'))\n"
        f"    with open(os.path.join(metadata_directory, '{name}-1.dist-info', 'METADATA'), 'w') as metadata:\n"
        f"        metadata.write('Metadata-Version: 2.1\\nName: {name}\\nVersion: 1\\n')\n"
        f"    return '{name}-1.dist-info'\n"
    )


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


@pytest.mark.xfail(
    sys.implementation.version.releaselevel != "final",
    reason="pep508_rs drops pre-release segments from marker specifiers, so no specifier can equal a pre-release "
    "interpreter version",
    strict=True,
)
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


def test_cli_defaults_to_rich_on_terminals(
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

    assert (code, "\x1b[" in out, "┗━━" in out) == (0, True, True)


def test_cli_freeze_editable_installs_with_pip(
    entry_point: Callable[[Sequence[str] | None], int | None],
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    project = tmp_path / "proj"
    project.mkdir()
    # pip installs an editable project offline only when it needs no build requirements.
    (project / "backend.py").write_text(
        textwrap.dedent("""\
            import pathlib
            import zipfile


            def build_editable(wheel_directory, config_settings=None, metadata_directory=None):
                with zipfile.ZipFile(pathlib.Path(wheel_directory) / "demo-1-py3-none-any.whl", "w") as wheel:
                    wheel.writestr("demo-1.dist-info/METADATA", "Metadata-Version: 2.1\\nName: demo\\nVersion: 1\\n")
                    wheel.writestr("demo-1.dist-info/WHEEL", "Wheel-Version: 1\\nRoot-Is-Purelib: true\\n")
                    wheel.writestr("demo-1.dist-info/RECORD", "")
                return "demo-1-py3-none-any.whl"
        """),
        encoding="utf-8",
    )
    (project / "pyproject.toml").write_text(
        '[build-system]\nrequires = []\nbuild-backend = "backend"\nbackend-path = ["."]\n', encoding="utf-8"
    )
    builder = venv.EnvBuilder(with_pip=True)
    environment = tmp_path / "venv"
    python = builder.ensure_directories(environment).env_exe
    builder.create(environment)
    subprocess.run([python, "-m", "pip", "install", "-q", "--no-index", "-e", str(project)], check=True)
    entry_point(["--python", python, "--freeze", "--packages", "demo"])
    requirements = tmp_path / "requirements.txt"
    requirements.write_text(capsys.readouterr().out, encoding="utf-8")

    install = subprocess.run(
        [python, "-m", "pip", "install", "--dry-run", "--no-deps", "--no-index", "-r", str(requirements)],
        capture_output=True,
        text=True,
        check=False,
    )

    assert (install.returncode, "Would install demo-1" in install.stdout) == (0, True), install.stderr
