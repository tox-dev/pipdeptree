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
    color = "NO_COLOR" not in os.environ and (
        "FORCE_COLOR" in os.environ or (sys.stdout.isatty() and os.environ.get("TERM") != "dumb")
    )
    code, stdout, stderr, graphviz_format = execute(argv, color=color)
    _write(sys.stdout, stdout, graphviz_format=graphviz_format)
    if stderr:
        sys.stderr.write(stderr)
    if code == 0 and any(value in {"-h", "--help", "-v", "--version"} for value in argv):
        raise SystemExit(0)
    return code


def _write(stream: TextIO, value: bytes, *, graphviz_format: str | None) -> None:
    if not value:
        return
    try:
        text = value.decode()
    except UnicodeDecodeError:
        pass
    else:
        stream.write(text)
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
