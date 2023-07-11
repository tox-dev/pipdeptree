from __future__ import annotations

import fnmatch
import inspect
import json
import os
import shutil
import subprocess
import sys
import tempfile
from abc import ABC, abstractmethod
from argparse import ArgumentParser, Namespace
from collections import defaultdict, deque
from importlib import import_module
from itertools import chain
from pathlib import Path
from textwrap import dedent
from typing import TYPE_CHECKING, Any, Iterator, List, Mapping, cast

from pip._vendor.pkg_resources import Distribution, Requirement

from .version import version as __version__

try:
    from pip._internal.operations.freeze import FrozenRequirement
except ImportError:
    from pip import FrozenRequirement  # type: ignore[attr-defined, no-redef]


if TYPE_CHECKING:
    from typing import Literal

    from pip._internal.metadata import BaseDistribution
    from pip._vendor.pkg_resources import DistInfoDistribution


def sorted_tree(tree: dict[DistPackage, list[ReqPackage]]) -> dict[DistPackage, list[ReqPackage]]:
    """
    Sorts the dict representation of the tree. The root packages as well as the intermediate packages are sorted in the
    alphabetical order of the package names.

    :param tree: the pkg dependency tree obtained by calling `construct_tree` function
    :returns: sorted tree
    """
    return {k: sorted(v) for k, v in sorted(tree.items())}


def guess_version(pkg_key: str, default: str = "?") -> str:
    """
    Guess the version of a pkg when pip doesn't provide it.

    :param pkg_key: key of the package
    :param default: default version to return if unable to find
    :returns: version
    """
    try:
        if sys.version_info >= (3, 8):  # pragma: >=3.8 cover
            import importlib.metadata as importlib_metadata
        else:  # pragma: <3.8 cover
            import importlib_metadata
        return importlib_metadata.version(pkg_key)
    except ImportError:
        pass
    # Avoid AssertionError with setuptools, see https://github.com/tox-dev/pipdeptree/issues/162
    if pkg_key in {"setuptools"}:
        return default
    try:
        m = import_module(pkg_key)
    except ImportError:
        return default
    else:
        v = getattr(m, "__version__", default)
        if inspect.ismodule(v):
            return getattr(v, "__version__", default)
        return v


def frozen_req_from_dist(dist: Distribution) -> FrozenRequirement:
    # The `pip._internal.metadata` modules were introduced in 21.1.1
    # and the `pip._internal.operations.freeze.FrozenRequirement`
    # class now expects dist to be a subclass of
    # `pip._internal.metadata.BaseDistribution`, however the
    # `pip._internal.utils.misc.get_installed_distributions` continues
    # to return objects of type
    # pip._vendor.pkg_resources.DistInfoDistribution.
    #
    # This is a hacky backward compatible (with older versions of pip)
    # fix.
    try:
        from pip._internal import metadata
    except ImportError:
        our_dist: BaseDistribution = dist  # type: ignore[assignment]
    else:
        our_dist = metadata.pkg_resources.Distribution(dist)

    try:
        return FrozenRequirement.from_dist(our_dist)
    except TypeError:
        return FrozenRequirement.from_dist(our_dist, [])  # type: ignore[call-arg]


class Package(ABC):
    """
    Abstract class for wrappers around objects that pip returns. This class needs to be subclassed with implementations
    for `render_as_root` and `render_as_branch` methods.
    """

    def __init__(self, obj: DistInfoDistribution) -> None:
        self._obj: DistInfoDistribution = obj
        self.project_name: str = obj.project_name
        self.key: str = obj.key

    @abstractmethod
    def render_as_root(self, frozen: bool) -> str:  # noqa: FBT001
        raise NotImplementedError

    @abstractmethod
    def render_as_branch(self, frozen: bool) -> str:  # noqa: FBT001
        raise NotImplementedError

    def render(
        self,
        parent: DistPackage | ReqPackage | None = None,
        frozen: bool = False,  # noqa: FBT001, FBT002
    ) -> str:
        if not parent:
            return self.render_as_root(frozen)
        return self.render_as_branch(frozen)

    @staticmethod
    def frozen_repr(obj: DistInfoDistribution) -> str:
        fr = frozen_req_from_dist(obj)
        return str(fr).strip()

    def __getattr__(self, key: str) -> Any:
        return getattr(self._obj, key)

    def __repr__(self) -> str:
        return f'<{self.__class__.__name__}("{self.key}")>'

    def __lt__(self, rhs: Package) -> bool:
        return self.key < rhs.key


