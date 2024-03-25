from __future__ import annotations

import locale
import re
from abc import ABC, abstractmethod
from importlib import import_module
from importlib.metadata import Distribution, PackageNotFoundError, metadata, version
from inspect import ismodule
from typing import TYPE_CHECKING, Any
from pathlib import Path

from packaging.requirements import Requirement
from packaging.specifiers import SpecifierSet
from pip._internal.models.direct_url import DirectUrl # noqa: PLC2701
from pip._internal.utils.urls import url_to_path # noqa: PLC2701
from pip._internal.utils.egg_link import egg_link_path_from_sys_path # noqa: PLC2701

if TYPE_CHECKING:
    from importlib.metadata import Distribution


def pep503_normalize(name: str) -> str:
    return re.sub("[-_.]+", "-", name)

def contains_extra(marker: str) -> bool:
    return re.search(r"\bextra\s*==", marker)

class Package(ABC):
    """Abstract class for wrappers around objects that pip returns."""

    UNKNOWN_LICENSE_STR = "(Unknown license)"

    def __init__(self, project_name: str) -> None:
        self._project_name = project_name
        self.key = pep503_normalize(project_name)

    def licenses(self) -> str:
        try:
            dist_metadata = metadata(self.key)
        except PackageNotFoundError:
            return self.UNKNOWN_LICENSE_STR

        license_strs: list[str] = []
        classifiers = dist_metadata.get_all("Classifier", [])

        for classifier in classifiers:
            line = str(classifier)
            if line.startswith("License"):
                license_str = line.split(":: ")[-1]
                license_strs.append(license_str)

        if len(license_strs) == 0:
            return self.UNKNOWN_LICENSE_STR

        return f'({", ".join(license_strs)})'

    @property
    def project_name(self) -> str:
        return pep503_normalize(self._project_name)

    @abstractmethod
    def render_as_root(self, *, frozen: bool) -> str:
        raise NotImplementedError

    @abstractmethod
    def render_as_branch(self, *, frozen: bool) -> str:
        raise NotImplementedError

    @abstractmethod
    def as_dict(self) -> dict[str, str]:
        raise NotImplementedError

    def render(
        self,
        parent: DistPackage | ReqPackage | None = None,
        *,
        frozen: bool = False,
    ) -> str:
        render = self.render_as_branch if parent else self.render_as_root
        return render(frozen=frozen)

    @staticmethod
    def as_frozen_repr(obj: DistPackage) -> str:
        # The `pip._internal.metadata` modules were introduced in 21.1.1
        # and the `pip._internal.operations.freeze.FrozenRequirement`
        # class now expects dist to be a subclass of
        # `pip._internal.metadata.BaseDistribution`, however the
        # `pip._internal.utils.misc.get_installed_distributions` continues
        # to return objects of type
        # pip._vendor.pkg_resources.DistInfoDistribution.
        #
        # This is a hacky backward compatible (with older versions of pip) fix.

        from pip._internal.operations.freeze import FrozenRequirement  # noqa: PLC0415, PLC2701 # pragma: no cover

        fr = FrozenRequirement.from_dist(obj)

        return str(fr).strip()

    def __repr__(self) -> str:
        return f'<{self.__class__.__name__}("{self.key}")>'

    def __lt__(self, rhs: Package) -> bool:
        return self.key < rhs.key


