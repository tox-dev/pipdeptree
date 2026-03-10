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
                and isinstance(r.info, VcsInfo)
                and r.info.vcs == "git"
                and r.info.commit_id == "abc123"
                and r.info.requested_revision is None
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
                },
                "subdirectory": "src/pkg",
            },
            lambda r: (
                r.subdirectory == "src/pkg" and isinstance(r.info, VcsInfo) and r.info.requested_revision == "main"
            ),
            id="vcs-full",
        ),
        pytest.param(
            {"url": "https://example.com/package.tar.gz", "archive_info": {"hash": "sha256=abc123"}},
            lambda r: isinstance(r.info, ArchiveInfo) and r.info.hash == "sha256=abc123",
            id="archive-with-hash",
        ),
        pytest.param(
            {"url": "https://example.com/package.tar.gz", "archive_info": {"hash": "md5=abc"}},
            lambda r: isinstance(r.info, ArchiveInfo) and r.info.hash == "md5=abc",
            id="archive-with-md5",
        ),
        pytest.param(
            {"url": "https://example.com/package.tar.gz", "archive_info": {"hash": "SHA256=ABC"}},
            lambda r: isinstance(r.info, ArchiveInfo) and r.info.hash == "SHA256=ABC",
            id="archive-with-uppercase",
        ),
        pytest.param(
            {"url": "https://example.com/package.tar.gz", "archive_info": {}},
            lambda r: isinstance(r.info, ArchiveInfo) and r.info.hash is None and r.info.hashes == {},
            id="archive-without-hash",
        ),
        pytest.param(
            {"url": "file:///path/to/project", "dir_info": {"editable": True}},
            lambda r: isinstance(r.info, DirInfo) and r.info.editable is True,
            id="dir-editable",
        ),
        pytest.param(
            {"url": "file:///path/to/project", "dir_info": {}},
            lambda r: isinstance(r.info, DirInfo) and r.info.editable is False,
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
        pytest.param(
            '{"url": "https://example.com"}',
            "Missing one of vcs_info, archive_info, or dir_info",
            id="missing-info",
        ),
        pytest.param(
            '{"url": "https://example.com", "vcs_info": {"vcs": "git", "commit_id": "abc"}, "dir_info": {}}',
            "More than one of vcs_info, archive_info, or dir_info",
            id="multiple-infos",
        ),
        pytest.param(
            '{"url": "https://example.com", "vcs_info": {}}',
            "Missing required vcs_info.vcs field",
            id="vcs-missing-vcs",
        ),
        pytest.param(
            '{"url": "https://example.com", "vcs_info": {"vcs": "git"}}',
            "Missing required vcs_info.commit_id field",
            id="vcs-missing-commit-id",
        ),
        pytest.param(
            '{"url": "https://example.com", "dir_info": {"editable": "true"}}',
            "dir_info.editable must be a boolean",
            id="dir-info-editable-not-bool",
        ),
        pytest.param(
            '{"url": 123, "dir_info": {}}',
            "url must be a string",
            id="url-not-string",
        ),
        pytest.param(
            '{"url": "https://example.com", "subdirectory": 123, "dir_info": {}}',
            "subdirectory must be a string",
            id="subdirectory-not-string",
        ),
        pytest.param(
            '{"url": "https://example.com", "vcs_info": "not-a-dict"}',
            "vcs_info must be a dict",
            id="vcs-info-not-dict",
        ),
        pytest.param(
            '{"url": "https://example.com", "archive_info": "not-a-dict"}',
            "archive_info must be a dict",
            id="archive-info-not-dict",
        ),
        pytest.param(
            '{"url": "https://example.com", "dir_info": "not-a-dict"}',
            "dir_info must be a dict",
            id="dir-info-not-dict",
        ),
        pytest.param(
            '{"url": "https://example.com", "vcs_info": {"vcs": 123, "commit_id": "abc"}}',
            "vcs_info.vcs must be a string",
            id="vcs-not-string",
        ),
        pytest.param(
            '{"url": "https://example.com", "vcs_info": {"vcs": "git", "commit_id": 123}}',
            "vcs_info.commit_id must be a string",
            id="commit-id-not-string",
        ),
        pytest.param(
            '{"url": "https://example.com", "vcs_info": {"vcs": "git", "commit_id": "abc", "requested_revision": 123}}',
            "vcs_info.requested_revision must be a string",
            id="requested-revision-not-string",
        ),
        pytest.param(
            '{"url": "https://example.com", "archive_info": {"hash": 123}}',
            "archive_info.hash must be a string",
            id="hash-not-string",
        ),
        pytest.param(
            '{"url": "https://example.com", "archive_info": {"hash": "invalid-hash"}}',
            "invalid archive_info.hash format",
            id="hash-invalid-format",
        ),
        pytest.param(
            '{"url": "https://example.com", "archive_info": {"hashes": "not-a-dict"}}',
            "archive_info.hashes must be a dict",
            id="hashes-not-dict",
        ),
    ],
)
def test_parse_direct_url_json_errors(json_str: str, error_match: str) -> None:
    with pytest.raises(DirectUrlValidationError, match=error_match):
        parse_direct_url_json(json_str)


