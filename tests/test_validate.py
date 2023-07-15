from __future__ import annotations

from typing import TYPE_CHECKING, Callable, Iterator

import pytest

from pipdeptree._models import PackageDAG
from pipdeptree._validate import conflicting_deps, cyclic_deps, render_conflicts_text, render_cycles_text

if TYPE_CHECKING:
    from unittest.mock import Mock

    from tests.our_types import MockGraph


@pytest.mark.parametrize(
    ("mpkgs", "expected_keys", "expected_output"),
    [
        (
            {
                ("a", "1.0.1"): [("b", [(">=", "2.0.0")])],
                ("b", "2.3.0"): [("a", [(">=", "1.0.1")])],
                ("c", "4.5.0"): [("d", [("==", "2.0")])],
                ("d", "2.0"): [],
            },
            [("a", "b", "a"), ("b", "a", "b")],
            ["Warning!! Cyclic dependencies found:", "* b => a => b", "* a => b => a"],
        ),
        (  # if a dependency isn't installed, cannot verify cycles
            {
                ("a", "1.0.1"): [("b", [(">=", "2.0.0")])],
            },
            [],
            [],  # no output expected
        ),
    ],
)
def test_cyclic_deps(
    capsys: pytest.CaptureFixture[str],
    mpkgs: dict[tuple[str, str], list[tuple[str, list[tuple[str, str]]]]],
    expected_keys: list[tuple[str, ...]],
    expected_output: list[str],
    mock_pkgs: Callable[[MockGraph], Iterator[Mock]],
) -> None:
    tree = PackageDAG.from_pkgs(list(mock_pkgs(mpkgs)))
    result = cyclic_deps(tree)
    result_keys = [(a.key, b.key, c.key) for (a, b, c) in result]
    assert sorted(expected_keys) == sorted(result_keys)
    render_cycles_text(result)
    captured = capsys.readouterr()
    assert "\n".join(expected_output).strip() == captured.err.strip()


@pytest.mark.parametrize(
    ("mpkgs", "expected_keys", "expected_output"),
    [
        (
            {("a", "1.0.1"): [("b", [(">=", "2.3.0")])], ("b", "1.9.1"): []},
            {"a": ["b"]},
            [
                "Warning!!! Possibly conflicting dependencies found:",
                "* a==1.0.1",
                " - b [required: >=2.3.0, installed: 1.9.1]",
            ],
        ),
        (
            {("a", "1.0.1"): [("c", [(">=", "9.4.1")])], ("b", "2.3.0"): [("c", [(">=", "7.0")])], ("c", "8.0.1"): []},
            {"a": ["c"]},
            [
                "Warning!!! Possibly conflicting dependencies found:",
                "* a==1.0.1",
                " - c [required: >=9.4.1, installed: 8.0.1]",
            ],
        ),
        (
            {("a", "1.0.1"): [("c", [(">=", "9.4.1")])], ("b", "2.3.0"): [("c", [(">=", "9.4.0")])]},
            {"a": ["c"], "b": ["c"]},
            [
                "Warning!!! Possibly conflicting dependencies found:",
                "* a==1.0.1",
                " - c [required: >=9.4.1, installed: ?]",
                "* b==2.3.0",
                " - c [required: >=9.4.0, installed: ?]",
            ],
        ),
        (
            {("a", "1.0.1"): [("c", [(">=", "9.4.1")])], ("b", "2.3.0"): [("c", [(">=", "7.0")])], ("c", "9.4.1"): []},
            {},
            [],
        ),
    ],
)
def test_conflicting_deps(
    capsys: pytest.CaptureFixture[str],
    mpkgs: dict[tuple[str, str], list[tuple[str, list[tuple[str, str]]]]],
    expected_keys: dict[str, list[str]],
    expected_output: list[str],
    mock_pkgs: Callable[[MockGraph], Iterator[Mock]],
) -> None:
    tree = PackageDAG.from_pkgs(list(mock_pkgs(mpkgs)))
    result = conflicting_deps(tree)
    result_keys = {k.key: [v.key for v in vs] for k, vs in result.items()}
    assert expected_keys == result_keys
    render_conflicts_text(result)
    captured = capsys.readouterr()
    assert "\n".join(expected_output).strip() == captured.err.strip()
