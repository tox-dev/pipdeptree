from __future__ import annotations

from typing import TYPE_CHECKING

from .graphviz import dump_graphviz, print_graphviz
from .json import render_json
from .json_tree import render_json_tree
from .mermaid import render_mermaid
from .text import render_text

if TYPE_CHECKING:
    from pipdeptree._cli import Options


def render(options: Options, tree: PackageDAG) -> None:  # noqa: F821
    if options.json:
        print(render_json(tree, indent=4))  # noqa: T201
    elif options.json_tree:
        print(render_json_tree(tree, indent=4))  # noqa: T201
    elif options.mermaid:
        print(render_mermaid(tree))  # noqa: T201
    elif options.output_format:
        output = dump_graphviz(tree, output_format=options.output_format, is_reverse=options.reverse)
        print_graphviz(output)
    else:
        render_text(tree, options.depth, options.encoding_type, options.all, options.freeze)


__all__ = [
    "render",
]
