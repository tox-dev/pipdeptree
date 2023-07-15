from __future__ import annotations

import sys
from argparse import ArgumentParser, Namespace
from typing import TYPE_CHECKING, cast

from .version import __version__

if TYPE_CHECKING:
    from typing import Literal


class Options(Namespace):
    freeze: bool
    python: str
    all: bool  # noqa: A003
    local_only: bool
    warn: Literal["silence", "suppress", "fail"]
    reverse: bool
    packages: str
    exclude: str
    json: bool
    json_tree: bool
    mermaid: bool
    graph_output: str | None
    depth: float
    encoding: str


def build_parser() -> ArgumentParser:
    parser = ArgumentParser(description="Dependency tree of the installed python packages")
    parser.add_argument("-v", "--version", action="version", version=f"{__version__}")
    parser.add_argument("-f", "--freeze", action="store_true", help="Print names so as to write freeze files")
    parser.add_argument(
        "--python",
        default=sys.executable,
        help="Python to use to look for packages in it (default: where installed)",
    )
    parser.add_argument("-a", "--all", action="store_true", help="list all deps at top level")
    parser.add_argument(
        "-l",
        "--local-only",
        action="store_true",
        help="If in a virtualenv that has global access do not show globally installed packages",
    )
    parser.add_argument("-u", "--user-only", action="store_true", help="Only show installations in the user site dir")
    parser.add_argument(
        "-w",
        "--warn",
        action="store",
        dest="warn",
        nargs="?",
        default="suppress",
        choices=("silence", "suppress", "fail"),
        help=(
            'Warning control. "suppress" will show warnings '
            "but return 0 whether or not they are present. "
            '"silence" will not show warnings at all and '
            'always return 0. "fail" will show warnings and '
            "return 1 if any are present. The default is "
            '"suppress".'
        ),
    )
    parser.add_argument(
        "-r",
        "--reverse",
        action="store_true",
        default=False,
        help=(
            "Shows the dependency tree in the reverse fashion "
            "ie. the sub-dependencies are listed with the "
            "list of packages that need them under them."
        ),
    )
    parser.add_argument(
        "-p",
        "--packages",
        help=(
            "Comma separated list of select packages to show in the output. "
            "Wildcards are supported, like 'somepackage.*'. "
            "If set, --all will be ignored."
        ),
    )
    parser.add_argument(
        "-e",
        "--exclude",
        help=(
            "Comma separated list of select packages to exclude from the output. "
            "Wildcards are supported, like 'somepackage.*'. "
            "If set, --all will be ignored."
        ),
        metavar="PACKAGES",
    )
    parser.add_argument(
        "-j",
        "--json",
        action="store_true",
        default=False,
        help=(
            "Display dependency tree as json. This will yield "
            '"raw" output that may be used by external tools. '
            "This option overrides all other options."
        ),
    )
    parser.add_argument(
        "--json-tree",
        action="store_true",
        default=False,
        help=(
            "Display dependency tree as json which is nested "
            "the same way as the plain text output printed by default. "
            "This option overrides all other options (except --json)."
        ),
    )
    parser.add_argument(
        "--mermaid",
        action="store_true",
        default=False,
        help="Display dependency tree as a Mermaid graph. This option overrides all other options.",
    )
    parser.add_argument(
        "--graph-output",
        dest="output_format",
        help=(
            "Print a dependency graph in the specified output "
            "format. Available are all formats supported by "
            "GraphViz, e.g.: dot, jpeg, pdf, png, svg"
        ),
    )
    parser.add_argument(
        "-d",
        "--depth",
        type=lambda x: int(x) if x.isdigit() and (int(x) >= 0) else parser.error("Depth must be a number that is >= 0"),
        default=float("inf"),
        help=(
            "Display dependency tree up to a depth >=0 using the default text display. All other display options"
            " ignore this argument."
        ),
    )
    parser.add_argument(
        "--encoding",
        dest="encoding_type",
        default=sys.stdout.encoding,
        help="Display dependency tree as text using specified encoding",
    )
    return parser


def get_options() -> Options:
    parser = build_parser()
    return cast(Options, parser.parse_args())


__all__ = [
    "get_options",
    "Options",
]
