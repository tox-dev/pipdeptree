from __future__ import annotations

import os
import sys
import tempfile
import webbrowser
from typing import TYPE_CHECKING

from pipdeptree._rust import execute

if TYPE_CHECKING:
    from collections.abc import Sequence
    from typing import TextIO


def main(args: Sequence[str] | None = None) -> int | None:
    """Return the CLI exit code; help and version requests exit after writing their output."""
    argv = list(sys.argv[1:] if args is None else args)
    if not any(value == "--encoding" or value.startswith("--encoding=") for value in argv):
        argv[:0] = ["--encoding", sys.stdout.encoding or "utf-8"]
    code, stdout, stderr = execute(
        argv,
        color=sys.stdout.isatty() and os.environ.get("TERM") != "dumb" and "NO_COLOR" not in os.environ,
    )
    _write(sys.stdout, stdout, graphviz_format=_graphviz_format(argv))
    if stderr:
        sys.stderr.write(stderr)
    if code == 0 and any(value in {"-h", "--help", "-v", "--version"} for value in argv):
        raise SystemExit(0)
    return code


def _graphviz_format(args: Sequence[str]) -> str | None:
    arguments = iter(args)
    for argument in arguments:
        name, separator, value = argument.partition("=")
        if name.startswith("-o") and not name.startswith("--") and name != "-o":
            value = name[2:]
            name = "-o"
        if not separator and name in {"--graph-output", "--output", "-o"}:
            value = value or next(arguments, "")
        if name == "--graph-output":
            return value
        if name in {"--output", "-o"} and value.startswith("graphviz-"):
            return value.removeprefix("graphviz-")
    return None


def _write(stream: TextIO, value: bytes, *, graphviz_format: str | None) -> None:
    if not value:
        return
    if graphviz_format is None or graphviz_format == "dot":
        stream.write(value.decode())
        return
    if not stream.isatty():
        stream.buffer.write(value)
        return
    with tempfile.NamedTemporaryFile(suffix=f".{graphviz_format}", delete=False) as temporary:
        temporary.write(value)
    sys.stderr.write(f"Binary output file written to: {temporary.name}\n")
    sys.stderr.write("Opening file with default application...\n")
    if not webbrowser.open(temporary.name):
        sys.stderr.write("Could not open file with default application. Please open it manually.\n")


__all__ = ["main"]
