from __future__ import annotations

import dataclasses
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import TYPE_CHECKING

import pytest

from pipdeptree.__main__ import main
from pipdeptree._cli import get_options
from pipdeptree._from_index import (
    FromIndexInputError,
    FromIndexUnavailableError,
    _LocalSource,
    _parse_requirements_file,
    _ParsedInputs,
    _read_pyproject_name,
    _render_pyproject,
    _resolve_indexes,
    _resolve_pyproject_path,
    _VcsSource,
    resolve_from_index,
)
from pipdeptree._models import PackageDAG
from pipdeptree._synthetic_dist import SyntheticDistribution

_PYPI_NAME = "pypi"
_PYPI_URL = "https://pypi.org/simple"

if TYPE_CHECKING:
    from collections.abc import Callable
    from importlib.metadata import Distribution

    from pytest_mock import MockerFixture


@pytest.fixture
def fake_result() -> SimpleNamespace:
    return SimpleNamespace(
        pins={"fastapi": "0.115.2", "starlette": "0.41.3", "anyio": "4.6.2"},
        lock_input=SimpleNamespace(dependencies={"fastapi": ("starlette",), "starlette": ("anyio",), "anyio": ()}),
    )


@pytest.fixture
def captured_pyproject(mocker: MockerFixture, fake_result: SimpleNamespace) -> dict[str, str]:
    """Capture the pyproject content nab is asked to resolve, bypassing the real (absent) resolver."""
    captured: dict[str, str] = {}

    def fake_resolve(path: Path, indexes: object) -> SimpleNamespace:  # noqa: ARG001
        captured["content"] = path.read_text(encoding="utf-8")
        return fake_result

    mocker.patch("pipdeptree._from_index._resolve_pyproject_path", side_effect=fake_resolve)
    return captured


@pytest.fixture
def fake_nab(mocker: MockerFixture, fake_result: SimpleNamespace) -> SimpleNamespace:
    """Stub the optional nab modules in ``sys.modules`` so ``_resolve_pyproject_path`` runs without nab installed."""
    # The path may live in a TemporaryDirectory that is gone after resolve returns, so read its content eagerly.
    captured = SimpleNamespace(paths=[], contents=[])

    def fake_resolve_pyproject(path: Path, transport: object, *, config: object) -> SimpleNamespace:  # noqa: ARG001
        captured.paths.append(path)
        captured.contents.append(path.read_text(encoding="utf-8"))
        return fake_result

    nab_resolve = mocker.MagicMock()
    nab_resolve.resolve_pyproject = fake_resolve_pyproject
    mocker.patch.dict(
        "sys.modules",
        {
            "nab_index": mocker.MagicMock(),
            "nab_index.multi_index": mocker.MagicMock(),
            "nab_index.urllib3_async_transport": mocker.MagicMock(),
            "nab_python": mocker.MagicMock(),
            "nab_python.config": mocker.MagicMock(),
            "nab_python.resolve": nab_resolve,
        },
    )
    return captured


@pytest.fixture
def write_pyproject(tmp_path: Path) -> Callable[[], Path]:
    def func() -> Path:
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text('[project]\nname = "x"\nversion = "0"\ndependencies = ["fastapi"]\n', encoding="utf-8")
        return pyproject

    return func


def _resolve(
    requirements: list[str] | None = None,
    requirement_files: list[str] | None = None,
    pyproject_files: list[str] | None = None,
) -> list[Distribution]:
    return resolve_from_index(
        requirements=requirements or [],
        requirement_files=requirement_files or [],
        pyproject_files=pyproject_files or [],
    )


def test_resolve_from_index_builds_tree(mocker: MockerFixture, fake_result: SimpleNamespace) -> None:
    mocker.patch("pipdeptree._from_index._resolve_pyproject_path", return_value=fake_result)

    dag = PackageDAG.from_pkgs(_resolve(["fastapi<=0.115.2"]))

    by_key = {str(pkg.key): pkg for pkg in dag}
    assert set(by_key) == {"fastapi", "starlette", "anyio"}
    assert by_key["fastapi"].version == "0.115.2"
    assert [child.key for child in dag.get_children("fastapi")] == ["starlette"]
    assert [child.key for child in dag.get_children("starlette")] == ["anyio"]
    assert dag.get_children("anyio") == []


