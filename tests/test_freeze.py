from __future__ import annotations

from unittest.mock import Mock

from pipdeptree._parser import distribution_to_specifier


def test_distribution_to_specifier() -> None:
    foo = Mock(metadata={"Name": "foo"}, version="20.4.1")
    foo.read_text = Mock(return_value=None)
    expected = "foo==20.4.1"
    assert distribution_to_specifier(foo) == expected