class DistPackage(Package):
    """
    Wrapper class for pkg_resources.Distribution instances.

    :param obj: pkg_resources.Distribution to wrap over
    :param req: optional ReqPackage object to associate this DistPackage with. This is useful for displaying the tree
        in reverse
    """

    def __init__(self, obj: DistInfoDistribution, req: ReqPackage | None = None) -> None:
        super().__init__(obj)
        self.version_spec = None
        self.req = req

    def render_as_root(self, frozen: bool) -> str:  # noqa: FBT001
        if not frozen:
            return f"{self.project_name}=={self.version}"
        return self.__class__.frozen_repr(self._obj)

    def render_as_branch(self, frozen: bool) -> str:  # noqa: FBT001
        assert self.req is not None  # noqa: S101
        if not frozen:
            parent_ver_spec = self.req.version_spec
            parent_str = self.req.project_name
            if parent_ver_spec:
                parent_str += parent_ver_spec
            return f"{self.project_name}=={self.version} [requires: {parent_str}]"
        return self.render_as_root(frozen)

    def as_requirement(self) -> ReqPackage:
        """Return a ReqPackage representation of this DistPackage."""
        return ReqPackage(self._obj.as_requirement(), dist=self)  # type: ignore[no-untyped-call]

    def as_parent_of(self, req: ReqPackage | None) -> DistPackage:
        """
        Return a DistPackage instance associated to a requirement. This association is necessary for reversing the
        PackageDAG.

        If `req` is None, and the `req` attribute of the current instance is also None, then the same instance will be
        returned.

        :param ReqPackage req: the requirement to associate with
        :returns: DistPackage instance
        """
        if req is None and self.req is None:
            return self
        return self.__class__(self._obj, req)

    def as_dict(self) -> dict[str, str]:
        return {"key": self.key, "package_name": self.project_name, "installed_version": self.version}


class ReqPackage(Package):
    """
    Wrapper class for Requirements instance.

    :param obj: The `Requirements` instance to wrap over
    :param dist: optional `pkg_resources.Distribution` instance for this requirement
    """

    UNKNOWN_VERSION = "?"

    def __init__(self, obj: Requirement, dist: DistPackage | None = None) -> None:
        super().__init__(obj)
        self.dist = dist

    @property
    def version_spec(self) -> str | None:
        specs = sorted(self._obj.specs, reverse=True)  # `reverse` makes '>' prior to '<'
        return ",".join(["".join(sp) for sp in specs]) if specs else None

    @property
    def installed_version(self) -> str:
        if not self.dist:
            return guess_version(self.key, self.UNKNOWN_VERSION)
        return cast(str, self.dist.version)

    @property
    def is_missing(self) -> bool:
        return self.installed_version == self.UNKNOWN_VERSION

    def is_conflicting(self) -> bool:
        """If installed version conflicts with required version."""
        # unknown installed version is also considered conflicting
        if self.installed_version == self.UNKNOWN_VERSION:
            return True
        ver_spec = self.version_spec if self.version_spec else ""
        req_version_str = f"{self.project_name}{ver_spec}"
        req_obj = Requirement.parse(req_version_str)  # type: ignore[no-untyped-call]
        return self.installed_version not in req_obj

    def render_as_root(self, frozen: bool) -> str:  # noqa: FBT001
        if not frozen:
            return f"{self.project_name}=={self.installed_version}"
        if self.dist:
            return self.__class__.frozen_repr(self.dist._obj)  # noqa: SLF001
        return self.project_name

    def render_as_branch(self, frozen: bool) -> str:  # noqa: FBT001
        if not frozen:
            req_ver = self.version_spec if self.version_spec else "Any"
            return f"{self.project_name} [required: {req_ver}, installed: {self.installed_version}]"
        return self.render_as_root(frozen)

    def as_dict(self) -> dict[str, str | None]:
        return {
            "key": self.key,
            "package_name": self.project_name,
            "installed_version": self.installed_version,
            "required_version": self.version_spec,
        }


