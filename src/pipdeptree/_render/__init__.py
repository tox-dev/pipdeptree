from __future__ import annotations

from typing import TYPE_CHECKING

from .graphviz import render_graphviz
from .json import render_json
from .json_tree import render_json_tree
from .mermaid import render_mermaid
from .text import render_text

if TYPE_CHECKING:
    from pipdeptree._cli import Options


def render(options: Options, tree: PackageDAG) -> None:  # noqa: F821
    if options.json:
        print(render_json(tree))  # noqa: T201
    elif options.json_tree:
        print(render_json_tree(tree))  # noqa: T201
    elif options.mermaid:
        print(render_mermaid(tree))  # noqa: T201
    elif options.output_format:
        render_graphviz(tree, output_format=options.graph_output, reverse=options.reverse)
    else:
        render_text(tree, options.depth, options.encoding_type, options.all, options.freeze)


__all__ = [
    "render",
]
