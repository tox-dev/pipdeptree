from __future__ import annotations

import doctest
import os
import shlex
import tempfile
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import dataclass
from io import StringIO
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator, Sequence

    EntryPoint = Callable[[Sequence[str] | None], int | None]

_SKIP_MARKERS = frozenset({".. runs-online", ".. illustrative"})
_CONFLICTING_MARKER = ".. conflicting-environment"
_INDENT = "    "


def test_documented_cli_output(
    entry_point: EntryPoint,
    console_document: Path,
    documentation_path: Path,
    conflicting_documentation_path: Path,
    update_docs: bool,  # pytest injects the flag fixture by name.
) -> None:
    failures = _check_document(
        console_document,
        entry_point,
        documentation_path,
        conflicting_documentation_path,
        update=update_docs,
    )

    joined = "\n\n".join(failures)
    assert not failures, f"{console_document}: {len(failures)} console example(s) out of sync:\n\n{joined}"


def test_update_docs_rewrites_stale_output(
    entry_point: EntryPoint,
    tmp_path: Path,
    documentation_path: Path,
    conflicting_documentation_path: Path,
) -> None:
    document = tmp_path / "sample.rst"
    document.write_text(
        ".. code-block:: console\n"
        "\n"
        "    $ pipdeptree --packages pytest --depth 0\n"
        "    stale==0\n"
        "    $ echo $?\n"
        "    5\n"
        "\n"
        ".. code-block:: console\n"
        "\n"
        "    $ pipdeptree from-index\n"
        "    pipdeptree: error: from-index needs at least...\n",
        encoding="utf-8",
    )

    failures = _check_document(document, entry_point, documentation_path, conflicting_documentation_path, update=True)

    assert (failures, document.read_text(encoding="utf-8")) == (
        [],
        (
            ".. code-block:: console\n"
            "\n"
            "    $ pipdeptree --packages pytest --depth 0\n"
            "    pytest==9.1.1\n"
            "    $ echo $?\n"
            "    0\n"
            "\n"
            ".. code-block:: console\n"
            "\n"
            "    $ pipdeptree from-index\n"
            "    pipdeptree: error: from-index needs at least...\n"
        ),
    )


def test_documented_cli_output_reports_stale_examples(
    entry_point: EntryPoint,
    tmp_path: Path,
    documentation_path: Path,
    conflicting_documentation_path: Path,
) -> None:
    document = tmp_path / "sample.rst"
    document.write_text(
        ".. code-block:: toml\n"
        "    :caption: pylock.toml\n"
        "    :linenos:\n"
        "\n"
        '    lock-version = "1.0"\n'
        "\n"
        ".. code-block:: console\n"
        "\n"
        "    $ pipdeptree from-lock pylock.toml\n"
        "    stale==0\n"
        "    $ echo $?\n"
        "    0\n",
        encoding="utf-8",
    )

    failures = _check_document(document, entry_point, documentation_path, conflicting_documentation_path, update=False)

    assert [failure.splitlines()[0] for failure in failures] == ["$ pipdeptree from-lock pylock.toml"] * 2


@dataclass(frozen=True)
class _Example:
    arguments: tuple[str, ...]
    expected: str
    output_lines: range
    exit_code: int | None
    exit_code_line: int | None
    skipped: bool
    conflicting: bool
    files: tuple[tuple[str, str], ...]


