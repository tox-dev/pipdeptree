from __future__ import annotations

import pytest

from pipdeptree._cli import build_parser, get_options


def test_get_options_default() -> None:
    get_options([])


@pytest.mark.parametrize("flag", ["-j", "--json"])
def test_get_options_json(flag: str) -> None:
    options = get_options([flag])
    assert options.json
    assert options.output_format == "json"


def test_get_options_json_tree() -> None:
    options = get_options(["--json-tree"])
    assert options.json_tree
    assert not options.json
    assert options.output_format == "json-tree"


def test_get_options_mermaid() -> None:
    options = get_options(["--mermaid"])
    assert options.mermaid
    assert options.output_format == "mermaid"


def test_get_options_pdf() -> None:
    options = get_options(["--graph-output", "pdf"])
    assert options.graphviz_format == "pdf"
    assert options.output_format == "graphviz-pdf"


def test_get_options_svg() -> None:
    options = get_options(["--graph-output", "svg"])
    assert options.graphviz_format == "svg"
    assert options.output_format == "graphviz-svg"


@pytest.mark.parametrize(("fmt"), ["freeze", "json", "json-tree", "mermaid", "graphviz-png"])
def test_get_options_output_format(fmt: str) -> None:
    options = get_options(["-o", fmt])
    assert options.output_format == fmt


def test_get_options_output_format_that_does_not_exist(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit, match="2"):
        get_options(["-o", "i-dont-exist"])

    out, err = capsys.readouterr()
    assert not out
    assert 'i-dont-exist" is not a known output format.' in err


def test_get_options_license_and_freeze_together_not_supported(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit, match="2"):
        get_options(["--license", "--freeze"])

    out, err = capsys.readouterr()
    assert not out
    assert "cannot use --license with --freeze" in err


@pytest.mark.parametrize(
    "args",
    [
        pytest.param(["--path", "/random/path", "--local-only"], id="path-with-local"),
        pytest.param(["--path", "/random/path", "--user-only"], id="path-with-user"),
    ],
)
def test_get_options_path_with_either_local_or_user_not_supported(
    args: list[str], capsys: pytest.CaptureFixture[str]
) -> None:
    with pytest.raises(SystemExit, match="2"):
        get_options(args)

    out, err = capsys.readouterr()
    assert not out
    assert "cannot use --path with --user-only or --local-only" in err


def test_get_options_exclude_dependencies_without_exclude(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit, match="2"):
        get_options(["--exclude-dependencies"])

    out, err = capsys.readouterr()
    assert not out
    assert "must use --exclude-dependencies with --exclude" in err


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
def test_parser_depth(should_be_error: bool, depth_arg: list[str], expected_value: float | None) -> None:
    parser = build_parser()

    if should_be_error:
        with pytest.raises(SystemExit):
            parser.parse_args(depth_arg)
    else:
        args = parser.parse_args(depth_arg)
        assert args.depth == expected_value


@pytest.mark.parametrize(
    "warning",
    [
        "silence",
        "suppress",
        "fail",
    ],
)
def test_parse_warn_option_normal(warning: str) -> None:
    options = get_options(["-w", warning])
    assert options.warn == warning

    options = get_options(["--warn", warning])
    assert options.warn == warning


def test_parse_warn_option_invalid() -> None:
    with pytest.raises(SystemExit, match="2"):
        get_options(["--warn", "non-existent-warning-type"])
