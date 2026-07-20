from __future__ import annotations

from importlib import reload

import pytest

from pipdeptree import _rust, version


@pytest.mark.parametrize(
    ("release", "expected"),
    [
        pytest.param("4.1.0", (4, 1, 0), id="final"),
        pytest.param("4.1.0b1", (4, 1, "0b1"), id="beta"),
        pytest.param("4.1.0rc1.dev3", (4, 1, "0rc1", "dev3"), id="dev"),
    ],
)
def test_version_tuple(monkeypatch: pytest.MonkeyPatch, release: str, expected: tuple[int | str, ...]) -> None:
    monkeypatch.setattr(_rust, "version", lambda: release)
    try:
        assert reload(version).version_tuple == expected
    finally:
        monkeypatch.undo()
        reload(version)
