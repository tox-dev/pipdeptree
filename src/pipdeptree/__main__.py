from __future__ import annotations

import sys
from typing import Sequence

from pipdeptree._cli import get_options
from pipdeptree._discovery import get_installed_distributions
from pipdeptree._models import PackageDAG
from pipdeptree._non_host import handle_non_host_target
from pipdeptree._render import render
from pipdeptree._validate import validate


def main(args: Sequence[str] | None = None) -> None | int:
    options = get_options(args)
    result = handle_non_host_target(options)
    if result is not None:
        return result

    pkgs = get_installed_distributions(local_only=options.local_only, user_only=options.user_only)
    tree = PackageDAG.from_pkgs(pkgs)
    is_text_output = not any([options.json, options.json_tree, options.output_format])

    return_code = validate(options, is_text_output, tree)

    # Reverse the tree (if applicable) before filtering, thus ensuring, that the filter will be applied on ReverseTree
    if options.reverse:
        tree = tree.reverse()

    show_only = set(options.packages.split(",")) if options.packages else None
    exclude = set(options.exclude.split(",")) if options.exclude else None

    if show_only is not None or exclude is not None:
        tree = tree.filter_nodes(show_only, exclude)

    render(options, tree)

    return return_code


if __name__ == "__main__":
    sys.exit(main())