def test_resolve_from_index_pins_children_versions(mocker: MockerFixture, fake_result: SimpleNamespace) -> None:
    mocker.patch("pipdeptree._from_index._resolve_pyproject_path", return_value=fake_result)

    dag = PackageDAG.from_pkgs(_resolve(["fastapi"]))

    (starlette,) = dag.get_children("fastapi")
    assert starlette.version_spec == "==0.41.3"


@pytest.mark.parametrize(
    ("requirements", "expected"),
    [
        pytest.param(['foo>=1,<2; python_version >= "3.10"'], 'foo>=1,<2; python_version >= \\"3.10\\"', id="inline"),
        pytest.param(["fastapi", "starlette"], '"starlette",', id="multiple-inline"),
    ],
)
def test_resolve_from_index_writes_requirement(
    captured_pyproject: dict[str, str], requirements: list[str], expected: str
) -> None:
    _resolve(requirements)

    assert expected in captured_pyproject["content"]


def test_resolve_from_index_requirements_file_parsed(captured_pyproject: dict[str, str], tmp_path: Path) -> None:
    req = tmp_path / "requirements.txt"
    req.write_text("fastapi\nstarlette\n", encoding="utf-8")

    _resolve(requirement_files=[str(req)])

    content = captured_pyproject["content"]
    assert '"fastapi",' in content
    assert '"starlette",' in content


def test_resolve_from_index_mixed_sources_merged(
    captured_pyproject: dict[str, str], write_pyproject: Callable[[], Path], tmp_path: Path
) -> None:
    pyproject = write_pyproject()
    req = tmp_path / "requirements.txt"
    req.write_text("starlette\n", encoding="utf-8")

    _resolve(["anyio"], requirement_files=[str(req)], pyproject_files=[str(pyproject)])

    content = captured_pyproject["content"]
    assert '"fastapi",' in content
    assert '"starlette",' in content
    assert '"anyio",' in content


def test_resolve_from_index_missing_nab_raises(mocker: MockerFixture) -> None:
    # Setting the modules to None makes the guarded import raise, simulating nab not being installed.
    mocker.patch.dict("sys.modules", dict.fromkeys(("nab_index", "nab_python.resolve")))
    with pytest.raises(FromIndexUnavailableError, match="pip install pipdeptree\\[index\\]"):
        _resolve(["starlette"])


@pytest.mark.parametrize(
    "kind",
    [
        pytest.param("requirement_files", id="requirements-flag"),
        pytest.param("pyproject_files", id="pyproject-flag"),
    ],
)
def test_resolve_from_index_missing_file(tmp_path: Path, kind: str) -> None:
    with pytest.raises(FromIndexInputError, match="source file does not exist"):
        _resolve(**{kind: [str(tmp_path / "absent")]})


def test_resolve_from_index_lone_pyproject_resolved_natively(
    mocker: MockerFixture, fake_result: SimpleNamespace, write_pyproject: Callable[[], Path]
) -> None:
    pyproject = write_pyproject()
    resolve = mocker.patch("pipdeptree._from_index._resolve_pyproject_path", return_value=fake_result)

    _resolve(pyproject_files=[str(pyproject)])

    resolve.assert_called_once_with(pyproject, None)


def test_resolve_from_index_writes_temp_pyproject_and_calls_nab(fake_nab: SimpleNamespace) -> None:
    result = _resolve(["fastapi<=0.115.2"])

    assert result[0].metadata["Name"] == "fastapi"
    (content,) = fake_nab.contents
    assert 'name = "pipdeptree-from-index"' in content
    assert '"fastapi<=0.115.2",' in content


def test_resolve_pyproject_path_passes_path_natively(
    fake_nab: SimpleNamespace, write_pyproject: Callable[[], Path]
) -> None:
    pyproject = write_pyproject()

    _resolve_pyproject_path(pyproject, None)

    assert fake_nab.paths == [pyproject]


