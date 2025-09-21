from __future__ import annotations

from typing import TYPE_CHECKING

from .freeze import render_freeze
from .graphviz import render_graphviz
from .json import render_json
from .json_tree import render_json_tree
from .mermaid import render_mermaid
from .text import render_text

if TYPE_CHECKING:
    from pipdeptree._cli import Options
    from pipdeptree._models import PackageDAG


def render(options: Options, tree: PackageDAG) -> None:
    if options.json:
        render_json(tree)
    elif options.json_tree:
        render_json_tree(tree)
    elif options.mermaid:
        render_mermaid(tree)
    elif options.output_format:
        render_graphviz(tree, output_format=options.output_format, reverse=options.reverse)
    elif options.freeze:
        render_freeze(tree, max_depth=options.depth, list_all=options.all)
    else:
        render_text(
            tree,
            max_depth=options.depth,
            encoding=options.encoding,
            list_all=options.all,
            include_license=options.license,
        )


__all__ = [
    "render",
]
