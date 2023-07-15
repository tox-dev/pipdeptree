from __future__ import annotations

from abc import ABC, abstractmethod
from collections import defaultdict, deque
from fnmatch import fnmatch
from importlib import import_module
from importlib.metadata import PackageNotFoundError, version
from inspect import ismodule
from itertools import chain
from typing import TYPE_CHECKING, Any, Iterator, List, Mapping, cast

from pip._vendor.pkg_resources import Distribution, Requirement

if TYPE_CHECKING:
    from pip._internal.metadata import BaseDistribution
    from pip._vendor.pkg_resources import DistInfoDistribution

try:
    from pip._internal.operations.freeze import FrozenRequirement
except ImportError:
    from pip import FrozenRequirement  # type: ignore[attr-defined, no-redef]


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
            if any(fnmatch(node.key, e) for e in exclude):
                continue
            if include is None or any(fnmatch(node.key, i) for i in include):
                stack.append(node)
            while stack:
                n = stack.pop()
                cldn = [c for c in self._obj[n] if not any(fnmatch(c.key, e) for e in exclude)]
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
                node: ReqPackage = next((p for p in m if p.key == v.key), v)
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
                node = next((p for p in m if p.key == v.key), v.as_parent_of(None))
                m[node].append(k)  # type: ignore[arg-type]
            if k.key not in child_keys:
                m[k.dist] = []
        return PackageDAG(dict(m))


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
        return version(pkg_key)
    except PackageNotFoundError:
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
        if ismodule(v):
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


__all__ = [
    "DistPackage",
    "ReqPackage",
    "PackageDAG",
    "ReversedPackageDAG",
]