def test_render_pyproject_quotes_special_chars() -> None:
    rendered = _render_pyproject(_ParsedInputs(requirements=['foo>=1; extra == "bar"']))
    assert 'dependencies = [\n  "foo>=1; extra == \\"bar\\"",\n]' in rendered


def test_synthetic_distribution_file_helpers() -> None:
    dist = SyntheticDistribution("foo", "1.0", ("bar==2.0",))
    assert dist.read_text("METADATA") is None
    assert dist.locate_file("METADATA") == Path("METADATA")


@pytest.mark.parametrize(
    ("body", "expected_reqs"),
    [
        pytest.param(
            "# a full-line comment\n\nfastapi  # inline comment\nanyio>=4\n",
            ["fastapi", "anyio>=4"],
            id="comments-and-blank-lines",
        ),
        pytest.param(
            "--index-url https://example.com\nfoo --hash=sha256:abcd\nbar\n",
            ["foo", "bar"],
            id="options-ignored",
        ),
        pytest.param(
            'fastapi[all]>=0.100; python_version >= "3.10"\n',
            ['fastapi[all]>=0.100; python_version >= "3.10"'],
            id="markers-and-extras-kept",
        ),
    ],
)
def test_parse_requirements_file(tmp_path: Path, body: str, expected_reqs: list[str]) -> None:
    req = tmp_path / "requirements.txt"
    req.write_text(body, encoding="utf-8")

    inputs = _ParsedInputs()
    _parse_requirements_file(req, inputs)

    assert inputs.requirements == expected_reqs
    assert inputs.constraints == []


def test_parse_requirements_file_follows_nested(tmp_path: Path) -> None:
    (tmp_path / "base.txt").write_text("anyio>=4\n", encoding="utf-8")
    req = tmp_path / "requirements.txt"
    req.write_text("-r base.txt\nfastapi\n", encoding="utf-8")

    inputs = _ParsedInputs()
    _parse_requirements_file(req, inputs)

    assert inputs.requirements == ["anyio>=4", "fastapi"]
    assert inputs.constraints == []


def test_parse_requirements_file_collects_constraints(tmp_path: Path) -> None:
    (tmp_path / "constraints.txt").write_text("urllib3<2\ncertifi\n", encoding="utf-8")
    req = tmp_path / "requirements.txt"
    req.write_text("-c constraints.txt\nrequests\n", encoding="utf-8")

    inputs = _ParsedInputs()
    _parse_requirements_file(req, inputs)

    assert inputs.requirements == ["requests"]
    assert inputs.constraints == ["urllib3<2", "certifi"]


@pytest.mark.parametrize(
    ("line", "match"),
    [
        pytest.param(
            "foo @ https://example.com/foo-1.0-py3-none-any.whl", r"URL requirements are not supported", id="wheel-url"
        ),
        pytest.param("foo @ hg+https://example.com/r", r"only git VCS requirements", id="hg-vcs"),
        pytest.param("foo @ git+https://example.com/foo.git", r"must be pinned to a full commit sha", id="vcs-no-sha"),
        pytest.param("-e .", r"must be a directory with a pyproject.toml", id="editable-no-pyproject"),
    ],
)
def test_parse_requirements_file_rejects_unmappable(tmp_path: Path, line: str, match: str) -> None:
    req = tmp_path / "requirements.txt"
    req.write_text(f"fastapi\n{line}\n", encoding="utf-8")

    with pytest.raises(FromIndexInputError, match=match):
        _parse_requirements_file(req, _ParsedInputs())


def test_parse_requirements_file_rejects_constraint_extras(tmp_path: Path) -> None:
    (tmp_path / "constraints.txt").write_text("fastapi[all]<1\n", encoding="utf-8")
    req = tmp_path / "requirements.txt"
    req.write_text("-c constraints.txt\nrequests\n", encoding="utf-8")

    with pytest.raises(FromIndexInputError, match=r"cannot constrain extras"):
        _parse_requirements_file(req, _ParsedInputs())


