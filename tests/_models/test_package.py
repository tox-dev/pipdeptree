from __future__ import annotations

import sys
from importlib.metadata import PackageNotFoundError
from pathlib import Path
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock, Mock

import pytest

from pipdeptree._models import DistPackage, ReqPackage
from pipdeptree._models.package import Package

if TYPE_CHECKING:
    from pytest_mock import MockerFixture


def sort_map_values(m: dict[str, Any]) -> dict[str, Any]:
    return {k: sorted(v) for k, v in m.items()}


def test_guess_version_setuptools(mocker: MockerFixture) -> None:
    mocker.patch("pipdeptree._models.package.version", side_effect=PackageNotFoundError)
    r = MagicMock()
    r.name = "setuptools"
    result = ReqPackage(r).installed_version
    assert result == "?"


def test_package_as_frozen_repr(tmp_path: Path, mocker: MockerFixture) -> None:
    file_path = tmp_path / "foo.egg-link"
    with Path(file_path).open("w") as f:
        f.write("/A/B/foo")
    mock_path = sys.path.copy()
    mock_path.append(str(tmp_path))
    mocker.patch("pipdeptree._discovery.sys.path", mock_path)
    json_text = '{"dir_info": {"editable": true}}'
    foo = Mock(metadata={"Name": "foo"}, version="20.4.1")
    foo.read_text = Mock(return_value=json_text)
    dp = DistPackage(foo)
    expected = "# Editable install with no version control (foo==20.4.1)\n-e /A/B/foo"
    assert Package.as_frozen_repr(dp.unwrap()) == expected


def test_dist_package_requires() -> None:
    foo = Mock(
        metadata={"Name": "foo"},
        requires=["bar", "baz >=2.7.2"],
    )
    dp = DistPackage(foo)
    reqs = list(dp.requires())
    assert len(reqs) == 2


def test_dist_package_requires_with_environment_markers_that_eval_to_false() -> None:
    foo = Mock(
        metadata={"Name": "foo"},
        requires=['foo ; sys_platform == "NoexistOS"', "bar >=2.7.2 ; extra == 'testing'"],
    )
    dp = DistPackage(foo)
    reqs = list(dp.requires())
    assert len(reqs) == 0


def test_dist_package_render_as_root() -> None:
    foo = Mock(metadata={"Name": "foo"}, version="20.4.1")
    dp = DistPackage(foo)
    is_frozen = False
    assert dp.render_as_root(frozen=is_frozen) == "foo==20.4.1"


def test_dist_package_render_as_branch() -> None:
    foo = Mock(metadata={"Name": "foo"}, version="20.4.1")
    bar = Mock(metadata={"Name": "bar"}, version="4.1.0")
    bar_req = MagicMock(version="4.1.0", specifier=[">=4.0"])
    bar_req.name = "bar"
    rp = ReqPackage(bar_req, dist=bar)
    dp = DistPackage(foo).as_parent_of(rp)
    is_frozen = False
    assert dp.render_as_branch(frozen=is_frozen) == "foo==20.4.1 [requires: bar>=4.0]"


def test_dist_package_render_as_root_with_frozen() -> None:
    json_text = '{"dir_info": {"editable": true}, "url": "file:///A/B/foo"}'
    foo = Mock(metadata={"Name": "foo"}, version="20.4.1")
    foo.read_text = Mock(return_value=json_text)
    dp = DistPackage(foo)
    is_frozen = True
    expect = "# Editable install with no version control (foo==20.4.1)\n-e /A/B/foo"
    assert dp.render_as_root(frozen=is_frozen) == expect


def test_dist_package_as_parent_of() -> None:
    foo = Mock(metadata={"Name": "foo"}, version="20.4.1")
    dp = DistPackage(foo)
    assert dp.req is None

    bar = Mock(metadata={"Name": "bar"}, version="4.1.0")
    bar_req = MagicMock(version="4.1.0", specifier=[">=4.0"])
    bar_req.name = "bar"
    rp = ReqPackage(bar_req, dist=bar)
    dp1 = dp.as_parent_of(rp)
    assert dp1._obj == dp._obj  # noqa: SLF001
    assert dp1.req is rp

    dp2 = dp.as_parent_of(None)
    assert dp2 is dp


def test_dist_package_as_dict() -> None:
    foo = Mock(metadata={"Name": "foo"}, version="1.3.2b1")
    dp = DistPackage(foo)
    result = dp.as_dict()
    expected = {"key": "foo", "package_name": "foo", "installed_version": "1.3.2b1"}
    assert expected == result


