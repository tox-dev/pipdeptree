from __future__ import annotations

import json
import sys
from typing import TYPE_CHECKING, Any

import pytest

from pipdeptree._computed import ComputedValues
from pipdeptree._models.dag import PackageDAG
from pipdeptree._render.summary import render_summary, summary_html
from pipdeptree._synthetic_dist import SyntheticDistribution

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator
    from importlib.metadata import Distribution
    from unittest.mock import Mock

    from pytest_mock import MockerFixture

    from pipdeptree._models.package import RenderMode
    from tests.conftest import MockDistMaker
    from tests.our_types import MockGraph

_RESOLVED_NOTE = "n/a (resolved from index/lock - package metadata unavailable)"


@pytest.fixture
def zero_size(mocker: MockerFixture) -> None:
    # Summary totals stat real files via ComputedValues; pin the per-package size so the metrics stay deterministic.
    mocker.patch.object(ComputedValues, "size_raw", 0)


def _text_rows(out: str) -> dict[str, str]:
    return {label.strip(): value.strip() for label, _, value in (line.partition(":") for line in out.splitlines())}


def _summary_text(
    dag: PackageDAG, capsys: pytest.CaptureFixture[str], *, mode: RenderMode = "default"
) -> dict[str, str]:
    render_summary(dag, mode=mode)
    return _text_rows(capsys.readouterr().out)


def _summary_json(
    dag: PackageDAG, capsys: pytest.CaptureFixture[str], *, mode: RenderMode = "default"
) -> dict[str, Any]:
    render_summary(dag, mode=mode, style="json")
    return json.loads(capsys.readouterr().out)


@pytest.mark.parametrize(
    ("graph", "expected"),
    [
        pytest.param(
            {
                ("a", "1.0.0"): [("b", [(">=", "2.0.0")]), ("c", [(">=", "1.0.0")])],
                ("b", "2.0.0"): [("c", [(">=", "1.0.0")])],
                ("c", "1.0.0"): [],
            },
            {"total_packages": 3, "direct_dependencies": 1, "transitive_dependencies": 2, "max_depth": 3},
            id="chain",
        ),
        pytest.param(
            {("a", "1.0.0"): [("b", [])], ("b", "1.0.0"): [("a", [])]},
            {"total_packages": 2, "direct_dependencies": 0, "max_depth": 2, "cyclic_dependencies": 2},
            id="cycle-terminates",
        ),
    ],
)
def test_structural_metrics(
    graph: MockGraph,
    expected: dict[str, int],
    mock_pkgs: Callable[[MockGraph], Iterator[Mock]],
    capsys: pytest.CaptureFixture[str],
) -> None:
    dag = PackageDAG.from_pkgs(list(mock_pkgs(graph)))

    data = _summary_json(dag, capsys, mode="resolved")

    assert {key: data[key] for key in expected} == expected


def test_resolved_json_drops_installed_tier(
    mock_pkgs: Callable[[MockGraph], Iterator[Mock]], capsys: pytest.CaptureFixture[str]
) -> None:
    dag = PackageDAG.from_pkgs(list(mock_pkgs({("a", "1.0.0"): [("b", [])], ("b", "2.0.0"): []})))

    assert _summary_json(dag, capsys, mode="resolved") == {
        "total_packages": 2,
        "direct_dependencies": 1,
        "transitive_dependencies": 1,
        "max_depth": 2,
        "cyclic_dependencies": 0,
    }


def test_resolved_text_marks_metadata_unavailable(
    mock_pkgs: Callable[[MockGraph], Iterator[Mock]], capsys: pytest.CaptureFixture[str]
) -> None:
    dag = PackageDAG.from_pkgs(list(mock_pkgs({("a", "1.0.0"): []})))

    rows = _summary_text(dag, capsys, mode="resolved")

    assert rows["licenses"] == _RESOLVED_NOTE
    assert "total size" not in rows
    assert "copyleft licenses" not in rows


def test_empty_tree_json(capsys: pytest.CaptureFixture[str]) -> None:
    data = _summary_json(PackageDAG({}), capsys)

    assert data["total_packages"] == 0
    assert data["max_depth"] == 0
    assert data["licenses"]["breakdown"] == {}
    assert data["total_size"] == "0 B"
    assert data["min_requires_python"] == "n/a"


def test_empty_tree_text(capsys: pytest.CaptureFixture[str]) -> None:
    rows = _summary_text(PackageDAG({}), capsys)

    assert rows["licenses"] == "none"
    assert rows["copyleft licenses"] == "no"
    assert rows["total size"] == "0 B"


