"""The local release command must never publish during a preview."""

from __future__ import annotations

import subprocess  # ruff:ignore[suspicious-subprocess-import]  # The subprocess boundary is mocked in these tests.
import sys
from typing import TYPE_CHECKING

import pytest

from tools.release import main

if TYPE_CHECKING:
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
    format_changes: bool,
    previous: str,
) -> None:
    mocker.patch.object(sys, "argv", ["release", "--bump", "patch"])
    outputs = [
        "",
        "",
        "4.2.9\n",
        "4.2.10\n",
        previous,
        "",
        "",
        "",
        "",
        "### Bug fixes\n\n- Fixed output.\n",
        "",
        "",
        "",
        "",
        "",
    ]
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
    assert commands[10 + format_changes][:6] == (
        "release-creator",
        "build-constraints",
        "--lock",
        "pylock.toml",
        "--group",
        "build",
    )
    assert commands[11 + format_changes][:3] == ("uv", "build", "--sdist")
    assert commands[11 + format_changes][4:6] == ("--python", sys.executable)
    assert "--require-hashes" in commands[11 + format_changes]
    assert run.call_args_list[11 + format_changes].kwargs["env"]["PIPDEPTREE_VERSION"] == "4.2.10"
    assert run.call_args_list[11 + format_changes].kwargs["env"]["UV_EXCLUDE_NEWER"] == "1 week"
    assert commands[-3:] == [
        ("twine", "check", "dist/*"),
        ("check-wheel-contents", "--no-config", "dist"),
        (sys.executable, "tools/check_release_wheels.py", "dist"),
    ]
    assert all(call.kwargs["stdout"] is sys.stderr for call in run.call_args_list if not call.kwargs["capture_output"])
    assert all(command[:2] != ("git", "push") for command in commands)
    assert all(command[:2] != ("git", "tag") or command[2:] == ("--list",) for command in commands)


def test_release_preview_rejects_empty_news(mocker: MockerFixture) -> None:
    mocker.patch.object(sys, "argv", ["release"])
    outputs = ["", "", "4.2.9\n", "4.2.10\n", "4.2.9\n", "", "", "", "", "[PyPI release](https://example.org)\n"]
    run = mocker.patch(
        "tools.release.subprocess.run", autospec=True, side_effect=[_completed(output) for output in outputs]
    )

    with pytest.raises(RuntimeError, match="no user-facing release notes"):
        main()

    assert run.call_count == 10


def test_release_preview_rejects_unsupported_platform(mocker: MockerFixture) -> None:
    mocker.patch.object(sys, "argv", ["release"])
    mocker.patch.object(sys, "platform", "freebsd")
    outputs = ["", "", "4.2.9\n", "4.2.10\n", "4.2.9\n", "", "", "", "", "### Bug fixes\n\n- Fixed output.\n"]
    run = mocker.patch(
        "tools.release.subprocess.run", autospec=True, side_effect=[_completed(output) for output in outputs]
    )

    with pytest.raises(RuntimeError, match="unsupported build platform: freebsd"):
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
