from __future__ import annotations

from importlib import reload
from typing import TYPE_CHECKING

import pytest

from pipdeptree import _rust, version  # ruff:ignore[import-private-name]  # paired test patches the extension

if TYPE_CHECKING:
    from pytest_mock import MockerFixture


@pytest.mark.parametrize(
    ("release", "expected"),
    [
        pytest.param("4.1.0", (4, 1, 0), id="final"),
        pytest.param("4.1.0b1", (4, 1, "0b1"), id="beta"),
        pytest.param("4.1.0rc1.dev3", (4, 1, "0rc1", "dev3"), id="dev"),
    ],
)
def test_version_tuple(mocker: MockerFixture, release: str, expected: tuple[int | str, ...]) -> None:
    mocker.patch.object(_rust, "version", return_value=release, autospec=True)
    try:
        assert reload(version).version_tuple == expected
    finally:
        mocker.stopall()
        reload(version)
