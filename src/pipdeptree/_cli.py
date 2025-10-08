from __future__ import annotations

import sys
from argparse import ArgumentDefaultsHelpFormatter, ArgumentParser, Namespace
from typing import TYPE_CHECKING, cast

from .version import __version__

if TYPE_CHECKING:
    from collections.abc import Sequence


class Options(Namespace):
    freeze: bool
    python: str
    path: list[str]
    all: bool
    local_only: bool
    user_only: bool
    warn: str
    reverse: bool
    packages: str
    exclude: str
    exclude_dependencies: bool
    json: bool
    json_tree: bool
    mermaid: bool
    output_format: str | None
    depth: float
    encoding: str
    license: bool


class _Formatter(ArgumentDefaultsHelpFormatter):
    def __init__(self, prog: str) -> None:
        super().__init__(prog, max_help_position=22, width=240)


def build_parser() -> ArgumentParser:
    parser = ArgumentParser(description="Dependency tree of the installed python packages", formatter_class=_Formatter)
    parser.add_argument("-v", "--version", action="version", version=f"{__version__}")
    parser.add_argument(
        "-w",
        "--warn",
        dest="warn",
        type=str,
        choices=["silence", "suppress", "fail"],
        default="suppress",
        help=(
            "warning control: suppress will show warnings but return 0 whether or not they are present; silence will "
            "not show warnings at all and  always return 0; fail will show warnings and  return 1 if any are present"
        ),
    )

    select = parser.add_argument_group(title="select", description="choose what to render")
    select.add_argument(
        "--python",
        default=sys.executable,
        help=(
            'Python interpreter to inspect. With "auto", it attempts to detect your virtual environment and fails if'
            " it can't."
        ),
    )
    select.add_argument(
        "--path",
        help="Passes a path used to restrict where packages should be looked for (can be used multiple times)",
        action="append",
    )
    select.add_argument(
        "-p",
        "--packages",
        help="comma separated list of packages to show - wildcards are supported, like 'somepackage.*'",
        metavar="P",
    )
    select.add_argument(
        "-e",
        "--exclude",
        help="comma separated list of packages to not show - wildcards are supported, like 'somepackage.*'. "
        "(cannot combine with -p or -a)",
        metavar="P",
    )
    select.add_argument(
        "--exclude-dependencies",
        help="Used along with --exclude to also exclude dependencies of packages",
        action="store_true",
    )

    scope = select.add_mutually_exclusive_group()
    scope.add_argument(
        "-l",
        "--local-only",
        action="store_true",
        help="if in a virtualenv that has global access do not show globally installed packages",
    )
    scope.add_argument("-u", "--user-only", action="store_true", help="only show installations in the user site dir")

    render = parser.add_argument_group(
        title="render",
        description="choose how to render the dependency tree (by default will use text mode)",
    )
    render.add_argument("-f", "--freeze", action="store_true", help="print names so as to write freeze files")
    render.add_argument(
        "--encoding",
        dest="encoding",
        default=sys.stdout.encoding,
        help="the encoding to use when writing to the output",
        metavar="E",
    )
    render.add_argument(
        "-a", "--all", action="store_true", help="list all deps at top level (text and freeze render only)"
    )
    render.add_argument(
        "-d",
        "--depth",
        type=lambda x: int(x) if x.isdigit() and (int(x) >= 0) else parser.error("Depth must be a number that is >= 0"),
        default=float("inf"),
        help="limit the depth of the tree (text and freeze render only)",
        metavar="D",
    )
    render.add_argument(
        "-r",
        "--reverse",
        action="store_true",
        default=False,
        help=(
            "render the dependency tree in the reverse fashion ie. the sub-dependencies are listed with the list of "
            "packages that need them under them"
        ),
    )
    render.add_argument(
        "--license",
        action="store_true",
        help="list the license(s) of a package (text render only)",
    )

    render_type = render.add_mutually_exclusive_group()
    render_type.add_argument(
        "-j",
        "--json",
        action="store_true",
        default=False,
        help="raw JSON - this will yield output that may be used by external tools",
    )
    render_type.add_argument(
        "--json-tree",
        action="store_true",
        default=False,
        help="nested JSON - mimics the text format layout",
    )
    render_type.add_argument(
        "--mermaid",
        action="store_true",
        default=False,
        help="https://mermaid.js.org flow diagram",
    )
    render_type.add_argument(
        "--graph-output",
        metavar="FMT",
        dest="output_format",
        help="Graphviz rendering with the value being the graphviz output e.g.: dot, jpeg, pdf, png, svg",
    )
    return parser


def get_options(args: Sequence[str] | None) -> Options:
    parser = build_parser()
    parsed_args = parser.parse_args(args)

    if parsed_args.exclude_dependencies and not parsed_args.exclude:
        return parser.error("must use --exclude-dependencies with --exclude")
    if parsed_args.license and parsed_args.freeze:
        return parser.error("cannot use --license with --freeze")
    if parsed_args.path and (parsed_args.local_only or parsed_args.user_only):
        return parser.error("cannot use --path with --user-only or --local-only")

    return cast("Options", parsed_args)


__all__ = [
    "Options",
    "get_options",
]
