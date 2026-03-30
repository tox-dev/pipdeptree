from __future__ import annotations

import re
import sys
from typing import TYPE_CHECKING

from pipdeptree._models.package import DistPackage, ReqPackage
from pipdeptree._render.text import _build_suffix, get_top_level_nodes

if TYPE_CHECKING:
    from rich.tree import Tree

    from pipdeptree._cli import RenderContext
    from pipdeptree._models import PackageDAG


def render_rich_text(
    tree: PackageDAG,
    *,
    max_depth: float,
    list_all: bool = True,
    context: RenderContext | None = None,
) -> None:
    """
    Print tree using Rich library for enhanced terminal output.

    :param tree: the package tree
    :param max_depth: the maximum depth of the dependency tree
    :param list_all: whether to list all the pkgs at the root level or only those that are the sub-dependencies
    :param context: metadata and computed fields to display
    :returns: None
    """
    try:
        from rich.console import Console  # noqa: PLC0415
        from rich.tree import Tree  # noqa: PLC0415
    except ImportError as exc:
        print(  # noqa: T201
            "rich is not available, but necessary for the output option. Please install it.",
            file=sys.stderr,
        )
        raise SystemExit(1) from exc

    nodes = get_top_level_nodes(tree, list_all=list_all)
    console = Console()

    for node in nodes:
        root_label = _format_node(node, parent=None, context=context, tree=tree)
        rich_tree = Tree(root_label, guide_style="bold bright_blue")
        _build_tree(tree, node, rich_tree, max_depth=max_depth, depth=0, cur_chain=[], context=context)
        console.print(rich_tree)


def _build_tree(  # noqa: PLR0913
    tree: PackageDAG,
    node: DistPackage | ReqPackage,
    rich_tree: Tree,
    *,
    max_depth: float,
    depth: int,
    cur_chain: list[str],
    context: RenderContext | None,
) -> None:
    """
    Recursively build the rich tree structure.

    :param tree: the package tree
    :param node: current node
    :param rich_tree: the rich Tree object to add children to
    :param max_depth: maximum depth
    :param depth: current depth
    :param cur_chain: chain of package names to detect cycles
    :param context: metadata and computed fields to display
    """
    if depth >= max_depth:
        return

    children = tree.get_children(node.key)
    for child in children:
        if child.project_name in cur_chain:
            continue

        child_label = _format_node(child, parent=node, context=context, tree=tree)
        child_tree = rich_tree.add(child_label)

        _build_tree(
            tree,
            child,
            child_tree,
            max_depth=max_depth,
            depth=depth + 1,
            cur_chain=[*cur_chain, child.project_name],
            context=context,
        )


def _format_node(
    node: DistPackage | ReqPackage,
    parent: DistPackage | ReqPackage | None,
    *,
    context: RenderContext | None,
    tree: PackageDAG,
) -> str:
    """
    Format a node for display with rich styling.

    :param node: the node to format
    :param parent: the parent node (if any)
    :param context: metadata and computed fields to display
    :param tree: the package tree (needed for computed fields)
    :return: formatted string with rich markup
    """
    node_str = node.render(parent, frozen=False)

    suffix = ""
    if context and context.active:
        suffix = _build_suffix(node, context, tree)

    if parent is None:
        return _format_root_node(node_str, suffix)
    return _format_branch_node(node_str, node, suffix)


def _format_root_node(node_str: str, suffix: str = "") -> str:
    """Format a root node (package at top level)."""
    match = re.match(r"^(.+?)==(.+?)$", node_str)
    assert match, f"Unexpected root node format: {node_str}"
    name, version = match.groups()
    suffix_str = f" [dim blue]{suffix.strip()}[/dim blue]" if suffix else ""
    return f"[bold cyan]{name}[/bold cyan][dim]==[/dim][bold green]{version}[/bold green]{suffix_str}"


def _format_branch_node(node_str: str, node: DistPackage | ReqPackage, suffix: str = "") -> str:
    """Format a branch node (dependency)."""
    suffix_str = f" [dim blue]{suffix.strip()}[/dim blue]" if suffix else ""
    if isinstance(node, ReqPackage) and (
        match := re.match(
            r"""
            ^(.+?)                          # package name (non-greedy)
            \s+\[                           # opening bracket
            required:\s*(.+?)               # required version spec (supports multi-spec like >=1.0,<2.0)
            ,\s+installed:\s*(.+?)          # installed version
            (?:,\s+extra:\s*(.+?))?         # optional extra name
            \]$                             # closing bracket
            """,
            node_str,
            re.VERBOSE,
        )
    ):
        name, required, installed, extra = match.groups()
        status_icon = _get_status_icon(node)
        extra_str = f" [magenta]\\[extra: {extra}][/magenta]" if extra else ""
        return (
            f"{status_icon} [bold cyan]{name}[/bold cyan] "
            f"[dim]required:[/dim] [yellow]{required}[/yellow] "
            f"[dim]installed:[/dim] {_format_version(installed, node)}{extra_str}{suffix_str}"
        )

    match = re.match(r"^(.+?)==(.+?)\s+\[requires:\s*(.+?)\]$", node_str)
    assert match, f"Unexpected branch node format: {node_str}"
    pkg_name, pkg_version, requires = match.groups()
    return (
        f"[bold cyan]{pkg_name}[/bold cyan][dim]==[/dim][bold green]{pkg_version}[/bold green] "
        f"[dim]\\[requires:[/dim] [yellow]{requires}[/yellow][dim]][/dim]{suffix_str}"
    )


def _get_status_icon(node: ReqPackage) -> str:
    """Get a status icon for a requirement package."""
    if node.is_missing:
        return "[bold red]✗[/bold red]"
    if node.is_conflicting():
        return "[bold yellow]⚠[/bold yellow]"
    return "[bold green]✓[/bold green]"


def _format_version(version: str, node: ReqPackage) -> str:
    """Format version with appropriate color based on status."""
    if node.is_missing:
        return f"[bold red]{version}[/bold red]"
    if node.is_conflicting():
        return f"[bold yellow]{version}[/bold yellow]"
    return f"[bold green]{version}[/bold green]"


__all__ = ["render_rich_text"]
