from __future__ import annotations

import sys
import warnings
from argparse import ArgumentDefaultsHelpFormatter, ArgumentParser, ArgumentTypeError, Namespace
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, cast

from .version import __version__

if TYPE_CHECKING:
    from collections.abc import Sequence

    from pipdeptree._models import PackageDAG


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
    graphviz_format: str | None
    output_format: str
    extras: bool
    depth: float
    encoding: str
    license: bool
    metadata: list[str]
    computed: list[str]
    context: RenderContext


@dataclass
class RenderContext:
    """Bundles metadata and computed fields that augment package display."""

    metadata: list[str] = field(default_factory=list)
    computed: list[str] = field(default_factory=list)
    full_tree: PackageDAG | None = field(default=None, repr=False, compare=False)

    @property
    def active(self) -> bool:
        return bool(self.metadata or self.computed)


# NOTE: graphviz-* has been intentionally left out. Users of this var should handle it separately.
ALLOWED_RENDER_FORMATS = ["freeze", "json", "json-tree", "mermaid", "rich", "text"]
ALLOWED_COMPUTED_FIELDS = frozenset({"size", "size-raw", "unique-deps-count", "unique-deps-names", "unique-deps-size"})


class _Formatter(ArgumentDefaultsHelpFormatter):
    def __init__(self, prog: str) -> None:
        super().__init__(prog, max_help_position=22, width=240)


def build_parser() -> ArgumentParser:
    parser = ArgumentParser(
        prog="pipdeptree", description="Dependency tree of the installed python packages", formatter_class=_Formatter
    )
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
        help="passes a path used to restrict where packages should be looked for (can be used multiple times)",
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
        help="used along with --exclude to also exclude dependencies of packages",
        action="store_true",
    )
    select.add_argument(
        "-x",
        "--extras",
        action="store_true",
        default=False,
        help="include optional (extras) dependencies in the tree",
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
        description="choose how to render the dependency tree",
    )
    render.add_argument(
        "-f", "--freeze", action="store_true", help="(Deprecated, use -o) print names so as to write freeze files"
    )
    render.add_argument(
        "--encoding",
        dest="encoding",
        default=sys.stdout.encoding,
        help="the encoding to use when writing to the output",
        metavar="E",
    )
    render.add_argument(
        "-a", "--all", action="store_true", help="list all deps at top level (text, rich, and freeze render only)"
    )
    render.add_argument(
        "-d",
        "--depth",
        type=lambda x: int(x) if x.isdigit() and (int(x) >= 0) else parser.error("Depth must be a number that is >= 0"),
        default=float("inf"),
        help="limit the depth of the tree (text, rich, freeze, and graphviz render only)",
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
        help="(Deprecated, use --metadata license) list the license(s) of a package",
    )
    render.add_argument(
        "-m",
        "--metadata",
        default="",
        help="comma separated list of metadata fields to display from the package METADATA file"
        " (e.g. license,summary,author,home-page,requires-python)",
        metavar="M",
    )
    render.add_argument(
        "-c",
        "--computed",
        default="",
        help=f"comma separated list of computed fields to display: {', '.join(sorted(ALLOWED_COMPUTED_FIELDS))}",
        metavar="C",
    )

    render_type = render.add_mutually_exclusive_group()
    render_type.add_argument(
        "-j",
        "--json",
        action="store_true",
        default=False,
        help="(Deprecated, use -o) raw JSON - this will yield output that may be used by external tools",
    )
    render_type.add_argument(
        "--json-tree",
        action="store_true",
        default=False,
        help="(Deprecated, use -o) nested JSON - mimics the text format layout",
    )
    render_type.add_argument(
        "--mermaid",
        action="store_true",
        default=False,
        help="(Deprecated, use -o) https://mermaid.js.org flow diagram",
    )
    render_type.add_argument(
        "--graph-output",
        metavar="FMT",
        dest="graphviz_format",
        help="(Deprecated, use -o) Graphviz rendering with the value being the graphviz output e.g.:\
              dot, jpeg, pdf, png, svg",
    )
    render_type.add_argument(
        "-o",
        "--output",
        metavar="FMT",
        dest="output_format",
        type=_validate_output_format,
        default="text",
        help=f"specify how to render the tree; supported formats: {', '.join(ALLOWED_RENDER_FORMATS)}, or graphviz-*\
            (e.g. graphviz-png, graphviz-dot)",
    )
    return parser


def get_options(args: Sequence[str] | None) -> Options:
    parser = build_parser()
    parsed_args = parser.parse_args(args)
    options = cast("Options", parsed_args)

    options.output_format = _handle_legacy_render_options(options)
    raw_metadata: str = cast("str", options.metadata)
    raw_computed: str = cast("str", options.computed)
    options.metadata = [f.strip() for f in raw_metadata.split(",") if f.strip()] if raw_metadata else []
    options.computed = [f.strip() for f in raw_computed.split(",") if f.strip()] if raw_computed else []

    if options.license:
        if "license" in options.metadata:
            return parser.error("cannot use --license with --metadata license")
        warnings.warn("--license is deprecated, use --metadata license instead", DeprecationWarning, stacklevel=1)
        options.metadata = ["license", *options.metadata]

    if invalid := set(options.computed) - ALLOWED_COMPUTED_FIELDS:
        allowed = ", ".join(sorted(ALLOWED_COMPUTED_FIELDS))
        return parser.error(f"invalid --computed values: {', '.join(sorted(invalid))}. Allowed: {allowed}")

    options.context = RenderContext(metadata=options.metadata, computed=options.computed)

    if options.exclude_dependencies and not options.exclude:
        return parser.error("must use --exclude-dependencies with --exclude")
    if options.path and (options.local_only or options.user_only):
        return parser.error("cannot use --path with --user-only or --local-only")

    return options


def _handle_legacy_render_options(options: Options) -> str:
    if options.freeze:
        return "freeze"
    if options.json:
        return "json"
    if options.json_tree:
        return "json-tree"
    if options.mermaid:
        return "mermaid"
    if options.graphviz_format:
        return f"graphviz-{options.graphviz_format}"

    return options.output_format


def _validate_output_format(value: str) -> str:
    if value in ALLOWED_RENDER_FORMATS:
        return value
    if value.startswith("graphviz-"):
        return value
    msg = f'"{value}" is not a known output format. Must be one of {", ".join(ALLOWED_RENDER_FORMATS)}, or graphviz-*'
    raise ArgumentTypeError(msg)


__all__ = [
    "Options",
    "get_options",
]