def test_resolve_from_index_constraints_reach_nab(captured_pyproject: dict[str, str], tmp_path: Path) -> None:
    (tmp_path / "constraints.txt").write_text("urllib3<2\n", encoding="utf-8")
    req = tmp_path / "requirements.txt"
    req.write_text("-c constraints.txt\nrequests\n", encoding="utf-8")

    _resolve(requirement_files=[str(req)])

    content = captured_pyproject["content"]
    assert '"requests",' in content
    assert '[tool.nab]\nconstraints = [\n  "urllib3<2",\n]' in content


def test_render_pyproject_omits_tool_nab_without_constraints() -> None:
    assert "[tool.nab]" not in _render_pyproject(_ParsedInputs(requirements=["fastapi"]))


@pytest.fixture
def read_name(mocker: MockerFixture) -> None:
    """Stand in for nab's read_pyproject_name (absent here); a minimal name read avoids a tomllib dep on 3.10."""

    def fake_read(directory: Path) -> str | None:
        for line in (directory / "pyproject.toml").read_text(encoding="utf-8").splitlines():
            if line.startswith("name = "):
                return line.removeprefix("name = ").strip().strip('"')
        return None

    mocker.patch("pipdeptree._from_index._read_pyproject_name", side_effect=fake_read)


@pytest.fixture
def local_pkg(tmp_path: Path) -> Path:
    pkg = tmp_path / "localpkg"
    pkg.mkdir()
    (pkg / "pyproject.toml").write_text(
        '[project]\nname = "localpkg"\nversion = "1.0"\ndependencies = ["anyio"]\n', encoding="utf-8"
    )
    return pkg


def test_translate_editable_local_source(
    captured_pyproject: dict[str, str],
    read_name: None,  # noqa: ARG001
    local_pkg: Path,
    tmp_path: Path,
) -> None:
    req = tmp_path / "requirements.txt"
    req.write_text("-e ./localpkg\n", encoding="utf-8")

    _resolve(requirement_files=[str(req)])

    content = captured_pyproject["content"]
    assert '"localpkg",' in content
    assert f'[[tool.nab.local-sources]]\nname = "localpkg"\npath = "{local_pkg}"\neditable = true\n' in content
    assert 'build-policy = "build-remote"' in content


def test_translate_file_url_local_source_not_editable(
    captured_pyproject: dict[str, str],
    read_name: None,  # noqa: ARG001
    local_pkg: Path,
    tmp_path: Path,
) -> None:
    req = tmp_path / "requirements.txt"
    req.write_text(f"localpkg @ file://{local_pkg}\n", encoding="utf-8")

    _resolve(requirement_files=[str(req)])

    content = captured_pyproject["content"]
    assert f'[[tool.nab.local-sources]]\nname = "localpkg"\npath = "{local_pkg}"\neditable = false\n' in content


def test_translate_local_source_without_project_name(
    read_name: None,  # noqa: ARG001
    tmp_path: Path,
) -> None:
    pkg = tmp_path / "nameless"
    pkg.mkdir()
    (pkg / "pyproject.toml").write_text("[build-system]\nrequires = []\n", encoding="utf-8")
    req = tmp_path / "requirements.txt"
    req.write_text("-e ./nameless\n", encoding="utf-8")

    with pytest.raises(FromIndexInputError, match=r"has no \[project\].name"):
        _resolve(requirement_files=[str(req)])


def test_translate_git_vcs_source(captured_pyproject: dict[str, str], tmp_path: Path) -> None:
    sha = "1234567890abcdef1234567890abcdef12345678"
    req = tmp_path / "requirements.txt"
    req.write_text(f"pkg @ git+https://h/r.git@{sha}\n", encoding="utf-8")

    _resolve(requirement_files=[str(req)])

    content = captured_pyproject["content"]
    assert '"pkg",' in content
    assert '[tool.nab.vcs]\npolicy = "allow"\nallowed-schemes = ["git+https", "git+ssh"' in content
    assert f'[[tool.nab.vcs-sources]]\nname = "pkg"\nurl = "git+https://h/r.git@{sha}"\n' in content
    assert 'build-policy = "build-remote"' in content


