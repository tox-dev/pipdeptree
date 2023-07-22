from __future__ import annotations

import pytest

from pipdeptree._cli import build_parser, get_options


def test_parser_default() -> None:
    parser = build_parser()
    args = parser.parse_args([])
    assert not args.json
    assert args.output_format is None


def test_parser_j() -> None:
    parser = build_parser()
    args = parser.parse_args(["-j"])
    assert args.json
    assert args.output_format is None


def test_parser_json() -> None:
    parser = build_parser()
    args = parser.parse_args(["--json"])
    assert args.json
    assert args.output_format is None


def test_parser_json_tree() -> None:
    parser = build_parser()
    args = parser.parse_args(["--json-tree"])
    assert args.json_tree
    assert not args.json
    assert args.output_format is None


def test_parser_mermaid() -> None:
    parser = build_parser()
    args = parser.parse_args(["--mermaid"])
    assert args.mermaid
    assert not args.json
    assert args.output_format is None


def test_parser_pdf() -> None:
    parser = build_parser()
    args = parser.parse_args(["--graph-output", "pdf"])
    assert args.output_format == "pdf"
    assert not args.json


def test_parser_svg() -> None:
    parser = build_parser()
    args = parser.parse_args(["--graph-output", "svg"])
    assert args.output_format == "svg"
    assert not args.json


@pytest.mark.parametrize(
    ("should_be_error", "depth_arg", "expected_value"),
    [
        (True, ["-d", "-1"], None),
        (True, ["--depth", "string"], None),
        (False, ["-d", "0"], 0),
        (False, ["--depth", "8"], 8),
        (False, [], float("inf")),
    ],
)
def test_parser_depth(should_be_error: bool, depth_arg: list[str], expected_value: None | int | float) -> None:
    parser = build_parser()

    if should_be_error:
        with pytest.raises(SystemExit):
            parser.parse_args(depth_arg)
    else:
        args = parser.parse_args(depth_arg)
        assert args.depth == expected_value


@pytest.mark.parametrize(
    "args",
    [
        pytest.param(["--exclude", "py", "--all"], id="exclude-all"),
        pytest.param(["-e", "py", "--packages", "py2"], id="exclude-packages"),
        pytest.param(["-e", "py", "-p", "py2", "-a"], id="exclude-packages-all"),
    ],
)
def test_parser_get_options_exclude_combine_not_supported(args: list[str], capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit, match="2"):
        get_options(args)

    out, err = capsys.readouterr()
    assert not out
    assert "cannot use --exclude with --packages or --all" in err


def test_parser_get_options_exclude_only() -> None:
    parsed_args = get_options(["--exclude", "py"])
    assert parsed_args.exclude == "py"