@pytest.mark.usefixtures("zero_size")
@pytest.mark.parametrize(
    ("build", "expected"),
    [
        pytest.param(
            lambda m: [m("a", "1.0.0", requires=["b>=2.0.0", "absent-pkg-xyz"]), m("b", "1.0.0")],
            {"conflicting_dependencies": {"packages": 1, "edges": 2}, "missing_dependencies": 1},
            id="conflict-and-missing",
        ),
        pytest.param(
            lambda m: [m("a", "1.0.0", license_expression="MIT"), m("b", "1.0.0")],
            {"licenses": {"breakdown": {"(MIT)": 1, "(N/A)": 1}, "unknown": 1, "copyleft": False}},
            id="license-breakdown",
        ),
        pytest.param(
            lambda m: [m("a", "1.0.0", license_expression="GPL-3.0-or-later")],
            {"licenses": {"breakdown": {"(GPL-3.0-or-later)": 1}, "unknown": 0, "copyleft": True}},
            id="copyleft",
        ),
        pytest.param(
            lambda m: [m("a", "1.0.0", requires_python=[">=3.8,<4.0"]), m("b", "1.0.0", requires_python=[">=3.10"])],
            {"min_requires_python": "3.10"},
            id="requires-python-floor",
        ),
        pytest.param(
            lambda m: [
                m("a", "1.0.0", requires_python=["garbage"]),
                m("b", "1.0.0", requires_python=["==3.*"]),
                m("c", "1.0.0", requires_python=[">=3.8", ">=3.9"]),
            ],
            {"min_requires_python": "n/a"},
            id="requires-python-unparsable",
        ),
    ],
)
def test_default_metrics(
    build: Callable[[MockDistMaker], list[Distribution]],
    expected: dict[str, Any],
    make_mock_dist: MockDistMaker,
    capsys: pytest.CaptureFixture[str],
) -> None:
    dag = PackageDAG.from_pkgs(build(make_mock_dist))

    data = _summary_json(dag, capsys)

    assert {key: data[key] for key in expected} == expected


def test_default_size_total(
    capsys: pytest.CaptureFixture[str], make_mock_dist: MockDistMaker, mocker: MockerFixture
) -> None:
    mocker.patch.object(ComputedValues, "size_raw", 512)
    dag = PackageDAG.from_pkgs([make_mock_dist("a", "1.0.0"), make_mock_dist("b", "1.0.0")])

    data = _summary_json(dag, capsys)

    assert data["total_size_raw"] == 1024
    assert data["total_size"] == "1.0 KB"


@pytest.mark.usefixtures("zero_size")
def test_default_text_tier(capsys: pytest.CaptureFixture[str], make_mock_dist: MockDistMaker) -> None:
    dag = PackageDAG.from_pkgs([make_mock_dist("a", "1.0.0", license_expression="MIT")])

    rows = _summary_text(dag, capsys)

    assert rows["licenses"] == "(MIT): 1"
    assert rows["conflicting dependencies"] == "0 (0 edges)"


def test_from_lock_synthetic_tree(capsys: pytest.CaptureFixture[str]) -> None:
    pkgs: list[Distribution] = [
        SyntheticDistribution("a", "1.0.0", ("b==2.0.0",)),
        SyntheticDistribution("b", "2.0.0", ()),
    ]

    rows = _summary_text(PackageDAG.from_pkgs(pkgs), capsys, mode="resolved")

    assert rows["total packages"] == "2"
    assert rows["max depth"] == "2"
    assert rows["missing dependencies"] == _RESOLVED_NOTE


@pytest.mark.usefixtures("zero_size")
@pytest.mark.parametrize(
    ("mode", "needle"),
    [
        pytest.param("default", "total packages", id="default"),
        pytest.param("resolved", "n/a (resolved", id="resolved"),
    ],
)
def test_rich_style(
    mode: RenderMode, needle: str, make_mock_dist: MockDistMaker, capsys: pytest.CaptureFixture[str]
) -> None:
    dag = PackageDAG.from_pkgs([make_mock_dist("a", "1.0.0", requires=["b"]), make_mock_dist("b", "1.0.0")])

    render_summary(dag, mode=mode, style="rich")

    out = capsys.readouterr().out
    assert "environment summary" in out
    assert needle in out


def test_rich_style_missing_import(mock_pkgs: Callable[[MockGraph], Iterator[Mock]], mocker: MockerFixture) -> None:
    mocker.patch.dict(sys.modules, {"rich": None, "rich.console": None, "rich.table": None})
    dag = PackageDAG.from_pkgs(list(mock_pkgs({("a", "1.0.0"): []})))

    with pytest.raises(SystemExit) as exc_info:
        render_summary(dag, mode="resolved", style="rich")

    assert exc_info.value.code == 1


def test_summary_html_table(mock_pkgs: Callable[[MockGraph], Iterator[Mock]]) -> None:
    dag = PackageDAG.from_pkgs(list(mock_pkgs({("a", "1.0.0"): [("b", [])], ("b", "2.0.0"): []})))

    html = summary_html(dag, mode="resolved")

    assert html.startswith("<table>")
    assert "<td>total packages</td><td>2</td>" in html