def test_translate_git_vcs_without_pin(tmp_path: Path) -> None:
    req = tmp_path / "requirements.txt"
    req.write_text("pkg @ git+https://h/r.git@v1.0\n", encoding="utf-8")

    with pytest.raises(FromIndexInputError, match="must be pinned to a full commit sha"):
        _resolve(requirement_files=[str(req)])


def test_translate_mixed_sources(
    captured_pyproject: dict[str, str],
    read_name: None,  # noqa: ARG001
    local_pkg: Path,  # noqa: ARG001
    tmp_path: Path,
) -> None:
    sha = "1234567890abcdef1234567890abcdef12345678"
    req = tmp_path / "requirements.txt"
    req.write_text(f"fastapi\n-e ./localpkg\npkg @ git+https://h/r.git@{sha}\n", encoding="utf-8")

    _resolve(requirement_files=[str(req)])

    content = captured_pyproject["content"]
    for dep in ('"fastapi",', '"localpkg",', '"pkg",'):
        assert dep in content
    assert "[[tool.nab.local-sources]]" in content
    assert "[[tool.nab.vcs-sources]]" in content


def test_translate_inline_git_vcs(captured_pyproject: dict[str, str]) -> None:
    sha = "1234567890abcdef1234567890abcdef12345678"

    _resolve([f"pkg @ git+https://h/r.git@{sha}"])

    content = captured_pyproject["content"]
    assert '"pkg",' in content
    assert f'url = "git+https://h/r.git@{sha}"' in content


def test_translate_git_vcs_without_name(tmp_path: Path) -> None:
    sha = "1234567890abcdef1234567890abcdef12345678"
    req = tmp_path / "requirements.txt"
    req.write_text(f"git+https://h/r.git@{sha}\n", encoding="utf-8")

    with pytest.raises(FromIndexInputError, match="VCS requirement needs an explicit name"):
        _resolve(requirement_files=[str(req)])


def test_read_pyproject_name_delegates_to_nab(mocker: MockerFixture, local_pkg: Path) -> None:
    requirements_file = mocker.MagicMock()
    requirements_file.read_pyproject_name.return_value = "localpkg"
    mocker.patch.dict("sys.modules", {"nab_python.requirements_file": requirements_file})

    assert _read_pyproject_name(local_pkg) == "localpkg"
    requirements_file.read_pyproject_name.assert_called_once_with(local_pkg / "pyproject.toml")


def test_translate_local_source_missing_nab(local_pkg: Path, tmp_path: Path, mocker: MockerFixture) -> None:
    # _read_pyproject_name imports from nab_python; with it absent, the local-source path reports unavailability.
    mocker.patch.dict("sys.modules", {"nab_python.requirements_file": None})
    req = tmp_path / "requirements.txt"
    req.write_text("-e ./localpkg\n", encoding="utf-8")
    assert local_pkg.exists()

    with pytest.raises(FromIndexUnavailableError, match=r"pip install pipdeptree\[index\]"):
        _resolve(requirement_files=[str(req)])


@pytest.mark.skipif(sys.version_info < (3, 11), reason="stdlib tomllib (and no tomli dep) only on 3.11+")
def test_render_pyproject_round_trips_as_toml(local_pkg: Path) -> None:
    import tomllib  # noqa: PLC0415

    inputs = _ParsedInputs(
        requirements=["fastapi", 'foo>=1; extra == "bar"'],
        constraints=["urllib3<2"],
        local_sources=[_LocalSource(name="localpkg", path=str(local_pkg), editable=True)],
        vcs_sources=[_VcsSource(name="pkg", url="git+https://h/r.git@" + "0" * 40)],
    )

    data = tomllib.loads(_render_pyproject(inputs))

    assert data["project"]["dependencies"] == ["fastapi", 'foo>=1; extra == "bar"', "localpkg", "pkg"]
    assert data["tool"]["nab"]["constraints"] == ["urllib3<2"]
    assert data["tool"]["nab"]["build-policy"] == "build-remote"
    assert data["tool"]["nab"]["vcs"]["policy"] == "allow"
    assert "git+https" in data["tool"]["nab"]["vcs"]["allowed-schemes"]
    assert data["tool"]["nab"]["local-sources"] == [{"name": "localpkg", "path": str(local_pkg), "editable": True}]
    assert data["tool"]["nab"]["vcs-sources"] == [{"name": "pkg", "url": "git+https://h/r.git@" + "0" * 40}]


