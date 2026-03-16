from __future__ import annotations

from math import inf
from typing import TYPE_CHECKING

import pytest

from pipdeptree._render.freeze import render_freeze

if TYPE_CHECKING:
    from pipdeptree._models.dag import PackageDAG


@pytest.fixture
def patch_pip_adapter(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Patch parser functions to return None, forcing standard name==version format.

    This ensures distributions are always formatted as "name==version" regardless
    of whether they are editable or direct URL installs.
    """
    monkeypatch.setattr("pipdeptree._parser.format.find_egg_link", lambda _: None)
    monkeypatch.setattr("pipdeptree._parser.format.get_direct_url", lambda _: None)


@pytest.mark.parametrize(
    ("list_all", "expected_output"),
    [
        (
            True,
            [
                "a==3.4.0",
                "  b==2.3.1",
                "    d==2.35",
                "      e==0.12.1",
                "  c==5.10.0",
                "    d==2.35",
                "      e==0.12.1",
                "    e==0.12.1",
                "b==2.3.1",
                "  d==2.35",
                "    e==0.12.1",
                "c==5.10.0",
                "  d==2.35",
                "    e==0.12.1",
                "  e==0.12.1",
                "d==2.35",
                "  e==0.12.1",
                "e==0.12.1",
                "f==3.1",
                "  b==2.3.1",
                "    d==2.35",
                "      e==0.12.1",
                "g==6.8.3rc1",
                "  e==0.12.1",
                "  f==3.1",
                "    b==2.3.1",
                "      d==2.35",
                "        e==0.12.1",
            ],
        ),
        (
            False,
            [
                "a==3.4.0",
                "  b==2.3.1",
                "    d==2.35",
                "      e==0.12.1",
                "  c==5.10.0",
                "    d==2.35",
                "      e==0.12.1",
                "    e==0.12.1",
                "g==6.8.3rc1",
                "  e==0.12.1",
                "  f==3.1",
                "    b==2.3.1",
                "      d==2.35",
                "        e==0.12.1",
            ],
        ),
    ],
)
@pytest.mark.usefixtures("patch_pip_adapter")
def test_render_freeze(
    example_dag: PackageDAG,
    capsys: pytest.CaptureFixture[str],
    list_all: bool,
    expected_output: list[str],
) -> None:
    render_freeze(example_dag, max_depth=inf, list_all=list_all)
    captured = capsys.readouterr()
    assert "\n".join(expected_output).strip() == captured.out.strip()


@pytest.mark.parametrize(
    ("depth", "expected_output"),
    [
        (
            0,
            [
                "a==3.4.0",
                "b==2.3.1",
                "c==5.10.0",
                "d==2.35",
                "e==0.12.1",
                "f==3.1",
                "g==6.8.3rc1",
            ],
        ),
        (
            2,
            [
                "a==3.4.0",
                "  b==2.3.1",
                "    d==2.35",
                "  c==5.10.0",
                "    d==2.35",
                "    e==0.12.1",
                "b==2.3.1",
                "  d==2.35",
                "    e==0.12.1",
                "c==5.10.0",
                "  d==2.35",
                "    e==0.12.1",
                "  e==0.12.1",
                "d==2.35",
                "  e==0.12.1",
                "e==0.12.1",
                "f==3.1",
                "  b==2.3.1",
                "    d==2.35",
                "g==6.8.3rc1",
                "  e==0.12.1",
                "  f==3.1",
                "    b==2.3.1",
            ],
        ),
    ],
)
@pytest.mark.usefixtures("patch_pip_adapter")
def test_render_freeze_given_depth(
    example_dag: PackageDAG,
    capsys: pytest.CaptureFixture[str],
    depth: int,
    expected_output: list[str],
) -> None:
    render_freeze(example_dag, max_depth=depth)
    captured = capsys.readouterr()
    assert "\n".join(expected_output).strip() == captured.out.strip()
