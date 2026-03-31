from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest

from pipdeptree._cli import RenderContext
from pipdeptree._computed import ComputedValues
from pipdeptree._models import PackageDAG

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator
    from pathlib import Path
    from unittest.mock import Mock

    from pytest_mock import MockerFixture

    from tests.our_types import MockGraph


@pytest.mark.parametrize(
    ("total_bytes", "expected"),
    [
        pytest.param(0, "0 B", id="zero"),
        pytest.param(512, "512 B", id="bytes"),
        pytest.param(1024, "1.0 KB", id="kilobytes"),
        pytest.param(1536, "1.5 KB", id="fractional-kb"),
        pytest.param(1048576, "1.0 MB", id="megabytes"),
        pytest.param(1073741824, "1.0 GB", id="gigabytes"),
    ],
)
def test_size_formatting(total_bytes: int, expected: str, mocker: MockerFixture) -> None:
    dag = MagicMock(spec=PackageDAG)
    mocker.patch(
        "pipdeptree._computed.distribution",
        return_value=MagicMock(files=["f"], locate_file=lambda _: "/dev/null"),
    )
    mocker.patch.object(ComputedValues, "_file_size", return_value=total_bytes)
    assert ComputedValues("pkg", dag).size == expected


def test_size_bytes_no_files(mocker: MockerFixture) -> None:
    dag = MagicMock(spec=PackageDAG)
    mocker.patch("pipdeptree._computed.distribution", return_value=MagicMock(files=None))
    assert ComputedValues("some-pkg", dag).size_bytes is None


def test_size_bytes_with_files(tmp_path: Path, mocker: MockerFixture) -> None:
    (tmp_path / "file1.py").write_text("x" * 100)
    (tmp_path / "file2.py").write_text("y" * 200)
    mocker.patch(
        "pipdeptree._computed.distribution",
        return_value=MagicMock(files=["file1.py", "file2.py"], locate_file=lambda f: tmp_path / f),
    )
    dag = MagicMock(spec=PackageDAG)
    cv = ComputedValues("some-pkg", dag)
    assert cv.size_bytes == 300
    assert cv.size == "300 B"
    assert cv.size_raw == 300


def test_size_bytes_missing_file_on_disk(mocker: MockerFixture) -> None:
    dag = MagicMock(spec=PackageDAG)
    mocker.patch(
        "pipdeptree._computed.distribution",
        return_value=MagicMock(files=["missing.py"], locate_file=lambda _: "/nonexistent/path"),
    )
    assert ComputedValues("pkg", dag).size_bytes == 0


def test_unique_deps(mock_pkgs: Callable[[MockGraph], Iterator[Mock]]) -> None:
    graph: MockGraph = {
        ("a", "1.0"): [("c", [(">=", "1.0")])],
        ("b", "1.0"): [("d", [(">=", "1.0")])],
        ("c", "1.0"): [],
        ("d", "1.0"): [],
    }
    if dag := PackageDAG.from_pkgs(list(mock_pkgs(graph))):
        assert ComputedValues("a", dag).unique_deps == {"c"}
        assert ComputedValues("b", dag).unique_deps == {"d"}


def test_unique_deps_shared(mock_pkgs: Callable[[MockGraph], Iterator[Mock]]) -> None:
    graph: MockGraph = {
        ("a", "1.0"): [("c", [(">=", "1.0")])],
        ("b", "1.0"): [("c", [(">=", "1.0")])],
        ("c", "1.0"): [],
    }
    if dag := PackageDAG.from_pkgs(list(mock_pkgs(graph))):
        assert ComputedValues("a", dag).unique_deps == set()
        assert ComputedValues("b", dag).unique_deps == set()