def test_render_pyproject_omits_build_policy_without_sources() -> None:
    rendered = _render_pyproject(_ParsedInputs(requirements=["fastapi"], constraints=["urllib3<2"]))
    assert "build-policy" not in rendered
    assert "[tool.nab.vcs]" not in rendered


def test_main_from_index_renders_text_tree(
    mocker: MockerFixture, fake_result: SimpleNamespace, capsys: pytest.CaptureFixture[str]
) -> None:
    mocker.patch("pipdeptree.__main__.sys.argv", ["", "from-index", "fastapi"])
    mocker.patch("pipdeptree._from_index._resolve_pyproject_path", return_value=fake_result)

    assert main() == 0

    out, _ = capsys.readouterr()
    assert "fastapi==0.115.2" in out
    assert "starlette" in out
    assert "anyio" in out
    assert "[candidate:" in out
    assert "required:" not in out
    assert "installed:" not in out


def test_main_from_index_pyproject_renders_tree(
    mocker: MockerFixture,
    fake_result: SimpleNamespace,
    write_pyproject: Callable[[], Path],
    capsys: pytest.CaptureFixture[str],
) -> None:
    pyproject = write_pyproject()
    mocker.patch("pipdeptree.__main__.sys.argv", ["", "from-index", "--pyproject", str(pyproject)])
    resolve = mocker.patch("pipdeptree._from_index._resolve_pyproject_path", return_value=fake_result)

    assert main() == 0

    resolve.assert_called_once_with(pyproject, None)
    out, _ = capsys.readouterr()
    assert "fastapi==0.115.2" in out


def test_main_from_index_missing_nab(mocker: MockerFixture, capsys: pytest.CaptureFixture[str]) -> None:
    mocker.patch("pipdeptree.__main__.sys.argv", ["", "from-index", "fastapi"])
    mocker.patch(
        "pipdeptree.__main__.resolve_from_index",
        side_effect=FromIndexUnavailableError("The from-index subcommand requires the optional 'nab' resolver."),
    )

    assert main() == 1

    out, err = capsys.readouterr()
    assert not out
    assert "The from-index subcommand requires the optional 'nab' resolver." in err


