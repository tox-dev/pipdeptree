from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pipdeptree._cli import Options
    from pipdeptree._models import PackageDAG
    from pipdeptree._models.package import RenderMode


def render(options: Options, tree: PackageDAG) -> None:
    output_format = options.output_format
    # from-index/from-lock build a tree from resolved data: one version per package and no per-edge
    # range, so edges show "[candidate: <version>]" instead of "[required:, installed:]".
    mode: RenderMode = "resolved" if options.command in {"from-index", "from-lock"} else "default"
    # --summary reduces the tree to an aggregate report; output_format then only selects its presentation style.
    if options.summary:
        from .summary import render_summary  # noqa: PLC0415  # Load only the selected renderer.

        render_summary(tree, mode=mode, style=output_format)
    elif output_format == "json":
        from .json import render_json  # noqa: PLC0415  # Load only the selected renderer.

        render_json(tree, context=options.context, mode=mode)
    elif output_format == "json-tree":
        from .json_tree import render_json_tree  # noqa: PLC0415  # Load only the selected renderer.

        render_json_tree(tree, context=options.context, mode=mode)
    elif output_format == "mermaid":
        from .mermaid import render_mermaid  # noqa: PLC0415  # Load only the selected renderer.

        render_mermaid(tree, context=options.context)
    elif output_format == "freeze":
        from .freeze import render_freeze  # noqa: PLC0415  # Load only the selected renderer.

        render_freeze(tree, max_depth=options.depth, list_all=options.all)
    elif output_format == "rich":
        from .rich_text import render_rich_text  # noqa: PLC0415  # Load only the selected renderer.

        render_rich_text(tree, max_depth=options.depth, list_all=options.all, context=options.context, mode=mode)
    elif output_format.startswith("graphviz-"):
        from .graphviz import render_graphviz  # noqa: PLC0415  # Graphviz is optional.

        render_graphviz(
            tree,
            output_format=output_format[len("graphviz-") :],
            reverse=options.reverse,
            max_depth=options.depth,
            context=options.context,
        )
    else:
        from .text import render_text  # noqa: PLC0415  # Load only the selected renderer.

        render_text(
            tree,
            max_depth=options.depth,
            encoding=options.encoding,
            list_all=options.all,
            context=options.context,
            mode=mode,
        )


__all__ = [
    "render",
]
