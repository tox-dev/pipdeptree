from __future__ import annotations

from unittest.mock import Mock

from pipdeptree._freeze import dist_to_frozen_repr


def test_dist_to_frozen_repr() -> None:
    foo = Mock(metadata={"Name": "foo"}, version="20.4.1")
    foo.read_text = Mock(return_value=None)
    expected = "foo==20.4.1"
    assert dist_to_frozen_repr(foo) == expected