class PackageDAG(Mapping[DistPackage, List[ReqPackage]]):
    """
    Representation of Package dependencies as directed acyclic graph using a dict (Mapping) as the underlying
    datastructure.

    The nodes and their relationships (edges) are internally stored using a map as follows,

    {a: [b, c],
     b: [d],
     c: [d, e],
     d: [e],
     e: [],
     f: [b],
     g: [e, f]}

    Here, node `a` has 2 children nodes `b` and `c`. Consider edge direction from `a` -> `b` and `a` -> `c`
    respectively.

    A node is expected to be an instance of a subclass of `Package`. The keys are must be of class `DistPackage` and
    each item in values must be of class `ReqPackage`. (See also ReversedPackageDAG where the key and value types are
    interchanged).
    """

    @classmethod
    def from_pkgs(cls, pkgs: list[DistInfoDistribution]) -> PackageDAG:
        dist_pkgs = [DistPackage(p) for p in pkgs]
        idx = {p.key: p for p in dist_pkgs}
        m: dict[DistPackage, list[ReqPackage]] = {}
        for p in dist_pkgs:
            reqs = []
            for r in p.requires():
                d = idx.get(r.key)
                # pip's _vendor.packaging.requirements.Requirement uses the exact casing of a dependency's name found in
                # a project's build config, which is not ideal when rendering.
                # See https://github.com/tox-dev/pipdeptree/issues/242
                r.project_name = d.project_name if d is not None else r.project_name
                pkg = ReqPackage(r, d)
                reqs.append(pkg)
            m[p] = reqs

        return cls(m)

    def __init__(self, m: dict[DistPackage, list[ReqPackage]]) -> None:
        """
        Initialize the PackageDAG object.

        :param dict m: dict of node objects (refer class docstring)
        :returns: None
        :rtype: NoneType

        """
        self._obj: dict[DistPackage, list[ReqPackage]] = m
        self._index: dict[str, DistPackage] = {p.key: p for p in list(self._obj)}

    def get_node_as_parent(self, node_key: str) -> DistPackage | None:
        """
        Get the node from the keys of the dict representing the DAG.

        This method is useful if the dict representing the DAG contains different kind of objects in keys and values.
        Use this method to look up a node obj as a parent (from the keys of the dict) given a node key.

        :param node_key: identifier corresponding to key attr of node obj
        :returns: node obj (as present in the keys of the dict)
        """
        try:
            return self._index[node_key]
        except KeyError:
            return None

    def get_children(self, node_key: str) -> list[ReqPackage]:
        """
        Get child nodes for a node by its key.

        :param node_key: key of the node to get children of
        :returns: child nodes
        """
        node = self.get_node_as_parent(node_key)
        return self._obj[node] if node else []

    def filter_nodes(self, include: set[str] | None, exclude: set[str] | None) -> PackageDAG:  # noqa: C901, PLR0912
        """
        Filters nodes in a graph by given parameters.

        If a node is included, then all it's children are also included.

        :param include: set of node keys to include (or None)
        :param exclude: set of node keys to exclude (or None)
        :returns: filtered version of the graph
        """
        # If neither of the filters are specified, short circuit
        if include is None and exclude is None:
            return self

        # Note: In following comparisons, we use lower cased values so
        # that user may specify `key` or `project_name`. As per the
        # documentation, `key` is simply
        # `project_name.lower()`. Refer:
        # https://setuptools.readthedocs.io/en/latest/pkg_resources.html#distribution-objects
        if include:
            include = {s.lower() for s in include}
        exclude = {s.lower() for s in exclude} if exclude else set()

        # Check for mutual exclusion of show_only and exclude sets
        # after normalizing the values to lowercase
        if include and exclude:
            assert not (include & exclude)  # noqa: S101

        # Traverse the graph in a depth first manner and filter the
        # nodes according to `show_only` and `exclude` sets
        stack: deque[DistPackage] = deque()
        m: dict[DistPackage, list[ReqPackage]] = {}
        seen = set()
        for node in self._obj:
            if any(fnmatch.fnmatch(node.key, e) for e in exclude):
                continue
            if include is None or any(fnmatch.fnmatch(node.key, i) for i in include):
                stack.append(node)
            while True:
                if len(stack) > 0:
                    n = stack.pop()
                    cldn = [c for c in self._obj[n] if not any(fnmatch.fnmatch(c.key, e) for e in exclude)]
                    m[n] = cldn
                    seen.add(n.key)
                    for c in cldn:
                        if c.key not in seen:
                            cld_node = self.get_node_as_parent(c.key)
                            if cld_node:
                                stack.append(cld_node)
                            else:
                                # It means there's no root node corresponding to the child node i.e.
                                # a dependency is missing
                                continue
                else:
                    break

        return self.__class__(m)

    def reverse(self) -> ReversedPackageDAG:
        """
        Reverse the DAG, or turn it upside-down.

        In other words, the directions of edges of the nodes in the DAG will be reversed.

        Note that this function purely works on the nodes in the graph. This implies that to perform a combination of
        filtering and reversing, the order in which `filter` and `reverse` methods should be applied is important. For
        e.g., if reverse is called on a filtered graph, then only the filtered nodes and it's children will be
        considered when reversing. On the other hand, if filter is called on reversed DAG, then the definition of
        "child" nodes is as per the reversed DAG.

        :returns: DAG in the reversed form
        """
        m: defaultdict[ReqPackage, list[DistPackage]] = defaultdict(list)
        child_keys = {r.key for r in chain.from_iterable(self._obj.values())}
        for k, vs in self._obj.items():
            for v in vs:
                # if v is already added to the dict, then ensure that
                # we are using the same object. This check is required
                # as we're using array mutation
                try:
                    node: ReqPackage = [p for p in m if p.key == v.key][0]
                except IndexError:  # noqa: PERF203
                    node = v
                m[node].append(k.as_parent_of(v))
            if k.key not in child_keys:
                m[k.as_requirement()] = []
        return ReversedPackageDAG(dict(m))  # type: ignore[arg-type]

    def sort(self) -> PackageDAG:
        """
        Return sorted tree in which the underlying _obj dict is an dict, sorted alphabetically by the keys.

        :returns: Instance of same class with dict
        """
        return self.__class__(sorted_tree(self._obj))

    # Methods required by the abstract base class Mapping
    def __getitem__(self, arg: DistPackage) -> list[ReqPackage] | None:  # type: ignore[override]
        return self._obj.get(arg)

    def __iter__(self) -> Iterator[DistPackage]:
        return self._obj.__iter__()

    def __len__(self) -> int:
        return len(self._obj)


