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
    if user_only:
        return list(distributions(path=[site.getusersitepackages()]))

    # NOTE: See https://docs.python.org/3/library/venv.html#how-venvs-work for more details.
    in_venv = sys.prefix != sys.base_prefix

    if local_only and in_venv:
        # TODO: Are venvs given only one site package?
        venv_site_packages = [sp for sp in site.getsitepackages() or [] if sp.startswith(sys.prefix)]
        return list(distributions(path=venv_site_packages))

    return list(distributions())


__all__ = [
    "get_installed_distributions",
]