def _check_document(
    document: Path,
    entry_point: EntryPoint,
    documentation_path: Path,
    conflicting_documentation_path: Path,
    *,
    update: bool,
) -> list[str]:
    def execute(example: _Example) -> tuple[int, str]:
        argv = list(example.arguments)
        if not any(value in {"-w", "--warn"} or value.startswith("--warn=") for value in argv):
            argv[:0] = ["--warn", "silence"]
        environment = conflicting_documentation_path if example.conflicting else documentation_path
        output = StringIO()
        cwd = Path.cwd()
        with tempfile.TemporaryDirectory() as workdir:
            for name, content in example.files:
                (Path(workdir) / name).write_text(content, encoding="utf-8")
            os.chdir(workdir)
            try:
                with redirect_stdout(output), redirect_stderr(output):
                    code = entry_point(["--path", str(environment), *argv])
            finally:
                os.chdir(cwd)
        # graphviz dot output contains tabs; documented blocks show them expanded.
        return code or 0, output.getvalue().expandtabs(4)

    lines = document.read_text(encoding="utf-8").splitlines()
    # A command shown without output or exit code is illustrative; running it would gain nothing
    # and may reach the network (documented private-index invocations).
    runnable = [
        example
        for example in _console_examples(lines)
        if not example.skipped and (example.expected or example.exit_code is not None)
    ]
    checker = doctest.OutputChecker()
    failures = []
    # Reversed so in-place output splices keep the earlier examples' line ranges valid.
    for example in reversed(runnable):
        code, actual = execute(example)
        normalized = f"{actual.rstrip()}\n" if actual.strip() else ""
        matched = not example.expected or checker.check_output(example.expected, normalized, doctest.ELLIPSIS)
        if update:
            _refresh(lines, example, code, actual, matched=matched)
            continue
        command = f"$ pipdeptree {shlex.join(example.arguments)}"
        if not matched:
            failures.append(f"{command}\nexpected:\n{example.expected}got:\n{normalized}")
        if example.exit_code is not None and code != example.exit_code:
            failures.append(f"{command}\nexpected exit code {example.exit_code}, got {code}")
    if update:
        document.write_text("\n".join(lines) + "\n", encoding="utf-8")
    failures.reverse()
    return failures


def _refresh(lines: list[str], example: _Example, code: int, actual: str, *, matched: bool) -> None:
    # A matching block keeps its hand-written form (ellipsis abbreviations).
    if example.exit_code_line is not None and code != example.exit_code:
        lines[example.exit_code_line] = f"{_INDENT}{code}"
    if example.expected and not matched:
        rendered = [f"{_INDENT}{line}".rstrip() for line in actual.rstrip("\n").splitlines()]
        lines[example.output_lines.start : example.output_lines.stop] = rendered


def _console_examples(lines: list[str]) -> Iterator[_Example]:
    files: dict[str, str] = {}
    for start, line in enumerate(lines):
        directive = line.strip()
        if not directive.startswith(".. code-block::"):
            continue
        stop = start + 1
        caption = None
        while stop < len(lines) and lines[stop].strip().startswith(":"):
            option, _, value = lines[stop].strip().partition(" ")
            if option == ":caption:":
                caption = value
            stop += 1
        content_start = stop
        while stop < len(lines) and (not lines[stop].strip() or lines[stop].startswith(_INDENT)):
            stop += 1
        if caption is not None:
            content = "\n".join(lines[row][len(_INDENT) :] for row in range(content_start, stop)).strip()
            files[caption] = f"{content}\n"
        elif directive == ".. code-block:: console":
            markers = {previous.strip() for previous in lines[max(start - 2, 0) : start]}
            yield from _block_examples(
                lines,
                content_start,
                stop,
                skipped=bool(markers & _SKIP_MARKERS),
                conflicting=_CONFLICTING_MARKER in markers,
                files=tuple(files.items()),
            )


def _block_examples(
    lines: list[str],
    start: int,
    stop: int,
    *,
    skipped: bool,
    conflicting: bool,
    files: tuple[tuple[str, str], ...],
) -> Iterator[_Example]:
    commands = [
        (index, lines[index][len(_INDENT) :]) for index in range(start, stop) if lines[index].startswith(f"{_INDENT}$")
    ]
    for position, (index, command) in enumerate(commands):
        parts = shlex.split(command)
        if parts[:2] != ["$", "pipdeptree"]:
            continue
        following = commands[position + 1] if position + 1 < len(commands) else None
        output_stop = following[0] if following else stop
        while output_stop > index + 1 and not lines[output_stop - 1].strip():
            output_stop -= 1
        exit_code = exit_code_line = None
        if following and following[1].strip() == "$ echo $?":
            exit_code_line = following[0] + 1
            exit_code = int(lines[exit_code_line][len(_INDENT) :])
        expected = "\n".join(lines[row][len(_INDENT) :] for row in range(index + 1, output_stop)).rstrip()
        yield _Example(
            arguments=tuple(parts[2:]),
            expected=f"{expected}\n" if expected else "",
            output_lines=range(index + 1, output_stop),
            exit_code=exit_code,
            exit_code_line=exit_code_line,
            skipped=skipped,
            conflicting=conflicting,
            files=files,
        )
