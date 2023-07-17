from __future__ import annotations

from math import inf
from typing import TYPE_CHECKING
from unittest.mock import ANY

from pipdeptree.__main__ import main

if TYPE_CHECKING:
    from pytest_mock import MockerFixture


def test_json_routing(mocker: MockerFixture) -> None:
    render = mocker.patch("pipdeptree._render.render_json")
    main(["--json"])
    render.assert_called_once_with(ANY)


def test_json_tree_routing(mocker: MockerFixture) -> None:
    render = mocker.patch("pipdeptree._render.render_json_tree")
    main(["--json-tree"])
    render.assert_called_once_with(ANY)


def test_mermaid_routing(mocker: MockerFixture) -> None:
    render = mocker.patch("pipdeptree._render.render_mermaid")
    main(["--mermaid"])
    render.assert_called_once_with(ANY)


def test_grahpviz_routing(mocker: MockerFixture) -> None:
    render = mocker.patch("pipdeptree._render.render_graphviz")
    main(["--graph-output", "dot"])
    render.assert_called_once_with(ANY, output_format="dot", reverse=False)


def test_text_routing(mocker: MockerFixture) -> None:
    render = mocker.patch("pipdeptree._render.render_text")
    main([])
    render.assert_called_once_with(ANY, encoding="utf-8", frozen=False, list_all=False, max_depth=inf)