class ReversedPackageDAG(PackageDAG):
    """
    Representation of Package dependencies in the reverse order.

    Similar to it's super class `PackageDAG`, the underlying datastructure is a dict, but here the keys are expected to
    be of type `ReqPackage` and each item in the values of type `DistPackage`.

    Typically, this object will be obtained by calling `PackageDAG.reverse`.
    """

    def reverse(self) -> PackageDAG:  # type: ignore[override]
        """
        Reverse the already reversed DAG to get the PackageDAG again.

        :returns: reverse of the reversed DAG
        """
        m: defaultdict[DistPackage, list[ReqPackage]] = defaultdict(list)
        child_keys = {r.key for r in chain.from_iterable(self._obj.values())}
        for k, vs in self._obj.items():
            for v in vs:
                try:
                    node = [p for p in m if p.key == v.key][0]
                except IndexError:  # noqa: PERF203
                    node = v.as_parent_of(None)
                m[node].append(k)  # type: ignore[arg-type]
            if k.key not in child_keys:
                m[k.dist] = []
        return PackageDAG(dict(m))


def render_text(
    tree: PackageDAG,
    max_depth: float,
    encoding: str,
    list_all: bool = True,  # noqa: FBT001, FBT002
    frozen: bool = False,  # noqa: FBT001, FBT002
) -> None:
    """
    Print tree as text on console.

    :param tree: the package tree
    :param list_all: whether to list all the pgks at the root level or only those that are the sub-dependencies
    :param frozen: show the names of the pkgs in the output that's favourable to pip --freeze
    :returns: None
    """
    tree = tree.sort()
    nodes = list(tree.keys())
    branch_keys = {r.key for r in chain.from_iterable(tree.values())}

    if not list_all:
        nodes = [p for p in nodes if p.key not in branch_keys]

    if encoding in ("utf-8", "utf-16", "utf-32"):
        _render_text_with_unicode(tree, nodes, max_depth, frozen)
    else:
        _render_text_without_unicode(tree, nodes, max_depth, frozen)


def _render_text_with_unicode(
    tree: PackageDAG,
    nodes: list[DistPackage],
    max_depth: float,
    frozen: bool,  # noqa: FBT001
) -> None:
    use_bullets = not frozen

    def aux(  # noqa: PLR0913
        node: DistPackage | ReqPackage,
        parent: DistPackage | ReqPackage | None = None,
        indent: int = 0,
        cur_chain: list[str] | None = None,
        prefix: str = "",
        depth: int = 0,
        has_grand_parent: bool = False,  # noqa: FBT001, FBT002
        is_last_child: bool = False,  # noqa: FBT001, FBT002
        parent_is_last_child: bool = False,  # noqa: FBT001, FBT002
    ) -> list[Any]:
        cur_chain = cur_chain or []
        node_str = node.render(parent, frozen)
        next_prefix = ""
        next_indent = indent + 2

        if parent:
            bullet = "├── "
            if is_last_child:
                bullet = "└── "

            line_char = "│"
            if not use_bullets:
                line_char = ""
                # Add 2 spaces so direct dependencies to a project are indented
                bullet = "  "

            if has_grand_parent:
                next_indent -= 1
                if parent_is_last_child:
                    offset = 0 if len(line_char) == 1 else 1
                    prefix += " " * (indent + 1 - offset - depth)
                else:
                    prefix += line_char + " " * (indent - depth)
                # Without this extra space, bullets will point to the space just before the project name
                prefix += " " if use_bullets else ""
            next_prefix = prefix
            node_str = prefix + bullet + node_str
        result = [node_str]

        children = tree.get_children(node.key)
        children_strings = [
            aux(
                c,
                node,
                indent=next_indent,
                cur_chain=[*cur_chain, c.project_name],
                prefix=next_prefix,
                depth=depth + 1,
                has_grand_parent=parent is not None,
                is_last_child=c is children[-1],
                parent_is_last_child=is_last_child,
            )
            for c in children
            if c.project_name not in cur_chain and depth + 1 <= max_depth
        ]

        result += list(chain.from_iterable(children_strings))
        return result

    lines = chain.from_iterable([aux(p) for p in nodes])
    print("\n".join(lines))  # noqa: T201