@pytest.mark.parametrize(
    ("direct_url", "expected"),
    [
        pytest.param(DirectUrl(url="file:///path/to/project", info=DirInfo(editable=True)), True, id="editable-true"),
        pytest.param(
            DirectUrl(url="file:///path/to/project", info=DirInfo(editable=False)), False, id="editable-false"
        ),
        pytest.param(
            DirectUrl(url="https://github.com/user/repo.git", info=VcsInfo(vcs="git", commit_id="abc")),
            False,
            id="vcs-not-editable",
        ),
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


def test_archive_info_hashes_from_json() -> None:
    result = parse_direct_url_json(
        json.dumps({
            "url": "https://example.com/pkg.tar.gz",
            "archive_info": {"hashes": {"sha256": "abc123", "md5": "def456"}},
        })
    )
    assert isinstance(result.info, ArchiveInfo)
    assert result.info.hashes == {"sha256": "abc123", "md5": "def456"}
    assert result.info.hash is None


def test_archive_info_hashes_back_populated_from_hash() -> None:
    result = parse_direct_url_json(
        json.dumps({
            "url": "https://example.com/pkg.tar.gz",
            "archive_info": {"hash": "sha256=abc123"},
        })
    )
    assert isinstance(result.info, ArchiveInfo)
    assert result.info.hashes == {"sha256": "abc123"}


def test_archive_info_hashes_takes_precedence() -> None:
    result = parse_direct_url_json(
        json.dumps({
            "url": "https://example.com/pkg.tar.gz",
            "archive_info": {"hash": "sha256=old", "hashes": {"sha256": "new"}},
        })
    )
    assert isinstance(result.info, ArchiveInfo)
    assert result.info.hashes == {"sha256": "new"}


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        pytest.param("https://example.com/repo.git", "https://example.com/repo.git", id="no-credentials"),
        pytest.param("https://user:pass@example.com/repo.git", "https://example.com/repo.git", id="user-pass"),
        pytest.param("https://git@example.com/repo.git", "https://****@example.com/repo.git", id="user-only"),
        pytest.param("https://token@host/path", "https://****@host/path", id="token-only"),
        pytest.param(
            "https://${TOKEN}@example.com/repo.git",
            "https://${TOKEN}@example.com/repo.git",
            id="env-var",
        ),
        pytest.param("file:///local/path", "file:///local/path", id="file-url"),
        pytest.param("git@github.com:user/repo.git", "git@github.com:user/repo.git", id="scp-style"),
    ],
)
def test_direct_url_redacted_url(url: str, expected: str) -> None:
    du = DirectUrl(url=url, info=DirInfo())
    assert du.redacted_url == expected
