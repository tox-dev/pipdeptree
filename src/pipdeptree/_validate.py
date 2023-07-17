from __future__ import annotations

import sys
from collections import defaultdict
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ._cli import Options
    from ._models import DistPackage, PackageDAG, ReqPackage


def validate(args: Options, is_text_output: bool, tree: PackageDAG) -> int:  # noqa: FBT001
    # Before any reversing or filtering, show warnings to console, about possibly conflicting or cyclic deps if found
    # and warnings are enabled (i.e. only if output is to be printed to console)
    if is_text_output and args.warn != "silence":
        conflicts = conflicting_deps(tree)
        if conflicts:
            render_conflicts_text(conflicts)
            print("-" * 72, file=sys.stderr)  # noqa: T201

        cycles = cyclic_deps(tree)
        if cycles:
            render_cycles_text(cycles)
            print("-" * 72, file=sys.stderr)  # noqa: T201

        if args.warn == "fail" and (conflicts or cycles):
            return 1
    return 0


def conflicting_deps(tree: PackageDAG) -> dict[DistPackage, list[ReqPackage]]:
    """
    Returns dependencies which are not present or conflict with the requirements of other packages.

    e.g. will warn if pkg1 requires pkg2==2.0 and pkg2==1.0 is installed

    :param tree: the requirements tree (dict)
    :returns: dict of DistPackage -> list of unsatisfied/unknown ReqPackage
    :rtype: dict
    """
    conflicting = defaultdict(list)
    for package, requires in tree.items():
        for req in requires:
            if req.is_conflicting():
                conflicting[package].append(req)  # noqa: PERF401
    return conflicting


def render_conflicts_text(conflicts: dict[DistPackage, list[ReqPackage]]) -> None:
    if conflicts:
        print("Warning!!! Possibly conflicting dependencies found:", file=sys.stderr)  # noqa: T201
        # Enforce alphabetical order when listing conflicts
        pkgs = sorted(conflicts.keys())
        for p in pkgs:
            pkg = p.render_as_root(frozen=False)
            print(f"* {pkg}", file=sys.stderr)  # noqa: T201
            for req in conflicts[p]:
                req_str = req.render_as_branch(frozen=False)
                print(f" - {req_str}", file=sys.stderr)  # noqa: T201


def cyclic_deps(tree: PackageDAG) -> list[tuple[DistPackage, ReqPackage, ReqPackage]]:
    """
    Return cyclic dependencies as list of tuples.

    :param  tree: package tree/dag
    :returns: list of tuples representing cyclic dependencies

    """
    index = {p.key: {r.key for r in rs} for p, rs in tree.items()}
    cyclic: list[tuple[DistPackage, ReqPackage, ReqPackage]] = []
    for p, rs in tree.items():
        for r in rs:
            if p.key in index.get(r.key, []):
                val = tree.get_node_as_parent(r.key)
                if val is not None:
                    entry = tree.get(val)
                    if entry is not None:
                        p_as_dep_of_r = next(x for x in entry if x.key == p.key)
                        cyclic.append((p, r, p_as_dep_of_r))
    return cyclic


def render_cycles_text(cycles: list[tuple[DistPackage, ReqPackage, ReqPackage]]) -> None:
    if cycles:
        print("Warning!! Cyclic dependencies found:", file=sys.stderr)  # noqa: T201
        # List in alphabetical order of the dependency that's cycling
        # (2nd item in the tuple)
        cycles = sorted(cycles, key=lambda xs: xs[1].key)
        for a, b, c in cycles:
            print(f"* {a.project_name} => {b.project_name} => {c.project_name}", file=sys.stderr)  # noqa: T201


__all__ = [
    "validate",
]
