from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest

from pipdeptree._cli import Options, RenderContext
from pipdeptree._render import render

if TYPE_CHECKING:
    from pipdeptree._models import PackageDAG


def _options(*, command: str | None, output_format: str) -> Options:
    options = Options()
    options.command = command
    options.output_format = output_format
    options.summary = False
    options.context = RenderContext()
    options.depth = float("inf")
    options.encoding = "utf-8"
    options.all = True
    options.reverse = False
    return options


@pytest.mark.parametrize(
    "command", [pytest.param("from-index", id="from-index"), pytest.param("from-lock", id="from-lock")]
)
def test_render_text_candidate(command: str, example_dag: PackageDAG, capsys: pytest.CaptureFixture[str]) -> None:
    render(_options(command=command, output_format="text"), example_dag)
    out = capsys.readouterr().out
    assert "[candidate: 2.3.1]" in out
    assert "required:" not in out
    assert "installed:" not in out


def test_render_text_default_unchanged(example_dag: PackageDAG, capsys: pytest.CaptureFixture[str]) -> None:
    render(_options(command=None, output_format="text"), example_dag)
    out = capsys.readouterr().out
    assert "[required: >=2.0.0, installed: 2.3.1]" in out
    assert "candidate:" not in out


def test_render_json_candidate(example_dag: PackageDAG, capsys: pytest.CaptureFixture[str]) -> None:
    render(_options(command="from-index", output_format="json"), example_dag)
    data = json.loads(capsys.readouterr().out)
    dep = next(d for entry in data for d in entry["dependencies"])
    assert "candidate_version" in dep
    assert "required_version" not in dep
    assert "installed_version" not in dep


def test_render_json_default_unchanged(example_dag: PackageDAG, capsys: pytest.CaptureFixture[str]) -> None:
    render(_options(command=None, output_format="json"), example_dag)
    data = json.loads(capsys.readouterr().out)
    dep = next(d for entry in data for d in entry["dependencies"])
    assert "required_version" in dep
    assert "installed_version" in dep
    assert "candidate_version" not in dep


def test_render_json_tree_candidate(example_dag: PackageDAG, capsys: pytest.CaptureFixture[str]) -> None:
    render(_options(command="from-index", output_format="json-tree"), example_dag)
    data = json.loads(capsys.readouterr().out)
    dep = next(d for entry in data for d in entry["dependencies"])
    assert "candidate_version" in dep
    assert "required_version" not in dep
    assert "installed_version" not in dep


def test_render_rich_candidate(example_dag: PackageDAG, capsys: pytest.CaptureFixture[str]) -> None:
    render(_options(command="from-index", output_format="rich"), example_dag)
    out = capsys.readouterr().out
    assert "candidate:" in out
    assert "required:" not in out
    assert "installed:" not in out
