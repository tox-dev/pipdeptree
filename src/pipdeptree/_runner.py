from __future__ import annotations

import os
import shutil
import sys
import tempfile
import webbrowser
from typing import TYPE_CHECKING, Final

from pipdeptree._rust import execute

if TYPE_CHECKING:
    from collections.abc import Sequence
    from typing import TextIO

# The text formats of https://graphviz.org/docs/outputs/; dot writes PostScript labels as Latin-1, so whether the output
# decodes as UTF-8 cannot tell a text format from an image.
_GRAPHVIZ_TEXT_FORMATS: Final = frozenset({
    "canon",
    "cmap",
    "cmapx",
    "cmapx_np",
    "dot",
    "dot_json",
    "eps",
    "fig",
    "gv",
    "imap",
    "imap_np",
    "ismap",
    "json",
    "json0",
    "mp",
    "pic",
    "plain",
    "plain-ext",
    "pov",
    "ps",
    "ps2",
    "svg",
    "tk",
    "vdx",
    "vml",
    "vrml",
    "xdot",
    "xdot1.2",
    "xdot1.4",
    "xdot_json",
})


def main(args: Sequence[str] | None = None) -> int | None:
    """Return the CLI exit code; help and version requests exit after writing their output."""
    argv = list(sys.argv[1:] if args is None else args)
    if not any(value == "--encoding" or value.startswith("--encoding=") for value in argv):
        argv[:0] = ["--encoding", sys.stdout.encoding or "utf-8"]
    color = "NO_COLOR" not in os.environ and (
        "FORCE_COLOR" in os.environ or (sys.stdout.isatty() and os.environ.get("TERM") != "dumb")
    )
    code, stdout, stderr, graphviz_format = execute(
        argv,
        color=color,
        terminal_width=shutil.get_terminal_size().columns if sys.stdout.isatty() else None,
    )
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
        try:
            stream.write(text)
        except UnicodeEncodeError:
            stream.write(text.encode(stream.encoding, "backslashreplace").decode(stream.encoding))
        return
    if not stream.isatty() or (graphviz_format or "").partition(":")[0] in _GRAPHVIZ_TEXT_FORMATS:
        stream.buffer.write(value)
        return
    with tempfile.NamedTemporaryFile(suffix=f".{graphviz_format}", delete=False) as temporary:
        temporary.write(value)
    sys.stderr.write(f"Binary output file written to: {temporary.name}\n")
    sys.stderr.write("Opening file with default application...\n")
    if not webbrowser.open(temporary.name):
        sys.stderr.write("Could not open file with default application. Please open it manually.\n")


__all__ = [
    "main",
]
