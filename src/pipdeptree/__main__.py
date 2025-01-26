"""The main entry point used for CLI."""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING

from pipdeptree._cli import get_options
from pipdeptree._detect_env import detect_active_interpreter
from pipdeptree._discovery import get_installed_distributions
from pipdeptree._models import PackageDAG
from pipdeptree._render import render
from pipdeptree._validate import validate
from pipdeptree._warning import WarningPrinter, WarningType, get_warning_printer

if TYPE_CHECKING:
    from collections.abc import Sequence


def main(args: Sequence[str] | None = None) -> int | None:
    """CLI - The main function called as entry point."""
    options = get_options(args)

    # Warnings are only enabled when using text output.
    is_text_output = not any([options.json, options.json_tree, options.output_format])
    if not is_text_output:
        options.warn = WarningType.SILENCE
    warning_printer = get_warning_printer()
    warning_printer.warning_type = options.warn

    if options.python == "auto":
        resolved_path = detect_active_interpreter()
        options.python = resolved_path
        print(f"(resolved python: {resolved_path})", file=sys.stderr)  # noqa: T201

    pkgs = get_installed_distributions(
        interpreter=options.python,
        supplied_paths=options.path or None,
        local_only=options.local_only,
        user_only=options.user_only,
    )
    tree = PackageDAG.from_pkgs(pkgs)

    validate(tree)

    # Reverse the tree (if applicable) before filtering, thus ensuring, that the filter will be applied on ReverseTree
    if options.reverse:
        tree = tree.reverse()

    show_only = options.packages.split(",") if options.packages else None
    exclude = set(options.exclude.split(",")) if options.exclude else None

    if show_only is not None or exclude is not None:
        try:
            tree = tree.filter_nodes(show_only, exclude)
        except ValueError as e:
            if warning_printer.should_warn():
                warning_printer.print_single_line(str(e))
            return _determine_return_code(warning_printer)

    render(options, tree)

    return _determine_return_code(warning_printer)


def _determine_return_code(warning_printer: WarningPrinter) -> int:
    return 1 if warning_printer.has_warned_with_failure() else 0


if __name__ == "__main__":
    sys.exit(main())