@pytest.mark.parametrize(
    ("mocked_metadata", "expected_output"),
    [
        pytest.param(
            Mock(get_all=lambda *args, **kwargs: []),  # noqa: ARG005
            Package.UNKNOWN_LICENSE_STR,
            id="no-license",
        ),
        pytest.param(
            Mock(
                get_all=lambda *args, **kwargs: [  # noqa: ARG005
                    "License :: OSI Approved :: GNU General Public License v2 (GPLv2)",
                    "Operating System :: OS Independent",
                ]
            ),
            "(GNU General Public License v2 (GPLv2))",
            id="one-license-with-one-non-license",
        ),
        pytest.param(
            Mock(
                get_all=lambda *args, **kwargs: [  # noqa: ARG005
                    "License :: OSI Approved :: GNU General Public License v2 (GPLv2)",
                    "License :: OSI Approved :: Apache Software License",
                ]
            ),
            "(GNU General Public License v2 (GPLv2), Apache Software License)",
            id="more-than-one-license",
        ),
    ],
)
def test_dist_package_licenses(mocked_metadata: Mock, expected_output: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("pipdeptree._models.package.metadata", lambda _: mocked_metadata)
    dist = DistPackage(Mock(metadata={"Name": "a"}))
    licenses_str = dist.licenses()

    assert licenses_str == expected_output


def test_dist_package_licenses_importlib_cant_find_package(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("pipdeptree._models.package.metadata", Mock(side_effect=PackageNotFoundError()))
    dist = DistPackage(Mock(metadata={"Name": "a"}))
    licenses_str = dist.licenses()

    assert licenses_str == Package.UNKNOWN_LICENSE_STR


def test_dist_package_key_pep503_normalized() -> None:
    foobar = Mock(metadata={"Name": "foo.bar"}, version="20.4.1")
    dp = DistPackage(foobar)
    assert dp.key == "foo-bar"


def test_req_package_key_pep503_normalized() -> None:
    bar_req = MagicMock(version="4.1.0", specifier=[">=4.0"])
    bar_req.name = "bar.bar-bar-bar"
    rp = ReqPackage(bar_req)
    assert rp.key == "bar-bar-bar-bar"


def test_req_package_render_as_root() -> None:
    bar = Mock(metadata={"Name": "bar"}, version="4.1.0")
    bar_req = MagicMock(version="4.1.0", specifier=[">=4.0"])
    bar_req.name = "bar"
    rp = ReqPackage(bar_req, dist=bar)
    is_frozen = False
    assert rp.render_as_root(frozen=is_frozen) == "bar==4.1.0"


def test_req_package_render_as_root_with_frozen() -> None:
    json_text = '{"dir_info": {"editable": true}, "url": "file:///A/B/bar"}'
    bar = Mock(metadata={"Name": "bar"}, version="4.1.0")
    bar.read_text = Mock(return_value=json_text)
    d = DistPackage(bar)
    bar_req = MagicMock(version="4.1.0", specifier=[">=4.0"])
    bar_req.name = "bar"
    rp = ReqPackage(bar_req, dist=d)
    is_frozen = True
    expect = "# Editable install with no version control (bar==4.1.0)\n-e /A/B/bar"
    assert rp.render_as_root(frozen=is_frozen) == expect


def test_req_package_render_as_branch() -> None:
    bar = Mock(metadata={"Name": "bar"}, version="4.1.0")
    bar_req = MagicMock(version="4.1.0", specifier=[">=4.0"])
    bar_req.name = "bar"
    rp = ReqPackage(bar_req, dist=bar)
    is_frozen = False
    assert rp.render_as_branch(frozen=is_frozen) == "bar [required: >=4.0, installed: 4.1.0]"


def test_req_package_as_dict() -> None:
    bar = Mock(metadata={"Name": "bar"}, version="4.1.0")
    bar_req = MagicMock(version="4.1.0", specifier=[">=4.0"])
    bar_req.name = "bar"
    rp = ReqPackage(bar_req, dist=bar)
    result = rp.as_dict()
    expected = {"key": "bar", "package_name": "bar", "installed_version": "4.1.0", "required_version": ">=4.0"}
    assert expected == result


def test_req_package_as_dict_with_no_version_spec() -> None:
    bar = Mock(key="bar", version="4.1.0")
    bar_req = MagicMock(version="4.1.0", specifier=[])
    bar_req.name = "bar"
    rp = ReqPackage(bar_req, dist=bar)
    result = rp.as_dict()
    expected = {"key": "bar", "package_name": "bar", "installed_version": "4.1.0", "required_version": "Any"}
    assert expected == result
