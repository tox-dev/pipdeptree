from __future__ import annotations

import site
import sys
from importlib.metadata import distributions
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from importlib.metadata import Distribution


def is_virtual_environment() -> bool:
    return sys.prefix != sys.base_prefix


def get_site_packages_directory() -> list[str] | None:
    if is_virtual_environment():
        return site.getsitepackages()
    return None


def get_installed_distributions(
    local_only: bool = False,  # noqa: FBT001, FBT002
    user_only: bool = False,  # noqa: FBT001, FBT002
) -> list[Distribution]:
    dists = distributions()

    if local_only:
        site_packages = get_site_packages_directory()
        dists = [d for d in dists if str(d.locate_file("")) in site_packages]

    if user_only:
        user_site = site.getusersitepackages()
        dists = [d for d in dists if str(d.locate_file("")) == user_site]

    return dists


__all__ = [
    "get_installed_distributions",
]