def _render_text_without_unicode(
    tree: PackageDAG,
    nodes: list[DistPackage],
    max_depth: float,
    frozen: bool,  # noqa: FBT001
) -> None:
    use_bullets = not frozen

    def aux(
        node: DistPackage | ReqPackage,
        parent: DistPackage | ReqPackage | None = None,
        indent: int = 0,
        cur_chain: list[str] | None = None,
        depth: int = 0,
    ) -> list[Any]:
        cur_chain = cur_chain or []
        node_str = node.render(parent, frozen)
        if parent:
            prefix = " " * indent + ("- " if use_bullets else "")
            node_str = prefix + node_str
        result = [node_str]
        children = [
            aux(c, node, indent=indent + 2, cur_chain=[*cur_chain, c.project_name], depth=depth + 1)
            for c in tree.get_children(node.key)
            if c.project_name not in cur_chain and depth + 1 <= max_depth
        ]
        result += list(chain.from_iterable(children))
        return result

    lines = chain.from_iterable([aux(p) for p in nodes])
    print("\n".join(lines))  # noqa: T201


def render_json(tree: PackageDAG, indent: int) -> str:
    """
    Converts the tree into a flat json representation.

    The json repr will be a list of hashes, each hash having 2 fields:
      - package
      - dependencies: list of dependencies

    :param tree: dependency tree
    :param indent: no. of spaces to indent json
    :returns: json representation of the tree
    """
    tree = tree.sort()
    return json.dumps(
        [{"package": k.as_dict(), "dependencies": [v.as_dict() for v in vs]} for k, vs in tree.items()],
        indent=indent,
    )


def render_json_tree(tree: PackageDAG, indent: int) -> str:
    """
    Converts the tree into a nested json representation.

    The json repr will be a list of hashes, each hash having the following fields:

      - package_name
      - key
      - required_version
      - installed_version
      - dependencies: list of dependencies

    :param tree: dependency tree
    :param indent: no. of spaces to indent json
    :returns: json representation of the tree
    """
    tree = tree.sort()
    branch_keys = {r.key for r in chain.from_iterable(tree.values())}
    nodes = [p for p in tree if p.key not in branch_keys]

    def aux(
        node: DistPackage | ReqPackage,
        parent: DistPackage | ReqPackage | None = None,
        cur_chain: list[str] | None = None,
    ) -> dict[str, Any]:
        if cur_chain is None:
            cur_chain = [node.project_name]

        d: dict[str, str | list[Any] | None] = node.as_dict()  # type: ignore[assignment]
        if parent:
            d["required_version"] = node.version_spec if node.version_spec else "Any"
        else:
            d["required_version"] = d["installed_version"]

        d["dependencies"] = [
            aux(c, parent=node, cur_chain=[*cur_chain, c.project_name])
            for c in tree.get_children(node.key)
            if c.project_name not in cur_chain
        ]

        return d

    return json.dumps([aux(p) for p in nodes], indent=indent)