def test_main_from_index_input_error(mocker: MockerFixture, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    mocker.patch("pipdeptree.__main__.sys.argv", ["", "from-index", "--requirements", str(tmp_path / "missing.txt")])

    assert main() == 1

    out, err = capsys.readouterr()
    assert not out
    assert "source file does not exist" in err


@pytest.fixture
def nab_index_defaults(mocker: MockerFixture) -> None:
    """Stub nab_python.fetch so _resolve_indexes can read the PyPI default name/url without nab installed."""
    fetch = mocker.MagicMock()
    fetch.DEFAULT_INDEX_NAME = _PYPI_NAME
    fetch.DEFAULT_INDEX_URL = _PYPI_URL
    mocker.patch.dict("sys.modules", {"nab_python.fetch": fetch})


@pytest.mark.parametrize(
    ("index_url", "extra_index_url", "env", "expected"),
    [
        pytest.param(None, None, {}, None, id="nothing-set"),
        pytest.param("https://a/simple", None, {}, [("primary", "https://a/simple")], id="index-url-only"),
        pytest.param(_PYPI_URL, None, {}, [(_PYPI_NAME, _PYPI_URL)], id="index-url-is-pypi-named-pypi"),
        pytest.param(
            None,
            ["https://x/simple", "https://y/simple"],
            {},
            [(_PYPI_NAME, _PYPI_URL), ("extra-1", "https://x/simple"), ("extra-2", "https://y/simple")],
            id="extra-only-keeps-pypi-primary",
        ),
        pytest.param(
            None, None, {"PIP_INDEX_URL": "https://pip/simple"}, [("primary", "https://pip/simple")], id="pip-env"
        ),
        pytest.param(
            None, None, {"UV_INDEX_URL": "https://uv/simple"}, [("primary", "https://uv/simple")], id="uv-env"
        ),
        pytest.param(
            None,
            None,
            {"PIP_INDEX_URL": "https://pip/simple", "UV_INDEX_URL": "https://uv/simple"},
            [("primary", "https://pip/simple")],
            id="pip-beats-uv",
        ),
        pytest.param(
            "https://flag/simple",
            None,
            {"PIP_INDEX_URL": "https://pip/simple"},
            [("primary", "https://flag/simple")],
            id="flag-beats-env",
        ),
        pytest.param(
            None,
            None,
            {"PIP_EXTRA_INDEX_URL": "https://x/simple https://y/simple"},
            [(_PYPI_NAME, _PYPI_URL), ("extra-1", "https://x/simple"), ("extra-2", "https://y/simple")],
            id="pip-extra-space-split",
        ),
        pytest.param(
            None,
            None,
            {"UV_EXTRA_INDEX_URL": "https://x/simple"},
            [(_PYPI_NAME, _PYPI_URL), ("extra-1", "https://x/simple")],
            id="uv-extra-fallback",
        ),
        pytest.param(
            None,
            ["https://flag/simple"],
            {"PIP_EXTRA_INDEX_URL": "https://env/simple"},
            [(_PYPI_NAME, _PYPI_URL), ("extra-1", "https://flag/simple")],
            id="flag-extra-beats-env-extra",
        ),
    ],
)
def test_resolve_indexes(
    nab_index_defaults: None,  # noqa: ARG001
    monkeypatch: pytest.MonkeyPatch,
    index_url: str | None,
    extra_index_url: list[str] | None,
    env: dict[str, str],
    expected: list[tuple[str, str]] | None,
) -> None:
    for key in ("PIP_INDEX_URL", "UV_INDEX_URL", "PIP_EXTRA_INDEX_URL", "UV_EXTRA_INDEX_URL"):
        monkeypatch.delenv(key, raising=False)
    for key, value in env.items():
        monkeypatch.setenv(key, value)

    resolved = _resolve_indexes(index_url, extra_index_url)

    assert resolved == expected
    if resolved is not None:
        names = [name for name, _ in resolved]
        assert len(names) == len(set(names))


def test_render_pyproject_emits_indexes() -> None:
    inputs = _ParsedInputs(
        requirements=["fastapi"],
        indexes=[("primary", "https://a/simple"), ("extra-1", "https://b/simple")],
    )

    rendered = _render_pyproject(inputs)

    assert '[[tool.nab.indexes]]\nname = "primary"\nurl = "https://a/simple"\n' in rendered
    assert '[[tool.nab.indexes]]\nname = "extra-1"\nurl = "https://b/simple"\n' in rendered
    # Order: primary table precedes the extra table.
    assert rendered.index('"primary"') < rendered.index('"extra-1"')


def test_render_pyproject_omits_indexes_without_override() -> None:
    assert "[[tool.nab.indexes]]" not in _render_pyproject(_ParsedInputs(requirements=["fastapi"]))


@pytest.mark.skipif(sys.version_info < (3, 11), reason="stdlib tomllib (and no tomli dep) only on 3.11+")
def test_render_pyproject_indexes_round_trip_as_toml() -> None:
    import tomllib  # noqa: PLC0415

    inputs = _ParsedInputs(
        requirements=["fastapi"],
        indexes=[("primary", "https://a/simple"), ("extra-1", "https://b/simple")],
    )

    data = tomllib.loads(_render_pyproject(inputs))

    assert data["tool"]["nab"]["indexes"] == [
        {"name": "primary", "url": "https://a/simple"},
        {"name": "extra-1", "url": "https://b/simple"},
    ]


def test_resolve_from_index_temp_path_emits_indexes(
    nab_index_defaults: None,  # noqa: ARG001
    captured_pyproject: dict[str, str],
) -> None:
    resolve_from_index(
        requirements=["fastapi"],
        requirement_files=[],
        pyproject_files=[],
        index_url="https://a/simple",
    )

    content = captured_pyproject["content"]
    # An explicit --index-url replaces PyPI, so only the single named primary index is emitted.
    assert '[[tool.nab.indexes]]\nname = "primary"\nurl = "https://a/simple"\n' in content


@dataclasses.dataclass(frozen=True)
class _FakeIndexConfig:
    name: str
    url: str


@dataclasses.dataclass(frozen=True)
class _FakeConfig:
    indexes: tuple[_FakeIndexConfig, ...]


def test_lone_pyproject_override_replaces_indexes(
    nab_index_defaults: None,  # noqa: ARG001
    mocker: MockerFixture,
    fake_result: SimpleNamespace,
    write_pyproject: Callable[[], Path],
) -> None:
    pyproject = write_pyproject()
    original = _FakeConfig(indexes=(_FakeIndexConfig("pyproject-index", "https://own/simple"),))
    captured: dict[str, object] = {}

    def fake_resolve_pyproject(path: Path, transport: object, *, config: object) -> SimpleNamespace:  # noqa: ARG001
        captured["config"] = config
        return fake_result

    nab_index_multi = mocker.MagicMock()
    nab_index_multi.IndexConfig = _FakeIndexConfig
    nab_config = mocker.MagicMock()
    nab_config.read_pyproject_config.return_value = original
    nab_resolve = mocker.MagicMock()
    nab_resolve.resolve_pyproject = fake_resolve_pyproject
    mocker.patch.dict(
        "sys.modules",
        {
            "nab_index": mocker.MagicMock(),
            "nab_index.multi_index": nab_index_multi,
            "nab_index.urllib3_async_transport": mocker.MagicMock(),
            "nab_python": mocker.MagicMock(),
            "nab_python.config": nab_config,
            "nab_python.resolve": nab_resolve,
        },
    )

    resolve_from_index(
        requirements=[],
        requirement_files=[],
        pyproject_files=[str(pyproject)],
        index_url="https://override/simple",
    )

    config = captured["config"]
    assert isinstance(config, _FakeConfig)
    # The flag replaced the pyproject's own [tool.nab].indexes.
    assert config.indexes == (_FakeIndexConfig("primary", "https://override/simple"),)


def test_lone_pyproject_no_override_keeps_own_indexes(
    mocker: MockerFixture, fake_result: SimpleNamespace, write_pyproject: Callable[[], Path]
) -> None:
    pyproject = write_pyproject()
    original = _FakeConfig(indexes=(_FakeIndexConfig("pyproject-index", "https://own/simple"),))
    captured: dict[str, object] = {}

    def fake_resolve_pyproject(path: Path, transport: object, *, config: object) -> SimpleNamespace:  # noqa: ARG001
        captured["config"] = config
        return fake_result

    nab_config = mocker.MagicMock()
    nab_config.read_pyproject_config.return_value = original
    nab_resolve = mocker.MagicMock()
    nab_resolve.resolve_pyproject = fake_resolve_pyproject
    mocker.patch.dict(
        "sys.modules",
        {
            "nab_index": mocker.MagicMock(),
            "nab_index.multi_index": mocker.MagicMock(),
            "nab_index.urllib3_async_transport": mocker.MagicMock(),
            "nab_python": mocker.MagicMock(),
            "nab_python.config": nab_config,
            "nab_python.resolve": nab_resolve,
        },
    )

    resolve_from_index(requirements=[], requirement_files=[], pyproject_files=[str(pyproject)])

    # No flag/env, so the pyproject's own indexes are left untouched.
    assert captured["config"] is original


def test_cli_index_url_flag() -> None:
    options = get_options(["from-index", "foo", "--index-url", "https://x/simple"])
    assert options.index_url == "https://x/simple"
    assert options.extra_index_url is None


def test_cli_extra_index_url_accumulates() -> None:
    options = get_options([
        "from-index",
        "foo",
        "--extra-index-url",
        "https://x/simple",
        "--extra-index-url",
        "https://y/simple",
    ])
    assert options.extra_index_url == ["https://x/simple", "https://y/simple"]


def test_cli_bare_top_level_seeds_index_defaults() -> None:
    options = get_options([])
    assert options.index_url is None
    assert options.extra_index_url is None
