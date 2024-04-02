from __future__ import annotations

import site
import sys
from importlib.metadata import distributions
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from importlib.metadata import Distribution


def get_installed_distributions(
    local_only: bool = False,  # noqa: FBT001, FBT002
    user_only: bool = False,  # noqa: FBT001, FBT002
) -> list[Distribution]:
    if user_only:
        return list(distributions(path=[site.getusersitepackages()]))

    # NOTE: See https://docs.python.org/3/library/venv.html#how-venvs-work for more details.
    in_venv = sys.prefix != sys.base_prefix

    if local_only and in_venv:
        venv_site_packages = site.getsitepackages([sys.prefix])
        return list(distributions(path=venv_site_packages))

    return list(distributions())


__all__ = [
    "get_installed_distributions",
]
