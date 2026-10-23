"""The local release command must never publish during a preview."""

from __future__ import annotations

import subprocess  # ruff:ignore[suspicious-subprocess-import]  # The subprocess boundary is mocked in these tests.
import sys
from contextlib import nullcontext
from typing import TYPE_CHECKING

import pytest

from tools.release import main

if TYPE_CHECKING:
    from pathlib import Path

    from pytest_mock import MockerFixture


def test_release_dispatch_starts_only_protected_workflow(mocker: MockerFixture) -> None:
    mocker.patch.object(sys, "argv", ["release", "--dispatch", "--bump", "minor"])
    run = mocker.patch("tools.release.subprocess.run", autospec=True, return_value=_completed())

    main()

    run.assert_called_once()
    assert run.call_args.args[0] == (
        "gh",
        "workflow",
        "run",
        "prepare-release.yaml",
        "--repo",
        "tox-dev/pipdeptree",
        "--ref",
        "main",
        "-f",
        "bump=minor",
    )


def test_release_preview_requires_clean_checkout(mocker: MockerFixture) -> None:
    mocker.patch.object(sys, "argv", ["release"])
    run = mocker.patch(
        "tools.release.subprocess.run", autospec=True, return_value=_completed(" M docs/changelog.rst\n")
    )

    with pytest.raises(RuntimeError, match="commit or stash"):
        main()

    run.assert_called_once()
    assert run.call_args.args[0] == ("git", "status", "--porcelain")


@pytest.mark.parametrize("format_changes", [pytest.param(False, id="unchanged"), pytest.param(True, id="formatted")])
@pytest.mark.parametrize("previous", [pytest.param("4.2.9", id="later-release"), pytest.param("", id="first-release")])
def test_release_preview_checks_notes_and_packages(
    mocker: MockerFixture,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
    format_changes: bool,
    previous: str,
) -> None:
    mocker.patch.object(sys, "argv", ["release", "--bump", "patch"])
    mocker.patch("tools.release.TemporaryDirectory", return_value=nullcontext(str(tmp_path)))
    dist = tmp_path / "source" / "dist"
    dist.mkdir(parents=True)
    (dist / "pipdeptree-4.2.10.tar.gz").touch()
    (dist / "pipdeptree-4.2.10-py3-none-any.whl").touch()
    outputs = [""] * 17
    outputs[2:5] = ["4.2.9\n", "4.2.10\n", previous]
    outputs[9] = "### Bug fixes\n\n- Fixed output.\n"
    outputs[12] = "1792696343\n"
    responses: list[subprocess.CompletedProcess[str] | subprocess.CalledProcessError] = [
        _completed(output) for output in outputs
    ]
    if format_changes:
        responses.insert(7, subprocess.CalledProcessError(1, "prek"))
    run = mocker.patch("tools.release.subprocess.run", autospec=True, side_effect=responses)

    main()

    assert capsys.readouterr().out == "### Bug fixes\n\n- Fixed output.\n"
    commands = [call.args[0] for call in run.call_args_list]
    assert commands[3][:5] == ("release-creator", "tags", "--next", "patch", "--directory")
    assert commands.count(("prek", "run", "docstrfmt", "--files", "docs/changelog.rst")) == 1 + format_changes
    assert commands[9 + format_changes][:4] == ("release-creator", "notes", "--changelog", "docs/changelog.rst")
    if previous:
        assert commands[9 + format_changes][-2:] == ("--previous", previous)
    else:
        assert "--previous" not in commands[9 + format_changes]
    assert commands[10 + format_changes][:3] == ("uv", "venv", "--python")
    assert commands[11 + format_changes][:3] == ("uv", "pip", "sync")
    assert "pylock.build.toml" in commands[11 + format_changes]
    assert commands[12 + format_changes] == ("git", "log", "-1", "--format=%ct")
    assert commands[13 + format_changes][:3] == ("uv", "build", "--sdist")
    assert "--no-build-isolation" in commands[13 + format_changes]
    assert run.call_args_list[13 + format_changes].kwargs["env"]["PIPDEPTREE_VERSION"] == "4.2.10"
    assert run.call_args_list[13 + format_changes].kwargs["env"]["SOURCE_DATE_EPOCH"] == "1792696343"
    assert commands[-3:] == [
        ("twine", "check", str(dist / "pipdeptree-4.2.10-py3-none-any.whl"), str(dist / "pipdeptree-4.2.10.tar.gz")),
        ("check-wheel-contents", "--no-config", "dist"),
        (sys.executable, "tools/check_release_wheels.py", "dist"),
    ]
    assert all(call.kwargs["stdout"] is sys.stderr for call in run.call_args_list if not call.kwargs["capture_output"])
    assert all(command[:2] != ("git", "push") for command in commands)
    assert all(command[:2] != ("git", "tag") or command[2:] == ("--list",) for command in commands)


def test_release_preview_stops_when_notes_fail(mocker: MockerFixture) -> None:
    mocker.patch.object(sys, "argv", ["release"])
    outputs = ["", "", "4.2.9\n", "4.2.10\n", "4.2.9\n", "", "", "", ""]
    run = mocker.patch(
        "tools.release.subprocess.run",
        autospec=True,
        side_effect=[*(_completed(output) for output in outputs), subprocess.CalledProcessError(1, "release-creator")],
    )

    with pytest.raises(subprocess.CalledProcessError):
        main()

    assert run.call_count == 10


def test_release_subprocess_error_stops_dispatch(mocker: MockerFixture) -> None:
    mocker.patch.object(sys, "argv", ["release", "--dispatch"])
    run = mocker.patch(
        "tools.release.subprocess.run", autospec=True, side_effect=subprocess.CalledProcessError(1, "gh")
    )

    with pytest.raises(subprocess.CalledProcessError):
        main()

    run.assert_called_once()


def _completed(stdout: str = "") -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(args=(), returncode=0, stdout=stdout)
