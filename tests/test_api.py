from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest

import pipdeptree
from pipdeptree import _RenderResult, _SummaryResult
from pipdeptree._computed import ComputedValues

if TYPE_CHECKING:
    from pytest_mock import MockerFixture

    from tests.conftest import MockDistMaker


@pytest.fixture
def patched_env_no_size(patched_env: None, mocker: MockerFixture) -> None:  # noqa: ARG001
    # Summary reads on-disk size via ComputedValues, which would look the mocked packages up in the real
    # environment; pin it so the summary metrics stay deterministic.
    mocker.patch.object(ComputedValues, "size_raw", 0)


@pytest.fixture
def patched_env(mocker: MockerFixture, make_mock_dist: MockDistMaker) -> None:
    pkgs = [
        make_mock_dist(name="a", version="1.0.0", requires=["b>=1.0"]),
        make_mock_dist(name="b", version="2.0.0"),
    ]
    mocker.patch("pipdeptree.__main__.get_installed_distributions", return_value=pkgs)


@pytest.mark.usefixtures("patched_env")
def test_render_returns_text_tree() -> None:
    out = pipdeptree.render()
    assert isinstance(out, str)
    assert "a==1.0.0" in out
    assert "b [required: >=1.0, installed: 2.0.0]" in out


@pytest.mark.usefixtures("patched_env")
def test_render_text_mimebundle_offers_mermaid_html_and_plain() -> None:
    out = pipdeptree.render()
    assert isinstance(out, _RenderResult)
    bundle = out._repr_mimebundle_()
    assert set(bundle) == {"text/vnd.mermaid", "text/html", "text/plain"}
    assert bundle["text/vnd.mermaid"].startswith("flowchart TD")
    assert bundle["text/html"].startswith("<pre")
    assert bundle["text/plain"] == str(out)


@pytest.mark.usefixtures("patched_env")
def test_render_text_mimebundle_respects_include() -> None:
    out = pipdeptree.render()
    assert isinstance(out, _RenderResult)
    bundle = out._repr_mimebundle_(include={"text/plain"})
    assert set(bundle) == {"text/plain"}


@pytest.mark.usefixtures("patched_env")
def test_render_json_has_no_rich_mimebundle() -> None:
    out = pipdeptree.render(output_format="json")
    assert not hasattr(out, "_repr_mimebundle_")


@pytest.mark.usefixtures("patched_env")
def test_render_json_returns_valid_json() -> None:
    payload = json.loads(pipdeptree.render(output_format="json"))
    assert {entry["package"]["key"] for entry in payload} == {"a", "b"}


@pytest.mark.usefixtures("patched_env")
def test_render_json_tree_returns_valid_json() -> None:
    payload = json.loads(pipdeptree.render(output_format="json-tree"))
    assert any(entry["key"] == "a" for entry in payload)


@pytest.mark.usefixtures("patched_env")
def test_render_mermaid() -> None:
    assert pipdeptree.render(output_format="mermaid").startswith("flowchart TD")


@pytest.mark.usefixtures("patched_env")
def test_render_dot_returns_graphviz_source() -> None:
    assert pipdeptree.render(output_format="dot").startswith("digraph {")


@pytest.mark.usefixtures("patched_env")
def test_render_packages_filter() -> None:
    assert pipdeptree.render(packages="b").strip() == "b==2.0.0"


@pytest.mark.usefixtures("patched_env")
def test_render_exclude_filter() -> None:
    out = pipdeptree.render(exclude="b")
    assert "b==2.0.0" not in out
    assert "a==1.0.0" in out


@pytest.mark.usefixtures("patched_env")
def test_render_reverse() -> None:
    assert pipdeptree.render(reverse=True).startswith("b==2.0.0")


@pytest.mark.usefixtures("patched_env")
def test_render_depth_limits_text_tree() -> None:
    out = pipdeptree.render(depth=0)
    assert "a==1.0.0" in out
    assert "required:" not in out


def test_render_passes_select_options_through(mocker: MockerFixture, make_mock_dist: MockDistMaker) -> None:
    discovery = mocker.patch(
        "pipdeptree.__main__.get_installed_distributions",
        return_value=[make_mock_dist(name="a", version="1.0.0")],
    )
    pipdeptree.render(python="/some/python", user_only=True)
    assert discovery.call_args.kwargs["interpreter"] == "/some/python"
    assert discovery.call_args.kwargs["user_only"] is True


