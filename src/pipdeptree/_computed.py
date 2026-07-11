from __future__ import annotations

import pathlib
from dataclasses import dataclass
from dataclasses import field as dataclass_field
from functools import cached_property
from importlib.metadata import distribution
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Sequence

    from pipdeptree._models import PackageDAG


@dataclass
class ComputedValues:
    key: str
    tree: PackageDAG
    full_tree: PackageDAG | None = None
    _size_cache: dict[str, int | None] | None = dataclass_field(default=None, repr=False, compare=False, kw_only=True)

    def as_dict(self, fields: Sequence[str]) -> dict[str, Any]:
        return {
            (attr := field.replace("-", "_")): getattr(self, attr)
            for field in fields
            if hasattr(self, field.replace("-", "_"))
        }

    def format_display(self, fields: Sequence[str], exclude: frozenset[str] = frozenset()) -> list[str]:
        result: list[str] = []
        for field in fields:
            if field in exclude:
                continue
            if field == "size":
                result.append(self.size)
            elif field == "size-raw":
                result.append(str(self.size_raw))
            elif field == "unique-deps-count" and self.unique_deps_count:
                result.append(f"{self.unique_deps_count} unique deps")
            elif field == "unique-deps-names" and self.unique_deps_names:
                result.append(f"unique: {' | '.join(self.unique_deps_names)}")
            elif field == "unique-deps-size" and self.unique_deps_size != "0 B":
                result.append(f"unique size: {self.unique_deps_size}")
        return result

    @cached_property
    def size(self) -> str:
        return self.format_size(self.size_bytes) if self.size_bytes is not None else "0 B"

    @cached_property
    def size_raw(self) -> int:
        return self.size_bytes or 0

    @cached_property
    def size_bytes(self) -> int | None:
        size_cache = self._size_cache
        if size_cache is not None and self.key in size_cache:
            return size_cache[self.key]
        dist = distribution(self.key)
        if record := dist.read_text("RECORD"):
            from csv import reader  # noqa: PLC0415  # Other computed fields do not read package file lists.

            files = (row[0] for row in reader(record.splitlines()))
        else:
            files = dist.files
        result = sum(self._file_size(str(dist.locate_file(f))) for f in files) if files else None
        if size_cache is not None:
            size_cache[self.key] = result
        return result

    @staticmethod
    def _file_size(path: str) -> int:
        try:
            return pathlib.Path(path).stat().st_size
        except OSError:
            return 0

    @staticmethod
    def format_size(size_bytes: int) -> str:
        for unit in ("B", "KB", "MB", "GB"):
            if size_bytes < 1024 or unit == "GB":
                return f"{size_bytes:.1f} {unit}" if unit != "B" else f"{size_bytes} B"
            size_bytes /= 1024  # ty: ignore[invalid-assignment]
        return f"{size_bytes:.1f} GB"  # pragma: no cover

    @cached_property
    def unique_deps_count(self) -> int:
        return len(self.unique_deps)

    @cached_property
    def unique_deps_names(self) -> list[str]:
        return sorted(self.unique_deps)

    @cached_property
    def unique_deps_size(self) -> str:
        size_cache = self._size_cache if self._size_cache is not None else {}
        total = sum(
            ComputedValues(dep, self.tree, self.full_tree, _size_cache=size_cache).size_raw for dep in self.unique_deps
        )
        return self.format_size(total)

    @cached_property
    def unique_deps(self) -> set[str]:
        tree = self.full_tree or self.tree
        removed = {self.key}
        parent_counts: dict[str, int] = {}
        for dependencies in tree.values():
            for dependency in dependencies:
                parent_counts[dependency.key] = parent_counts.get(dependency.key, 0) + 1

        stack = [self.key]
        while stack:
            for dependency in tree.get_children(stack.pop()):
                parent_counts[dependency.key] -= 1
                if parent_counts[dependency.key] == 0 and dependency.key not in removed:
                    removed.add(dependency.key)
                    stack.append(dependency.key)
        return removed - {self.key}


__all__ = [
    "ComputedValues",
]