class DistPackage(Package):
    """
    Wrapper class for pkg_resources.Distribution instances.

    :param obj: pkg_resources.Distribution to wrap over
    :param req: optional ReqPackage object to associate this DistPackage with. This is useful for displaying the tree in
        reverse

    """

    def __init__(self, obj: Distribution, req: ReqPackage | None = None) -> None:
        if hasattr(obj, "key"):
            super().__init__(obj.key)
        else:
            super().__init__(obj.metadata["Name"])
        self._obj = obj
        self.req = req

    def requires(self) -> list[Requirement]:
        req_list = []
        req_name_list = []
        if self._obj.requires:
            for r in self._obj.requires:
                req = Requirement(r)
                is_extra_req = req.marker and contains_extra(str(req.marker))
                if not is_extra_req and req.name not in req_name_list:
                    req_list.append(req)
                    req_name_list.append(req.name)
        return req_list

    @property
    def editable(self) -> bool:
        return self.direct_url_dict["editable"]

    @property
    def direct_url(self) -> str:
        return self.direct_url_dict["url"]

    @property
    def raw_name(self) -> str:
        return self.project_name

    @property
    def version(self) -> str:
        return self._obj.version  # type: ignore[no-any-return]

    @property
    def editable_project_location(self) -> str:
        if self.direct_url:
            from pip._internal.utils.urls import url_to_path # noqa: PLC2701, PLC0415

            return url_to_path(self.direct_url)

        from pip._internal.utils.egg_link import egg_link_path_from_sys_path # noqa: PLC2701, PLC0415

        egg_link_path = egg_link_path_from_sys_path(self.raw_name)
        if egg_link_path:
            return self.location
        return None

    @property
    def direct_url_dict(self) -> dict[str, Any]:
        result = {"editable": False, "url": None}

        if not self._obj.files:
            return result

        for path in self._obj.files:
            if Path(path).name == "direct_url.json":
                abstract_path = Path(self._obj.locate_file(path))
                with abstract_path.open('r') as f:
                    drurl = DirectUrl.from_json(f.read())
                    result["url"] = drurl.url
                    result["editable"] = bool(drurl.is_local_editable)
                break

        return result

    def render_as_root(self, *, frozen: bool) -> str:
        if not frozen:
            return f"{self.project_name}=={self.version}"
        return self.as_frozen_repr(self)

    def render_as_branch(self, *, frozen: bool) -> str:
        assert self.req is not None
        if not frozen:
            parent_ver_spec = self.req.version_spec
            parent_str = self.req.project_name
            if parent_ver_spec:
                parent_str += parent_ver_spec
            return f"{self.project_name}=={self.version} [requires: {parent_str}]"
        return self.render_as_root(frozen=frozen)

    def as_requirement(self) -> ReqPackage:
        """Return a ReqPackage representation of this DistPackage."""
        return ReqPackage(self._obj.as_requirement(), dist=self)  # type: ignore[no-untyped-call]

    def as_parent_of(self, req: ReqPackage | None) -> DistPackage:
        """
        Return a DistPackage instance associated to a requirement.

        This association is necessary for reversing the PackageDAG.
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
        if hasattr(obj, "key"):
            super().__init__(obj.key)
        else:
            super().__init__(obj.name)
        self._obj = obj
        self.dist = dist

    def render_as_root(self, *, frozen: bool) -> str:
        if not frozen:
            return f"{self.project_name}=={self.installed_version}"
        if self.dist:
            return self.as_frozen_repr(self.dist)
        return self.project_name

    def render_as_branch(self, *, frozen: bool) -> str:
        if not frozen:
            req_ver = self.version_spec if self.version_spec else "Any"
            return f"{self.project_name} [required: {req_ver}, installed: {self.installed_version}]"
        return self.render_as_root(frozen=frozen)

    @property
    def version_spec(self) -> str | None:
        result = None
        specs = sorted(map(str, self._obj.specifier), reverse=True)
        if specs:
            result = ",".join(specs)
        return result

    @property
    def installed_version(self) -> str:
        if not self.dist:
            try:
                return version(self.key)
            except PackageNotFoundError:
                pass
            # Avoid AssertionError with setuptools, see https://github.com/tox-dev/pipdeptree/issues/162
            if self.key == "setuptools":
                return self.UNKNOWN_VERSION
            try:
                m = import_module(self.key)
            except ImportError:
                return self.UNKNOWN_VERSION
            else:
                v = getattr(m, "__version__", self.UNKNOWN_VERSION)
                if ismodule(v):
                    return getattr(v, "__version__", self.UNKNOWN_VERSION)
                return v
        return self.dist.version

    @property
    def is_missing(self) -> bool:
        return self.installed_version == self.UNKNOWN_VERSION

    def is_conflicting(self) -> bool:
        """If installed version conflicts with required version."""
        # unknown installed version is also considered conflicting
        if self.installed_version == self.UNKNOWN_VERSION:
            return True

        ver_spec = self.version_spec if self.version_spec else ""
        if ver_spec:
            req_obj = SpecifierSet(ver_spec)
        else:
            return False

        return self.installed_version not in req_obj

    def as_dict(self) -> dict[str, str]:
        return {
            "key": self.key,
            "package_name": self.project_name,
            "installed_version": self.installed_version,
            "required_version": self.version_spec if self.version_spec is not None else "Any",
        }


__all__ = [
    "DistPackage",
    "ReqPackage",
]
