from __future__ import annotations

from subprocess import TimeoutExpired  # noqa: S404


def raise_timeout(_process: object) -> None:
    msg = "cmd"
    raise TimeoutExpired(msg, 5)


def raise_file_not_found(_process: object) -> None:
    raise FileNotFoundError
