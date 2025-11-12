from __future__ import annotations

from math import inf
from typing import TYPE_CHECKING
from unittest.mock import ANY

import pytest

from pipdeptree.__main__ import main

if TYPE_CHECKING:
    from pytest_mock import MockerFixture


@pytest.mark.parametrize("option", [["--json"], ["--output", "json"]])
def test_json_routing(option: list[str], mocker: MockerFixture) -> None:
    render = mocker.patch("pipdeptree._render.render_json")
    main(option)
    render.assert_called_once_with(ANY)


@pytest.mark.parametrize("option", [["--json-tree"], ["--output", "json-tree"]])
def test_json_tree_routing(option: list[str], mocker: MockerFixture) -> None:
    render = mocker.patch("pipdeptree._render.render_json_tree")
    main(option)
    render.assert_called_once_with(ANY)


@pytest.mark.parametrize("option", [["--mermaid"], ["--output", "mermaid"]])
def test_mermaid_routing(option: list[str], mocker: MockerFixture) -> None:
    render = mocker.patch("pipdeptree._render.render_mermaid")
    main(option)
    render.assert_called_once_with(ANY)


@pytest.mark.parametrize("option", [["--graph-output", "dot"], ["--output", "graphviz-dot"]])
def test_grahpviz_routing(option: list[str], mocker: MockerFixture) -> None:
    render = mocker.patch("pipdeptree._render.render_graphviz")
    main(option)
    render.assert_called_once_with(ANY, output_format="dot", reverse=False)


@pytest.mark.parametrize("option", [[], ["--output", "text"]])
def test_text_routing(option: list[str], mocker: MockerFixture) -> None:
    render = mocker.patch("pipdeptree._render.render_text")
    main(option)
    render.assert_called_once_with(ANY, encoding="utf-8", max_depth=inf, list_all=False, include_license=False)


@pytest.mark.parametrize("option", [["--freeze"], ["--output", "freeze"]])
def test_freeze_routing(option: list[str], mocker: MockerFixture) -> None:
    render = mocker.patch("pipdeptree._render.render_freeze")
    main(option)
    render.assert_called_once_with(ANY, max_depth=inf, list_all=False)
