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


def _completed(stdout: str = "") -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(args=(), returncode=0, stdout=stdout)


@pytest.mark.parametrize(
    "docstrfmt_failures",
    [
        pytest.param([], id="unchanged"),
        pytest.param([subprocess.CalledProcessError(1, "prek")], id="formatted"),
    ],
)
@pytest.mark.parametrize(
    ("previous", "previous_args"),
    [
        pytest.param("4.2.9", ("--previous", "4.2.9"), id="later-release"),
        pytest.param("", (), id="first-release"),
    ],
)
def test_release_preview_checks_notes_and_packages(
    mocker: MockerFixture,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
    docstrfmt_failures: list[subprocess.CalledProcessError],
    previous: str,
    previous_args: tuple[str, ...],
) -> None:
    mocker.patch.object(sys, "argv", ["release", "--bump", "patch"])
    mocker.patch("tools.release.TemporaryDirectory", autospec=True, return_value=nullcontext(str(tmp_path)))
    outputs = [""] * 15
    outputs[1:4] = ["4.2.9\n", "4.2.10\n", previous]
    outputs[9] = "### Bug fixes\n\n- Fixed output.\n"
    outputs[12] = "1792696343\n"
    responses: list[subprocess.CompletedProcess[str] | subprocess.CalledProcessError] = [
        *(_completed(output) for output in outputs[:7]),
        *docstrfmt_failures,
        *(_completed(output) for output in outputs[7:]),
    ]
    run = mocker.patch("tools.release.subprocess.run", autospec=True, side_effect=responses)
    retries = len(docstrfmt_failures)

    main()

    assert capsys.readouterr().out == "### Bug fixes\n\n- Fixed output.\n"
    commands = [call.args[0] for call in run.call_args_list]
    assert commands[2][:5] == ("release-creator", "tags", "--next", "patch", "--directory")
    assert commands[6] == (
        "release-creator",
        "contributors",
        "--changelog",
        "docs/changelog.rst",
        "--version",
        "4.2.10",
        "--repository",
        "tox-dev/pipdeptree",
    )
    assert commands.count(("prek", "run", "docstrfmt", "--files", "docs/changelog.rst")) == 1 + retries
    assert commands[9 + retries] == (
        "release-creator",
        "notes",
        "--changelog",
        "docs/changelog.rst",
        "--tag",
        "4.2.10",
        "--repository",
        "tox-dev/pipdeptree",
        "--artifact-url",
        "https://pypi.org/project/pipdeptree/4.2.10/",
        *previous_args,
    )
    assert commands[10 + retries][:3] == ("uv", "venv", "--python")
    assert commands[11 + retries][:3] == ("uv", "pip", "sync")
    assert "pylock.build.toml" in commands[11 + retries]
    assert commands[12 + retries] == ("git", "log", "-1", "--format=%ct")
    assert commands[13 + retries][:3] == ("uv", "build", "--sdist")
    assert "--no-build-isolation" in commands[13 + retries]
    env = run.call_args_list[13 + retries].kwargs["env"]
    assert (env["PIPDEPTREE_VERSION"], env["SOURCE_DATE_EPOCH"]) == ("4.2.10", "1792696343")
    assert commands[-1] == (sys.executable, "tools/check_release_wheels.py", "dist")
    assert all(call.kwargs["stdout"] is sys.stderr for call in run.call_args_list if not call.kwargs["capture_output"])
    assert all(command[:2] != ("git", "push") for command in commands)
    assert all(command[:2] != ("git", "tag") or command[2:] == ("--list",) for command in commands)


def test_release_preview_stops_when_notes_fail(mocker: MockerFixture) -> None:
    mocker.patch.object(sys, "argv", ["release"])
    outputs = ["", "4.2.9\n", "4.2.10\n", "4.2.9\n", "", "", "", "", ""]
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
