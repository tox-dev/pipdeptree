from __future__ import annotations

import pathlib
from importlib.metadata import PackageNotFoundError, distribution
from importlib.metadata import metadata as get_pkg_metadata
from typing import TYPE_CHECKING, TypedDict

if TYPE_CHECKING:
    from collections.abc import Sequence

    from pipdeptree._cli import RenderContext
    from pipdeptree._models import PackageDAG


class ComputedValues(TypedDict, total=False):
    size: str
    size_raw: int
    unique_deps_count: int
    unique_deps_names: list[str]
    unique_deps_size: str


def build_node_extra_label(key: str, context: RenderContext | None, tree: PackageDAG, separator: str) -> str:
    if not context or not context.active:
        return ""
    parts: list[str] = []
    if context.metadata:
        parts.extend(get_metadata_label_parts(key, context.metadata, tree))
    if context.computed:
        for field_key, field_value in get_computed_values(key, context.computed, tree, context.full_tree).items():
            parts.append(f"{field_key}: {field_value}")
    return separator.join(parts)


def get_metadata_label_parts(key: str, fields: Sequence[str], tree: PackageDAG) -> list[str]:
    parts: list[str] = []
    for field in fields:
        if field == "license":
            for pkg in tree:
                if pkg.key == key:
                    parts.append(pkg.licenses().strip("()"))
                    break
            continue
        try:
            dist_metadata = get_pkg_metadata(key)
            if value := dist_metadata[field]:
                parts.append(str(value))
        except PackageNotFoundError:
            pass
    return parts


def format_computed_display(
    key: str, fields: Sequence[str], tree: PackageDAG, full_tree: PackageDAG | None = None
) -> list[str]:
    values = get_computed_values(key, fields, tree, full_tree)
    result: list[str] = []
    for field in fields:
        if field == "size" and "size" in values:
            result.append(str(values["size"]))
        elif field == "size-raw" and "size_raw" in values:
            result.append(str(values["size_raw"]))
        elif field == "unique-deps-count" and "unique_deps_count" in values and values["unique_deps_count"]:
            result.append(f"{values['unique_deps_count']} unique deps")
        elif field == "unique-deps-names" and "unique_deps_names" in values and values["unique_deps_names"]:
            result.append(f"unique: {', '.join(values['unique_deps_names'])}")
        elif field == "unique-deps-size" and "unique_deps_size" in values and values["unique_deps_size"] != "0 B":
            result.append(f"unique size: {values['unique_deps_size']}")
    return result


def get_computed_values(
    key: str, fields: Sequence[str], tree: PackageDAG, full_tree: PackageDAG | None = None
) -> ComputedValues:
    result: ComputedValues = {}
    size_bytes: int | None = None
    if {"size", "size-raw"} & set(fields):
        size_bytes = compute_installed_size_bytes(key)
    unique: set[str] | None = None
    if {"unique-deps-count", "unique-deps-names", "unique-deps-size"} & set(fields):
        unique = compute_unique_deps(key, full_tree or tree)
    for field in fields:
        if field == "size":
            result["size"] = _format_size(size_bytes) if size_bytes is not None else "0 B"
        elif field == "size-raw":
            result["size_raw"] = size_bytes or 0
        elif field == "unique-deps-count" and unique is not None:
            result["unique_deps_count"] = len(unique)
        elif field == "unique-deps-names" and unique is not None:
            result["unique_deps_names"] = sorted(unique)
        elif field == "unique-deps-size" and unique is not None:
            total = sum(compute_installed_size_bytes(dep) or 0 for dep in unique)
            result["unique_deps_size"] = _format_size(total)
    return result


def compute_installed_size_bytes(key: str) -> int | None:
    dist = distribution(key)
    if not (files := dist.files):
        return None
    return sum(_file_size(str(dist.locate_file(file_entry))) for file_entry in files)


def _file_size(path: str) -> int:
    try:
        return pathlib.Path(path).stat().st_size
    except OSError:
        return 0


def _format_size(size_bytes: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if size_bytes < 1024 or unit == "GB":
            return f"{size_bytes:.1f} {unit}" if unit != "B" else f"{size_bytes} B"
        size_bytes /= 1024  # ty: ignore[invalid-assignment]
    return f"{size_bytes:.1f} GB"  # pragma: no cover


def compute_unique_deps(key: str, tree: PackageDAG) -> set[str]:
    own_deps = _transitive_deps(key, tree)
    removed = {key}
    changed = True
    while changed:
        changed = False
        reachable: set[str] = set()
        for pkg in tree:
            if pkg.key not in removed:
                reachable |= _transitive_deps(pkg.key, tree, exclude=removed)
        newly_orphaned = own_deps - reachable - removed
        if newly_orphaned:
            removed |= newly_orphaned
            changed = True
    return removed - {key}


def _transitive_deps(key: str, tree: PackageDAG, exclude: set[str] | None = None) -> set[str]:
    result: set[str] = set()
    excluded = exclude or set()
    stack = [c.key for c in tree.get_children(key) if c.key not in excluded]
    while stack:
        if (dep := stack.pop()) not in result:
            result.add(dep)
            stack.extend(c.key for c in tree.get_children(dep) if c.key not in excluded)
    return result


__all__ = [
    "ComputedValues",
    "build_node_extra_label",
    "compute_installed_size_bytes",
    "compute_unique_deps",
    "format_computed_display",
    "get_computed_values",
    "get_metadata_label_parts",
]
