from __future__ import annotations

from pipdeptree import version


def test_version_exports() -> None:
    assert version.__all__ == [
        "__commit_id__",
        "__version__",
        "__version_tuple__",
        "commit_id",
        "version",
        "version_tuple",
    ]