def test_unique_deps_size(mock_pkgs: Callable[[MockGraph], Iterator[Mock]], mocker: MockerFixture) -> None:
    graph: MockGraph = {
        ("a", "1.0"): [("b", [(">=", "1.0")])],
        ("b", "1.0"): [],
    }
    dag = PackageDAG.from_pkgs(list(mock_pkgs(graph)))
    mocker.patch(
        "pipdeptree._computed.distribution",
        return_value=MagicMock(files=["f"], locate_file=lambda _: "/dev/null"),
    )
    mocker.patch.object(ComputedValues, "_file_size", return_value=2048)
    assert ComputedValues("a", dag).unique_deps_size == "2.0 KB"


def test_unique_deps_count_matches_names(mock_pkgs: Callable[[MockGraph], Iterator[Mock]]) -> None:
    dag = PackageDAG.from_pkgs(list(mock_pkgs({("a", "1.0"): [("b", [(">=", "1.0")])], ("b", "1.0"): []})))
    cv = ComputedValues("a", dag)
    assert cv.unique_deps_count == 1
    assert cv.unique_deps_names == ["b"]


def test_as_dict(mock_pkgs: Callable[[MockGraph], Iterator[Mock]], mocker: MockerFixture) -> None:
    graph: MockGraph = {
        ("a", "1.0"): [("b", [(">=", "1.0")])],
        ("b", "1.0"): [],
    }
    dag = PackageDAG.from_pkgs(list(mock_pkgs(graph)))
    mocker.patch("pipdeptree._computed.distribution", return_value=MagicMock(files=None))
    assert ComputedValues("a", dag).as_dict(["size", "unique-deps-count", "unique-deps-names"]) == {
        "size": "0 B",
        "unique_deps_count": 1,
        "unique_deps_names": ["b"],
    }


def test_as_dict_size_raw(mock_pkgs: Callable[[MockGraph], Iterator[Mock]], mocker: MockerFixture) -> None:
    dag = PackageDAG.from_pkgs(list(mock_pkgs({("a", "1.0"): []})))
    mocker.patch(
        "pipdeptree._computed.distribution",
        return_value=MagicMock(files=["f"], locate_file=lambda _: "/dev/null"),
    )
    mocker.patch.object(ComputedValues, "_file_size", return_value=123456)
    assert ComputedValues("a", dag).as_dict(["size-raw"]) == {"size_raw": 123456}


def test_as_dict_unknown_field(mock_pkgs: Callable[[MockGraph], Iterator[Mock]]) -> None:
    dag = PackageDAG.from_pkgs(list(mock_pkgs({("a", "1.0"): []})))
    assert ComputedValues("a", dag).as_dict(["nonexistent"]) == {}


def test_size_computed_once(mocker: MockerFixture) -> None:
    dag = MagicMock(spec=PackageDAG)
    mock_dist = mocker.patch("pipdeptree._computed.distribution", return_value=MagicMock(files=None))
    cv = ComputedValues("a", dag)
    assert cv.size_bytes is None
    assert cv.size == "0 B"
    assert cv.size_raw == 0
    mock_dist.assert_called_once()


def test_format_display(mock_pkgs: Callable[[MockGraph], Iterator[Mock]], mocker: MockerFixture) -> None:
    graph: MockGraph = {
        ("a", "1.0"): [("b", [(">=", "1.0")])],
        ("b", "1.0"): [],
    }
    dag = PackageDAG.from_pkgs(list(mock_pkgs(graph)))
    mocker.patch(
        "pipdeptree._computed.distribution",
        return_value=MagicMock(files=["f"], locate_file=lambda _: "/dev/null"),
    )
    mocker.patch.object(ComputedValues, "_file_size", return_value=100)
    assert ComputedValues("a", dag).format_display(["size", "unique-deps-count", "unique-deps-names"]) == [
        "100 B",
        "1 unique deps",
        "unique: b",
    ]