def render_mermaid(tree: PackageDAG) -> str:  # noqa: C901
    """
    Produce a Mermaid flowchart from the dependency graph.

    :param tree: dependency graph
    """
    # List of reserved keywords in Mermaid that cannot be used as node names.
    # See: https://github.com/mermaid-js/mermaid/issues/4182#issuecomment-1454787806
    reserved_ids: set[str] = {
        "C4Component",
        "C4Container",
        "C4Deployment",
        "C4Dynamic",
        "_blank",
        "_parent",
        "_self",
        "_top",
        "call",
        "class",
        "classDef",
        "click",
        "end",
        "flowchart",
        "flowchart-v2",
        "graph",
        "interpolate",
        "linkStyle",
        "style",
        "subgraph",
    }
    node_ids_map: dict[str, str] = {}

    def mermaid_id(key: str) -> str:
        """Returns a valid Mermaid node ID from a string."""
        # If we have already seen this key, return the canonical ID.
        canonical_id = node_ids_map.get(key)
        if canonical_id is not None:
            return canonical_id
        # If the key is not a reserved keyword, return it as is, and update the map.
        if key not in reserved_ids:
            node_ids_map[key] = key
            return key
        # If the key is a reserved keyword, append a number to it.
        number = 0
        while True:
            new_id = f"{key}_{number}"
            if new_id not in node_ids_map:
                node_ids_map[key] = new_id
                return new_id
            number += 1

    # Use a sets to avoid duplicate entries.
    nodes: set[str] = set()
    edges: set[str] = set()

    if isinstance(tree, ReversedPackageDAG):
        for package, reverse_dependencies in tree.items():
            package_label = "\\n".join(
                (package.project_name, "(missing)" if package.is_missing else package.installed_version),
            )
            package_key = mermaid_id(package.key)
            nodes.add(f'{package_key}["{package_label}"]')
            for reverse_dependency in reverse_dependencies:
                edge_label = reverse_dependency.req.version_spec or "any"
                reverse_dependency_key = mermaid_id(reverse_dependency.key)
                edges.add(f'{package_key} -- "{edge_label}" --> {reverse_dependency_key}')
    else:
        for package, dependencies in tree.items():
            package_label = f"{package.project_name}\\n{package.version}"
            package_key = mermaid_id(package.key)
            nodes.add(f'{package_key}["{package_label}"]')
            for dependency in dependencies:
                edge_label = dependency.version_spec or "any"
                dependency_key = mermaid_id(dependency.key)
                if dependency.is_missing:
                    dependency_label = f"{dependency.project_name}\\n(missing)"
                    nodes.add(f'{dependency_key}["{dependency_label}"]:::missing')
                    edges.add(f"{package_key} -.-> {dependency_key}")
                else:
                    edges.add(f'{package_key} -- "{edge_label}" --> {dependency_key}')

    # Produce the Mermaid Markdown.
    indent = " " * 4
    output = dedent(
        f"""\
        flowchart TD
        {indent}classDef missing stroke-dasharray: 5
        """,
    )
    # Sort the nodes and edges to make the output deterministic.
    output += indent
    output += f"\n{indent}".join(node for node in sorted(nodes))
    output += "\n" + indent
    output += f"\n{indent}".join(edge for edge in sorted(edges))
    output += "\n"
    return output


def dump_graphviz(  # noqa: C901, PLR0912
    tree: PackageDAG,
    output_format: str = "dot",
    is_reverse: bool = False,  # noqa: FBT001, FBT002
) -> str | bytes:
    """
    Output dependency graph as one of the supported GraphViz output formats.

    :param dict tree: dependency graph
    :param string output_format: output format
    :param bool is_reverse: reverse or not
    :returns: representation of tree in the specified output format
    :rtype: str or binary representation depending on the output format

    """
    try:
        from graphviz import Digraph
    except ImportError as exc:
        print(  # noqa: T201
            "graphviz is not available, but necessary for the output option. Please install it.",
            file=sys.stderr,
        )
        raise SystemExit(1) from exc

    try:
        from graphviz import parameters
    except ImportError:
        from graphviz import backend

        valid_formats = backend.FORMATS
        print(  # noqa: T201
            "Deprecation warning! Please upgrade graphviz to version >=0.18.0 "
            "Support for older versions will be removed in upcoming release",
            file=sys.stderr,
        )
    else:
        valid_formats = parameters.FORMATS

    if output_format not in valid_formats:
        print(f"{output_format} is not a supported output format.", file=sys.stderr)  # noqa: T201
        print(f"Supported formats are: {', '.join(sorted(valid_formats))}", file=sys.stderr)  # noqa: T201
        raise SystemExit(1)

    graph = Digraph(format=output_format)

    if is_reverse:
        for dep_rev, parents in tree.items():
            dep_label = f"{dep_rev.project_name}\\n{dep_rev.installed_version}"
            graph.node(dep_rev.key, label=dep_label)
            for parent in parents:
                # req reference of the dep associated with this
                # particular parent package
                req_ref = parent.req
                edge_label = req_ref.version_spec or "any"
                graph.edge(dep_rev.key, parent.key, label=edge_label)
    else:
        for pkg, deps in tree.items():
            pkg_label = f"{pkg.project_name}\\n{pkg.version}"
            graph.node(pkg.key, label=pkg_label)
            for dep in deps:
                edge_label = dep.version_spec or "any"
                if dep.is_missing:
                    dep_label = f"{dep.project_name}\\n(missing)"
                    graph.node(dep.key, label=dep_label, style="dashed")
                    graph.edge(pkg.key, dep.key, style="dashed")
                else:
                    graph.edge(pkg.key, dep.key, label=edge_label)

    # Allow output of dot format, even if GraphViz isn't installed.
    if output_format == "dot":
        # Emulates graphviz.dot.Dot.__iter__() to force the sorting of graph.body.
        # Fixes https://github.com/tox-dev/pipdeptree/issues/188
        # That way we can guarantee the output of the dot format is deterministic
        # and stable.
        return "".join([tuple(graph)[0], *sorted(graph.body), graph._tail])  # noqa: SLF001

    # As it's unknown if the selected output format is binary or not, try to
    # decode it as UTF8 and only print it out in binary if that's not possible.
    try:
        return graph.pipe().decode("utf-8")  # type: ignore[no-any-return]
    except UnicodeDecodeError:
        return graph.pipe()  # type: ignore[no-any-return]


