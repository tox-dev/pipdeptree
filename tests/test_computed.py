from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest

from pipdeptree._computed import (
    _format_size,
    compute_installed_size_bytes,
    compute_unique_deps,
    format_computed_display,
    get_computed_values,
)
from pipdeptree._models import PackageDAG

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator
    from pathlib import Path
    from unittest.mock import Mock

    from tests.our_types import MockGraph


@pytest.mark.parametrize(
    ("size_bytes", "expected"),
    [
        pytest.param(0, "0 B", id="zero"),
        pytest.param(512, "512 B", id="bytes"),
        pytest.param(1024, "1.0 KB", id="kilobytes"),
        pytest.param(1536, "1.5 KB", id="fractional-kb"),
        pytest.param(1048576, "1.0 MB", id="megabytes"),
        pytest.param(1073741824, "1.0 GB", id="gigabytes"),
    ],
)
def test_format_size(size_bytes: int, expected: str) -> None:
    assert _format_size(size_bytes) == expected


def test_compute_installed_size_bytes_no_files() -> None:
    mock_dist = MagicMock()
    mock_dist.files = None
    with patch("pipdeptree._computed.distribution", return_value=mock_dist):
        assert compute_installed_size_bytes("some-pkg") is None


def test_compute_installed_size_bytes_with_files(tmp_path: Path) -> None:
    (tmp_path / "file1.py").write_text("x" * 100)
    (tmp_path / "file2.py").write_text("y" * 200)

    mock_dist = MagicMock()
    mock_dist.files = ["file1.py", "file2.py"]
    mock_dist.locate_file = lambda f: tmp_path / f
    with patch("pipdeptree._computed.distribution", return_value=mock_dist):
        assert compute_installed_size_bytes("some-pkg") == 300


def test_compute_unique_deps(mock_pkgs: Callable[[MockGraph], Iterator[Mock]]) -> None:
    graph: MockGraph = {
        ("a", "1.0"): [("c", [(">=", "1.0")])],
        ("b", "1.0"): [("d", [(">=", "1.0")])],
        ("c", "1.0"): [],
        ("d", "1.0"): [],
    }
    if dag := PackageDAG.from_pkgs(list(mock_pkgs(graph))):
        assert compute_unique_deps("a", dag) == {"c"}
        assert compute_unique_deps("b", dag) == {"d"}


def test_compute_unique_deps_shared(mock_pkgs: Callable[[MockGraph], Iterator[Mock]]) -> None:
    graph: MockGraph = {
        ("a", "1.0"): [("c", [(">=", "1.0")])],
        ("b", "1.0"): [("c", [(">=", "1.0")])],
        ("c", "1.0"): [],
    }
    if dag := PackageDAG.from_pkgs(list(mock_pkgs(graph))):
        assert compute_unique_deps("a", dag) == set()
        assert compute_unique_deps("b", dag) == set()


def test_get_computed_values_size_and_unique_deps(mock_pkgs: Callable[[MockGraph], Iterator[Mock]]) -> None:
    graph: MockGraph = {
        ("a", "1.0"): [("b", [(">=", "1.0")])],
        ("b", "1.0"): [],
    }
    dag = PackageDAG.from_pkgs(list(mock_pkgs(graph)))
    with patch("pipdeptree._computed.compute_installed_size_bytes", return_value=100):
        result = get_computed_values("a", ["size", "unique-deps-count", "unique-deps-names"], dag)
    assert result == {"size": "100 B", "unique_deps_count": 1, "unique_deps_names": ["b"]}


def test_get_computed_values_size_raw(mock_pkgs: Callable[[MockGraph], Iterator[Mock]]) -> None:
    dag = PackageDAG.from_pkgs(list(mock_pkgs({("a", "1.0"): []})))
    with patch("pipdeptree._computed.compute_installed_size_bytes", return_value=123456):
        assert get_computed_values("a", ["size-raw"], dag) == {"size_raw": 123456}


def test_get_computed_values_size_and_size_raw_computes_once(mock_pkgs: Callable[[MockGraph], Iterator[Mock]]) -> None:
    dag = PackageDAG.from_pkgs(list(mock_pkgs({("a", "1.0"): []})))
    with patch("pipdeptree._computed.compute_installed_size_bytes", return_value=2048) as mock_size:
        result = get_computed_values("a", ["size", "size-raw"], dag)
        mock_size.assert_called_once_with("a")
    assert result == {"size": "2.0 KB", "size_raw": 2048}


def test_get_computed_values_unique_deps_computes_once(mock_pkgs: Callable[[MockGraph], Iterator[Mock]]) -> None:
    graph: MockGraph = {
        ("a", "1.0"): [("b", [(">=", "1.0")])],
        ("b", "1.0"): [],
    }
    dag = PackageDAG.from_pkgs(list(mock_pkgs(graph)))
    with patch("pipdeptree._computed.compute_unique_deps", return_value={"b"}) as mock_unique:
        result = get_computed_values("a", ["unique-deps-count", "unique-deps-names"], dag)
        mock_unique.assert_called_once_with("a", dag)
    assert result == {"unique_deps_count": 1, "unique_deps_names": ["b"]}


def test_format_computed_display_count_and_names(mock_pkgs: Callable[[MockGraph], Iterator[Mock]]) -> None:
    graph: MockGraph = {
        ("a", "1.0"): [("b", [(">=", "1.0")])],
        ("b", "1.0"): [],
    }
    dag = PackageDAG.from_pkgs(list(mock_pkgs(graph)))
    with patch("pipdeptree._computed.compute_installed_size_bytes", return_value=100):
        result = format_computed_display("a", ["size", "unique-deps-count", "unique-deps-names"], dag)
    assert result == ["100 B", "1 unique deps", "unique: b"]


def test_format_computed_display_hides_zero_unique_deps(mock_pkgs: Callable[[MockGraph], Iterator[Mock]]) -> None:
    dag = PackageDAG.from_pkgs(list(mock_pkgs({("a", "1.0"): []})))
    assert format_computed_display("a", ["unique-deps-count", "unique-deps-names"], dag) == []


def test_format_computed_display_size_raw(mock_pkgs: Callable[[MockGraph], Iterator[Mock]]) -> None:
    dag = PackageDAG.from_pkgs(list(mock_pkgs({("a", "1.0"): []})))
    with patch("pipdeptree._computed.compute_installed_size_bytes", return_value=5000):
        assert format_computed_display("a", ["size-raw"], dag) == ["5000"]
