from __future__ import annotations

import pytest

from pipdeptree._cli import build_parser, get_options, parse_packages


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


@pytest.mark.parametrize("fmt", ["text", "rich", "json"])
def test_get_options_summary_allows_styles(fmt: str) -> None:
    options = get_options(["--summary", "-o", fmt])
    assert options.summary
    assert options.output_format == fmt


def test_get_options_summary_default_text() -> None:
    options = get_options(["--summary"])
    assert options.summary
    assert options.output_format == "text"


@pytest.mark.parametrize("fmt", ["mermaid", "json-tree", "freeze", "graphviz-png"])
def test_get_options_summary_rejects_tree_formats(fmt: str, capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit, match="2"):
        get_options(["--summary", "-o", fmt])

    assert "--summary supports only -o json, rich, text" in capsys.readouterr().err


@pytest.mark.parametrize(("alias", "canonical"), [("i", "from-index"), ("l", "from-lock")])
def test_get_options_subcommand_aliases(alias: str, canonical: str) -> None:
    args = [alias, "req"] if canonical == "from-index" else [alias, "pylock.toml"]
    options = get_options(args)
    assert options.command == canonical


def test_get_options_license_deprecated() -> None:
    with pytest.warns(DeprecationWarning, match="--license is deprecated"):
        options = get_options(["--license"])
    assert options.metadata == ["license"]
    assert options.context.metadata == ["license"]


def test_get_options_license_and_metadata_license_conflict(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit, match="2"):
        get_options(["--license", "--metadata", "license"])
    out, err = capsys.readouterr()
    assert not out
    assert "cannot use --license with --metadata license" in err


def test_get_options_metadata() -> None:
    options = get_options(["--metadata", "license,summary"])
    assert options.metadata == ["license", "summary"]
    assert options.context.metadata == ["license", "summary"]


def test_get_options_metadata_dedup() -> None:
    options = get_options(["--metadata", "name,name"])
    assert options.metadata == ["name"]
    assert options.context.metadata == ["name"]


def test_get_options_computed() -> None:
    options = get_options(["--computed", "size,unique-deps-count"])
    assert options.computed == ["size", "unique-deps-count"]
    assert options.context.computed == ["size", "unique-deps-count"]


def test_get_options_invalid_computed(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit, match="2"):
        get_options(["--computed", "invalid-field"])
    out, err = capsys.readouterr()
    assert not out
    assert "invalid --computed values: invalid-field" in err


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


def test_get_options_default_has_no_subcommand() -> None:
    options = get_options([])
    assert options.command is None
    assert options.requirement == []
    assert options.requirements is None
    assert options.pyproject is None


def test_get_options_default_top_level_flag_still_works() -> None:
    options = get_options(["-o", "json"])
    assert options.command is None
    assert options.output_format == "json"


@pytest.mark.parametrize(
    "requirements",
    [
        pytest.param(["fastapi<=0.115.2"], id="single"),
        pytest.param(["fastapi", "starlette"], id="multiple"),
    ],
)
def test_get_options_from_index_requirements(requirements: list[str]) -> None:
    options = get_options(["from-index", *requirements])
    assert options.command == "from-index"
    assert options.requirement == requirements


def test_get_options_from_index_accumulates_file_flags() -> None:
    options = get_options(["from-index", "--requirements", "r.txt", "--pyproject", "p.toml"])
    assert options.command == "from-index"
    assert options.requirement == []
    assert options.requirements == ["r.txt"]
    assert options.pyproject == ["p.toml"]


def test_get_options_from_index_requires_a_source(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit, match="2"):
        get_options(["from-index"])
    out, err = capsys.readouterr()
    assert not out
    assert "from-index needs at least one REQUIREMENT, --requirements FILE, or --pyproject FILE" in err


def test_get_options_from_index_shares_render_flags() -> None:
    options = get_options(["from-index", "fastapi", "-o", "json"])
    assert options.command == "from-index"
    assert options.requirement == ["fastapi"]
    assert options.output_format == "json"


def test_get_options_from_index_keeps_extras() -> None:
    options = get_options(["from-index", "fastapi", "-x", "active"])
    assert options.command == "from-index"
    assert options.extras == "active"


def test_get_options_from_index_defaults_installed_metadata_options() -> None:
    options = get_options(["from-index", "fastapi"])
    assert options.license is False
    assert options.metadata == []
    assert options.computed == []
    assert options.context.active is False


@pytest.mark.parametrize(
    "args",
    [
        pytest.param(["--license"], id="license"),
        pytest.param(["--metadata", "license"], id="metadata"),
        pytest.param(["--computed", "size"], id="computed"),
    ],
)
def test_get_options_from_index_rejects_installed_metadata_options(
    args: list[str], capsys: pytest.CaptureFixture[str]
) -> None:
    with pytest.raises(SystemExit, match="2"):
        get_options(["from-index", "fastapi", *args])
    out, err = capsys.readouterr()
    assert not out
    assert "unrecognized arguments" in err


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


@pytest.mark.parametrize(
    ("args", "expected"),
    [
        (["-x"], "explicit"),
        (["--extras"], "explicit"),
        (["--extras", "explicit"], "explicit"),
        (["--extras", "active"], "active"),
        (["--extras", "none"], "none"),
    ],
)
def test_get_options_extras(args: list[str], expected: str) -> None:
    options = get_options(args)
    assert options.extras == expected


def test_get_options_extras_default() -> None:
    options = get_options([])
    assert options.extras == "explicit"


def test_get_options_extras_invalid(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit, match="2"):
        get_options(["--extras", "bogus"])
    out, err = capsys.readouterr()
    assert not out
    assert "invalid choice: 'bogus'" in err


@pytest.mark.parametrize(
    ("value", "names", "requested_extras"),
    [
        pytest.param("foo", ["foo"], {}, id="plain"),
        pytest.param("foo[bar]", ["foo"], {"foo": {"bar"}}, id="single-extra"),
        pytest.param("foo[bar,baz]", ["foo"], {"foo": {"bar", "baz"}}, id="multiple-extras"),
        pytest.param("foo[bar],qux", ["foo", "qux"], {"foo": {"bar"}}, id="mixed-entries"),
        pytest.param("foo[]", ["foo"], {}, id="empty-extras"),
        pytest.param("pytest*[x]", ["pytest*"], {"pytest*": {"x"}}, id="wildcard-extra"),
        pytest.param("a[b], c , d[e,f]", ["a", "c", "d"], {"a": {"b"}, "d": {"e", "f"}}, id="whitespace"),
        pytest.param(None, [], {}, id="none"),
        pytest.param("", [], {}, id="empty"),
        pytest.param(",,", [], {}, id="only-separators"),
    ],
)
def test_parse_packages(value: str | None, names: list[str], requested_extras: dict[str, set[str]]) -> None:
    assert parse_packages(value) == (names, requested_extras)
