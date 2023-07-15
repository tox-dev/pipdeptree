from __future__ import annotations

import sys

from pipdeptree._cli import get_options
from pipdeptree._discovery import get_installed_distributions
from pipdeptree._models import PackageDAG
from pipdeptree._non_host import handle_non_host_target
from pipdeptree._render import render

from ._validate import validate


def main() -> None | int:
    args = get_options()
    result = handle_non_host_target(args)
    if result is not None:
        return result

    pkgs = get_installed_distributions(local_only=args.local_only, user_only=args.user_only)
    tree = PackageDAG.from_pkgs(pkgs)
    is_text_output = not any([args.json, args.json_tree, args.output_format])

    return_code = validate(args, is_text_output, tree)

    # Reverse the tree (if applicable) before filtering, thus ensuring, that the filter will be applied on ReverseTree
    if args.reverse:
        tree = tree.reverse()

    show_only = set(args.packages.split(",")) if args.packages else None
    exclude = set(args.exclude.split(",")) if args.exclude else None

    if show_only is not None or exclude is not None:
        tree = tree.filter_nodes(show_only, exclude)

    render(args, tree)

    return return_code


if __name__ == "__main__":
    sys.exit(main())