def print_graphviz(dump_output: str | bytes) -> None:
    """
    Dump the data generated by GraphViz to stdout.

    :param dump_output: The output from dump_graphviz
    """
    if hasattr(dump_output, "encode"):
        print(dump_output)  # noqa: T201
    else:
        with os.fdopen(sys.stdout.fileno(), "wb") as bytestream:
            bytestream.write(dump_output)


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
            pkg = p.render_as_root(False)  # noqa: FBT003
            print(f"* {pkg}", file=sys.stderr)  # noqa: T201
            for req in conflicts[p]:
                req_str = req.render_as_branch(False)  # noqa: FBT003
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
                        p_as_dep_of_r = [x for x in entry if x.key == p.key][0]
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


def get_parser() -> ArgumentParser:
    parser = ArgumentParser(description="Dependency tree of the installed python packages")
    parser.add_argument("-v", "--version", action="version", version=f"{__version__}")
    parser.add_argument("-f", "--freeze", action="store_true", help="Print names so as to write freeze files")
    parser.add_argument(
        "--python",
        default=sys.executable,
        help="Python to use to look for packages in it (default: where installed)",
    )
    parser.add_argument("-a", "--all", action="store_true", help="list all deps at top level")
    parser.add_argument(
        "-l",
        "--local-only",
        action="store_true",
        help="If in a virtualenv that has global access do not show globally installed packages",
    )
    parser.add_argument("-u", "--user-only", action="store_true", help="Only show installations in the user site dir")
    parser.add_argument(
        "-w",
        "--warn",
        action="store",
        dest="warn",
        nargs="?",
        default="suppress",
        choices=("silence", "suppress", "fail"),
        help=(
            'Warning control. "suppress" will show warnings '
            "but return 0 whether or not they are present. "
            '"silence" will not show warnings at all and '
            'always return 0. "fail" will show warnings and '
            "return 1 if any are present. The default is "
            '"suppress".'
        ),
    )
    parser.add_argument(
        "-r",
        "--reverse",
        action="store_true",
        default=False,
        help=(
            "Shows the dependency tree in the reverse fashion "
            "ie. the sub-dependencies are listed with the "
            "list of packages that need them under them."
        ),
    )
    parser.add_argument(
        "-p",
        "--packages",
        help=(
            "Comma separated list of select packages to show in the output. "
            "Wildcards are supported, like 'somepackage.*'. "
            "If set, --all will be ignored."
        ),
    )
    parser.add_argument(
        "-e",
        "--exclude",
        help=(
            "Comma separated list of select packages to exclude from the output. "
            "Wildcards are supported, like 'somepackage.*'. "
            "If set, --all will be ignored."
        ),
        metavar="PACKAGES",
    )
    parser.add_argument(
        "-j",
        "--json",
        action="store_true",
        default=False,
        help=(
            "Display dependency tree as json. This will yield "
            '"raw" output that may be used by external tools. '
            "This option overrides all other options."
        ),
    )
    parser.add_argument(
        "--json-tree",
        action="store_true",
        default=False,
        help=(
            "Display dependency tree as json which is nested "
            "the same way as the plain text output printed by default. "
            "This option overrides all other options (except --json)."
        ),
    )
    parser.add_argument(
        "--mermaid",
        action="store_true",
        default=False,
        help="Display dependency tree as a Mermaid graph. This option overrides all other options.",
    )
    parser.add_argument(
        "--graph-output",
        dest="output_format",
        help=(
            "Print a dependency graph in the specified output "
            "format. Available are all formats supported by "
            "GraphViz, e.g.: dot, jpeg, pdf, png, svg"
        ),
    )
    parser.add_argument(
        "-d",
        "--depth",
        type=lambda x: int(x) if x.isdigit() and (int(x) >= 0) else parser.error("Depth must be a number that is >= 0"),
        default=float("inf"),
        help=(
            "Display dependency tree up to a depth >=0 using the default text display. All other display options"
            " ignore this argument."
        ),
    )
    parser.add_argument(
        "--encoding",
        dest="encoding_type",
        default=sys.stdout.encoding,
        help="Display dependency tree as text using specified encoding",
    )
    return parser


