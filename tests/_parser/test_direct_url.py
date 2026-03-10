from __future__ import annotations

import json
from typing import TYPE_CHECKING
from unittest.mock import Mock

import pytest

from pipdeptree._parser._direct_url import (
    ArchiveInfo,
    DirectUrl,
    DirectUrlValidationError,
    DirInfo,
    VcsInfo,
    get_direct_url,
    parse_direct_url_json,
)

if TYPE_CHECKING:
    from collections.abc import Callable


@pytest.mark.parametrize(
    ("json_data", "check_fn"),
    [
        pytest.param(
            {
                "url": "https://github.com/user/repo.git",
                "vcs_info": {"vcs": "git", "commit_id": "abc123"},
            },
            lambda r: (
                r.url == "https://github.com/user/repo.git"
                and r.vcs_info is not None
                and r.vcs_info.vcs == "git"
                and r.vcs_info.commit_id == "abc123"
                and r.vcs_info.requested_revision is None
            ),
            id="vcs-minimal",
        ),
        pytest.param(
            {
                "url": "https://github.com/user/repo.git",
                "vcs_info": {
                    "vcs": "git",
                    "commit_id": "abc123",
                    "requested_revision": "main",
                    "resolved_revision": "v1.0.0",
                    "resolved_revision_type": "tag",
                },
                "subdirectory": "src/pkg",
            },
            lambda r: (
                r.subdirectory == "src/pkg"
                and r.vcs_info is not None
                and r.vcs_info.requested_revision == "main"
                and r.vcs_info.resolved_revision_type == "tag"
            ),
            id="vcs-full",
        ),
        pytest.param(
            {
                "url": "https://github.com/user/repo.git",
                "vcs_info": {"vcs": "git", "commit_id": "abc123", "resolved_revision_type": "branch"},
            },
            lambda r: r.vcs_info is not None and r.vcs_info.resolved_revision_type == "branch",
            id="vcs-branch-type",
        ),
        pytest.param(
            {
                "url": "https://github.com/user/repo.git",
                "vcs_info": {"vcs": "git", "commit_id": "abc123", "resolved_revision_type": "invalid"},
            },
            lambda r: r.vcs_info is not None and r.vcs_info.resolved_revision_type is None,
            id="vcs-invalid-revision-type",
        ),
        pytest.param(
            {"url": "https://example.com/package.tar.gz", "archive_info": {"hash": "sha256=abc123"}},
            lambda r: r.archive_info is not None and r.archive_info.hash_value == "sha256=abc123",
            id="archive-with-hash",
        ),
        pytest.param(
            {"url": "https://example.com/package.tar.gz", "archive_info": {}},
            lambda r: r.archive_info is not None and r.archive_info.hash_value is None,
            id="archive-without-hash",
        ),
        pytest.param(
            {"url": "file:///path/to/project", "dir_info": {"editable": True}},
            lambda r: r.dir_info is not None and r.dir_info.editable is True,
            id="dir-editable",
        ),
        pytest.param(
            {"url": "file:///path/to/project", "dir_info": {}},
            lambda r: r.dir_info is not None and r.dir_info.editable is False,
            id="dir-not-editable",
        ),
    ],
)
def test_parse_direct_url_json(json_data: dict, check_fn: Callable[[DirectUrl], bool]) -> None:
    result = parse_direct_url_json(json.dumps(json_data))
    assert check_fn(result)


@pytest.mark.parametrize(
    ("json_str", "error_match"),
    [
        pytest.param("not json", "Invalid JSON", id="invalid-json"),
        pytest.param("[]", "must be a JSON object", id="not-dict"),
        pytest.param('{"vcs_info": {}}', "Missing required 'url' field", id="missing-url"),
    ],
)
def test_parse_direct_url_json_errors(json_str: str, error_match: str) -> None:
    with pytest.raises(DirectUrlValidationError, match=error_match):
        parse_direct_url_json(json_str)


@pytest.mark.parametrize(
    ("direct_url", "expected"),
    [
        pytest.param(
            DirectUrl(url="https://github.com/user/repo.git", vcs_info=VcsInfo(vcs="git", commit_id="abc")),
            "vcs",
            id="vcs",
        ),
        pytest.param(
            DirectUrl(url="https://example.com/pkg.tar.gz", archive_info=ArchiveInfo()), "archive", id="archive"
        ),
        pytest.param(DirectUrl(url="file:///path/to/project", dir_info=DirInfo()), "dir", id="dir"),
        pytest.param(DirectUrl(url="https://example.com"), None, id="none"),
    ],
)
def test_direct_url_info_type(direct_url: DirectUrl, expected: str | None) -> None:
    assert direct_url.info_type == expected


@pytest.mark.parametrize(
    ("direct_url", "expected"),
    [
        pytest.param(
            DirectUrl(url="file:///path/to/project", dir_info=DirInfo(editable=True)), True, id="editable-true"
        ),
        pytest.param(
            DirectUrl(url="file:///path/to/project", dir_info=DirInfo(editable=False)), False, id="editable-false"
        ),
        pytest.param(DirectUrl(url="https://github.com/user/repo.git"), False, id="no-dir-info"),
    ],
)
def test_direct_url_is_editable(direct_url: DirectUrl, expected: bool) -> None:
    assert direct_url.is_editable() is expected


def test_get_direct_url_success() -> None:
    dist = Mock()
    dist.read_text.return_value = json.dumps({
        "url": "https://github.com/user/repo.git",
        "vcs_info": {"vcs": "git", "commit_id": "abc123"},
    })
    result = get_direct_url(dist)
    assert result is not None
    assert result.url == "https://github.com/user/repo.git"


@pytest.mark.parametrize(
    "setup_fn",
    [
        pytest.param(lambda: Mock(read_text=Mock(return_value=None)), id="no-file"),
        pytest.param(lambda: Mock(read_text=Mock(return_value="")), id="empty-string"),
        pytest.param(
            lambda: Mock(read_text=Mock(side_effect=UnicodeDecodeError("utf-8", b"", 0, 1, "invalid"))),
            id="unicode-decode-error",
        ),
        pytest.param(lambda: Mock(read_text=Mock(return_value='{"invalid": "json"}')), id="validation-error"),
    ],
)
def test_get_direct_url_returns_none(setup_fn: Callable[[], Mock]) -> None:
    dist = setup_fn()
    result = get_direct_url(dist)
    assert result is None