def test_format_display_unique_deps_size(
    mock_pkgs: Callable[[MockGraph], Iterator[Mock]], mocker: MockerFixture
) -> None:
    graph: MockGraph = {
        ("a", "1.0"): [("b", [(">=", "1.0")])],
        ("b", "1.0"): [],
    }
    dag = PackageDAG.from_pkgs(list(mock_pkgs(graph)))
    mocker.patch(
        "pipdeptree._computed.distribution",
        return_value=MagicMock(files=["f"], locate_file=lambda _: "/dev/null"),
    )
    mocker.patch.object(ComputedValues, "_file_size", return_value=1024)
    assert ComputedValues("a", dag).format_display(["unique-deps-size"]) == ["unique size: 1.0 KB"]


def test_format_display_hides_zero_unique_deps(mock_pkgs: Callable[[MockGraph], Iterator[Mock]]) -> None:
    dag = PackageDAG.from_pkgs(list(mock_pkgs({("a", "1.0"): []})))
    assert ComputedValues("a", dag).format_display(["unique-deps-count", "unique-deps-names", "unique-deps-size"]) == []


def test_format_display_size_raw(mock_pkgs: Callable[[MockGraph], Iterator[Mock]], mocker: MockerFixture) -> None:
    dag = PackageDAG.from_pkgs(list(mock_pkgs({("a", "1.0"): []})))
    mocker.patch(
        "pipdeptree._computed.distribution",
        return_value=MagicMock(files=["f"], locate_file=lambda _: "/dev/null"),
    )
    mocker.patch.object(ComputedValues, "_file_size", return_value=5000)
    assert ComputedValues("a", dag).format_display(["size-raw"]) == ["5000"]


def test_build_node_extra_label_inactive() -> None:
    dag = MagicMock(spec=PackageDAG)
    assert not RenderContext().build_node_extra_label("a", dag, ", ")


def test_build_node_extra_label_metadata(
    mock_pkgs: Callable[[MockGraph], Iterator[Mock]], mocker: MockerFixture
) -> None:
    graph: MockGraph = {("a", "1.0"): []}
    dag = PackageDAG.from_pkgs(list(mock_pkgs(graph)))
    mocker.patch("pipdeptree._models.package.Package.get_metadata_values", return_value=["A package"])
    ctx = RenderContext(metadata=["Summary"])
    assert ctx.build_node_extra_label("a", dag, ", ") == "A package"


def test_build_node_extra_label_computed(
    mock_pkgs: Callable[[MockGraph], Iterator[Mock]], mocker: MockerFixture
) -> None:
    graph: MockGraph = {("a", "1.0"): [("b", [(">=", "1.0")])], ("b", "1.0"): []}
    dag = PackageDAG.from_pkgs(list(mock_pkgs(graph)))
    mocker.patch("pipdeptree._computed.distribution", return_value=MagicMock(files=None))
    ctx = RenderContext(computed=["size"])
    assert ctx.build_node_extra_label("a", dag, ", ") == "size: 0 B"


def test_build_node_extra_label_license(
    mock_pkgs: Callable[[MockGraph], Iterator[Mock]], mocker: MockerFixture
) -> None:
    graph: MockGraph = {("a", "1.0"): []}
    dag = PackageDAG.from_pkgs(list(mock_pkgs(graph)))
    mocker.patch("pipdeptree._models.package.Package.licenses", return_value="(MIT)")
    ctx = RenderContext(metadata=["license"])
    assert ctx.build_node_extra_label("a", dag, ", ") == "MIT License"


def test_build_node_extra_label_missing_metadata_field(
    mock_pkgs: Callable[[MockGraph], Iterator[Mock]], mocker: MockerFixture
) -> None:
    graph: MockGraph = {("a", "1.0"): []}
    dag = PackageDAG.from_pkgs(list(mock_pkgs(graph)))
    mocker.patch("pipdeptree._models.package.Package.get_metadata_values", return_value=[])
    ctx = RenderContext(metadata=["Author"])
    assert not ctx.build_node_extra_label("a", dag, ", ")