class Options(Namespace):
    freeze: bool
    python: str
    all: bool  # noqa: A003
    local_only: bool
    warn: Literal["silence", "suppress", "fail"]
    reverse: bool
    packages: str
    exclude: str
    json: bool
    json_tree: bool
    mermaid: bool
    graph_output: str | None
    depth: float
    encoding: str


def _get_args() -> Options:
    parser = get_parser()
    return cast(Options, parser.parse_args())


def handle_non_host_target(args: Options) -> int | None:
    # if target is not current python re-invoke it under the actual host
    py_path = Path(args.python).absolute()
    if py_path != Path(sys.executable).absolute():
        # there's no way to guarantee that graphviz is available, so refuse
        if args.output_format:
            print(  # noqa: T201
                "graphviz functionality is not supported when querying non-host python",
                file=sys.stderr,
            )
            raise SystemExit(1)
        argv = sys.argv[1:]  # remove current python executable
        for py_at, value in enumerate(argv):
            if value == "--python":
                del argv[py_at]
                del argv[py_at]
            elif value.startswith("--python"):
                del argv[py_at]

        main_file = inspect.getsourcefile(sys.modules[__name__])
        assert main_file is not None  # noqa: S101
        with tempfile.TemporaryDirectory() as project:
            shutil.copytree(Path(main_file).parent, Path(project) / "pipdeptree")
            # invoke from an empty folder to avoid cwd altering sys.path
            env = os.environ.copy()
            env["PYTHONPATH"] = project
            cmd: list[Path | str] = [py_path, "-m", "pipdeptree"]
            cmd.extend(argv)
            return subprocess.call(cmd, cwd=project, env=env)  # noqa: S603
    return None


def get_installed_distributions(
    local_only: bool = False,  # noqa: FBT001, FBT002
    user_only: bool = False,  # noqa: FBT001, FBT002
) -> list[DistInfoDistribution]:
    try:
        from pip._internal.metadata import pkg_resources
    except ImportError:
        # For backward compatibility with python ver. 2.7 and pip
        # version 20.3.4 (the latest pip version that works with python
        # version 2.7)
        from pip._internal.utils import misc

        return misc.get_installed_distributions(  # type: ignore[no-any-return,attr-defined]
            local_only=local_only,
            user_only=user_only,
        )

    else:
        dists = pkg_resources.Environment.from_paths(None).iter_installed_distributions(
            local_only=local_only,
            skip=(),
            user_only=user_only,
        )
        return [d._dist for d in dists]  # type: ignore[attr-defined] # noqa: SLF001


def main() -> None | int:
    args = _get_args()
    result = handle_non_host_target(args)
    if result is not None:
        return result

    pkgs = get_installed_distributions(local_only=args.local_only, user_only=args.user_only)
    tree = PackageDAG.from_pkgs(pkgs)
    is_text_output = not any([args.json, args.json_tree, args.output_format])

    return_code = _check_cycle_conflict(args, is_text_output, tree)

    # Reverse the tree (if applicable) before filtering, thus ensuring
    # that the filter will be applied on ReverseTree
    if args.reverse:
        tree = tree.reverse()

    show_only = set(args.packages.split(",")) if args.packages else None
    exclude = set(args.exclude.split(",")) if args.exclude else None

    if show_only is not None or exclude is not None:
        tree = tree.filter_nodes(show_only, exclude)

    _render(args, tree)

    return return_code


def _check_cycle_conflict(args: Options, is_text_output: bool, tree: PackageDAG) -> int:  # noqa: FBT001
    # Before any reversing or filtering, show warnings to console
    # about possibly conflicting or cyclic deps if found and warnings
    # are enabled (i.e. only if output is to be printed to console)
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


def _render(args: Options, tree: PackageDAG) -> None:
    if args.json:
        print(render_json(tree, indent=4))  # noqa: T201
    elif args.json_tree:
        print(render_json_tree(tree, indent=4))  # noqa: T201
    elif args.mermaid:
        print(render_mermaid(tree))  # noqa: T201
    elif args.output_format:
        output = dump_graphviz(tree, output_format=args.output_format, is_reverse=args.reverse)
        print_graphviz(output)
    else:
        render_text(tree, args.depth, args.encoding_type, args.all, args.freeze)