def test_render_local_only_passed_through(mocker: MockerFixture, make_mock_dist: MockDistMaker) -> None:
    discovery = mocker.patch(
        "pipdeptree.__main__.get_installed_distributions",
        return_value=[make_mock_dist(name="a", version="1.0.0")],
    )
    pipdeptree.render(local_only=True)
    assert discovery.call_args.kwargs["local_only"] is True


def test_render_extras_passed_through(mocker: MockerFixture, make_mock_dist: MockDistMaker) -> None:
    spy = mocker.spy(pipdeptree.__main__.PackageDAG, "from_pkgs")
    mocker.patch(
        "pipdeptree.__main__.get_installed_distributions",
        return_value=[make_mock_dist(name="a", version="1.0.0")],
    )
    pipdeptree.render(extras=True)
    assert spy.call_args.kwargs["extras"] == "explicit"


def test_render_extras_mode_passed_through(mocker: MockerFixture, make_mock_dist: MockDistMaker) -> None:
    spy = mocker.spy(pipdeptree.__main__.PackageDAG, "from_pkgs")
    mocker.patch(
        "pipdeptree.__main__.get_installed_distributions",
        return_value=[make_mock_dist(name="a", version="1.0.0")],
    )
    pipdeptree.render(extras="active")
    assert spy.call_args.kwargs["extras"] == "active"


def test_render_invalid_filter_returns_empty(mocker: MockerFixture, make_mock_dist: MockDistMaker) -> None:
    mocker.patch(
        "pipdeptree.__main__.get_installed_distributions",
        return_value=[make_mock_dist(name="a", version="1.0.0")],
    )
    assert not pipdeptree.render(packages="does-not-exist")


def test_render_warnings_do_not_leak_by_default(
    mocker: MockerFixture,
    capsys: pytest.CaptureFixture[str],
    make_mock_dist: MockDistMaker,
) -> None:
    mocker.patch(
        "pipdeptree.__main__.get_installed_distributions",
        return_value=[make_mock_dist(name="a", version="1.0.0", requires=["missing>=1"])],
    )
    pipdeptree.render()
    assert not capsys.readouterr().err


@pytest.mark.usefixtures("patched_env_no_size")
def test_render_summary_text_has_html_mimebundle() -> None:
    out = pipdeptree.render(summary=True)
    assert isinstance(out, _SummaryResult)
    assert out.startswith("total packages:")
    bundle = out._repr_mimebundle_()
    assert set(bundle) == {"text/html", "text/plain"}
    assert bundle["text/html"].startswith("<table>")
    assert bundle["text/plain"] == str(out)


@pytest.mark.usefixtures("patched_env_no_size")
def test_render_summary_text_mimebundle_respects_include() -> None:
    out = pipdeptree.render(summary=True)
    assert isinstance(out, _SummaryResult)
    assert set(out._repr_mimebundle_(include={"text/plain"})) == {"text/plain"}


@pytest.mark.usefixtures("patched_env_no_size")
def test_render_summary_json_is_plain_str() -> None:
    out = pipdeptree.render(summary=True, output_format="json")
    assert not hasattr(out, "_repr_mimebundle_")
    assert json.loads(out)["total_packages"] == 2


@pytest.mark.usefixtures("patched_env_no_size")
def test_render_summary_rich_is_plain_str() -> None:
    out = pipdeptree.render(summary=True, output_format="rich")
    assert not hasattr(out, "_repr_mimebundle_")
    assert "environment summary" in out


@pytest.mark.usefixtures("patched_env")
def test_render_summary_rejects_tree_format() -> None:
    with pytest.raises(ValueError, match="summary output_format must be one of"):
        pipdeptree.render(summary=True, output_format="mermaid")


@pytest.mark.usefixtures("patched_env")
def test_render_unknown_output_format_raises() -> None:
    with pytest.raises(ValueError, match="unknown output_format 'xml'"):
        pipdeptree.render(output_format="xml")


@pytest.mark.usefixtures("patched_env")
def test_render_binary_graphviz_format_raises() -> None:
    with pytest.raises(ValueError, match="binary Graphviz formats"):
        pipdeptree.render(output_format="png")
