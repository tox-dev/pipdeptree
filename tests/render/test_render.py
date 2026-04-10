from __future__ import annotations

from math import inf
from typing import TYPE_CHECKING
from unittest.mock import ANY

import pytest

from pipdeptree.__main__ import main
from pipdeptree._cli import RenderContext

if TYPE_CHECKING:
    from pytest_mock import MockerFixture


@pytest.mark.parametrize(
    "option", [pytest.param(["--json"], id="flag"), pytest.param(["--output", "json"], id="output")]
)
def test_json_routing(option: list[str], mocker: MockerFixture) -> None:
    render = mocker.patch("pipdeptree._render.render_json")
    main(option)
    render.assert_called_once_with(ANY, context=RenderContext())


@pytest.mark.parametrize(
    "option",
    [pytest.param(["--json-tree"], id="flag"), pytest.param(["--output", "json-tree"], id="output")],
)
def test_json_tree_routing(option: list[str], mocker: MockerFixture) -> None:
    render = mocker.patch("pipdeptree._render.render_json_tree")
    main(option)
    render.assert_called_once_with(ANY, context=RenderContext())


@pytest.mark.parametrize(
    "option",
    [pytest.param(["--mermaid"], id="flag"), pytest.param(["--output", "mermaid"], id="output")],
)
def test_mermaid_routing(option: list[str], mocker: MockerFixture) -> None:
    render = mocker.patch("pipdeptree._render.render_mermaid")
    main(option)
    render.assert_called_once_with(ANY, context=RenderContext())


@pytest.mark.parametrize(
    "option",
    [pytest.param(["--graph-output", "dot"], id="flag"), pytest.param(["--output", "graphviz-dot"], id="output")],
)
def test_grahpviz_routing(option: list[str], mocker: MockerFixture) -> None:
    render = mocker.patch("pipdeptree._render.render_graphviz")
    main(option)
    render.assert_called_once_with(ANY, output_format="dot", reverse=False, max_depth=inf, context=RenderContext())


@pytest.mark.parametrize(
    "option",
    [pytest.param([], id="default"), pytest.param(["--output", "text"], id="output")],
)
def test_text_routing(option: list[str], mocker: MockerFixture) -> None:
    render = mocker.patch("pipdeptree._render.render_text")
    main(option)
    render.assert_called_once_with(ANY, encoding="utf-8", max_depth=inf, list_all=False, context=RenderContext())


@pytest.mark.parametrize(
    "option",
    [pytest.param(["--freeze"], id="flag"), pytest.param(["--output", "freeze"], id="output")],
)
def test_freeze_routing(option: list[str], mocker: MockerFixture) -> None:
    render = mocker.patch("pipdeptree._render.render_freeze")
    main(option)
    render.assert_called_once_with(ANY, max_depth=inf, list_all=False)


@pytest.mark.parametrize("option", [pytest.param(["--output", "rich"], id="output")])
def test_rich_routing(option: list[str], mocker: MockerFixture) -> None:
    render = mocker.patch("pipdeptree._render.render_rich_text")
    main(option)
    render.assert_called_once_with(ANY, max_depth=inf, list_all=False, context=RenderContext())
