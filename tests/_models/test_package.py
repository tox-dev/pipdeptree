from __future__ import annotations

from importlib.metadata import PackageNotFoundError
from typing import TYPE_CHECKING, Any
from unittest.mock import Mock

import pytest

from pipdeptree._models import DistPackage, ReqPackage

if TYPE_CHECKING:
    from pytest_mock import MockerFixture


def sort_map_values(m: dict[str, Any]) -> dict[str, Any]:
    return {k: sorted(v) for k, v in m.items()}


def test_guess_version_setuptools(mocker: MockerFixture) -> None:
    mocker.patch("pipdeptree._models.package.version", side_effect=PackageNotFoundError)
    result = ReqPackage(mocker.MagicMock(key="setuptools")).installed_version
    assert result == "?"


def test_dist_package_render_as_root() -> None:
    foo = Mock(key="foo", project_name="foo", version="20.4.1")
    dp = DistPackage(foo)
    is_frozen = False
    assert dp.render_as_root(frozen=is_frozen) == "foo==20.4.1"


def test_dist_package_render_as_branch() -> None:
    foo = Mock(key="foo", project_name="foo", version="20.4.1")
    bar = Mock(key="bar", project_name="bar", version="4.1.0")
    bar_req = Mock(key="bar", project_name="bar", version="4.1.0", specs=[(">=", "4.0")])
    rp = ReqPackage(bar_req, dist=bar)
    dp = DistPackage(foo).as_parent_of(rp)
    is_frozen = False
    assert dp.render_as_branch(frozen=is_frozen) == "foo==20.4.1 [requires: bar>=4.0]"


def test_dist_package_as_parent_of() -> None:
    foo = Mock(key="foo", project_name="foo", version="20.4.1")
    dp = DistPackage(foo)
    assert dp.req is None

    bar = Mock(key="bar", project_name="bar", version="4.1.0")
    bar_req = Mock(key="bar", project_name="bar", version="4.1.0", specs=[(">=", "4.0")])
    rp = ReqPackage(bar_req, dist=bar)
    dp1 = dp.as_parent_of(rp)
    assert dp1._obj == dp._obj  # noqa: SLF001
    assert dp1.req is rp

    dp2 = dp.as_parent_of(None)
    assert dp2 is dp


def test_dist_package_as_dict() -> None:
    foo = Mock(key="foo", project_name="foo", version="1.3.2b1")
    dp = DistPackage(foo)
    result = dp.as_dict()
    expected = {"key": "foo", "package_name": "foo", "installed_version": "1.3.2b1"}
    assert expected == result


@pytest.mark.parametrize(
    ("mocked_metadata", "expected_output"),
    [
        pytest.param(
            Mock(get_all=lambda *args, **kwargs: []),  # noqa: ARG005
            DistPackage.UNKNOWN_LICENSE_STR,
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
    dist = DistPackage(Mock(project_name="a"))
    licenses_str = dist.licenses()

    assert licenses_str == expected_output


def test_dist_package_licenses_importlib_cant_find_package(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("pipdeptree._models.package.metadata", Mock(side_effect=PackageNotFoundError()))
    dist = DistPackage(Mock(project_name="a"))
    licenses_str = dist.licenses()

    assert licenses_str == DistPackage.UNKNOWN_LICENSE_STR


def test_req_package_render_as_root() -> None:
    bar = Mock(key="bar", project_name="bar", version="4.1.0")
    bar_req = Mock(key="bar", project_name="bar", version="4.1.0", specs=[(">=", "4.0")])
    rp = ReqPackage(bar_req, dist=bar)
    is_frozen = False
    assert rp.render_as_root(frozen=is_frozen) == "bar==4.1.0"


def test_req_package_render_as_branch() -> None:
    bar = Mock(key="bar", project_name="bar", version="4.1.0")
    bar_req = Mock(key="bar", project_name="bar", version="4.1.0", specs=[(">=", "4.0")])
    rp = ReqPackage(bar_req, dist=bar)
    is_frozen = False
    assert rp.render_as_branch(frozen=is_frozen) == "bar [required: >=4.0, installed: 4.1.0]"


def test_req_package_as_dict() -> None:
    bar = Mock(key="bar", project_name="bar", version="4.1.0")
    bar_req = Mock(key="bar", project_name="bar", version="4.1.0", specs=[(">=", "4.0")])
    rp = ReqPackage(bar_req, dist=bar)
    result = rp.as_dict()
    expected = {"key": "bar", "package_name": "bar", "installed_version": "4.1.0", "required_version": ">=4.0"}
    assert expected == result


def test_req_package_as_dict_with_no_version_spec() -> None:
    bar = Mock(key="bar", project_name="bar", version="4.1.0")
    bar_req = Mock(key="bar", project_name="bar", version="4.1.0", specs=[])
    rp = ReqPackage(bar_req, dist=bar)
    result = rp.as_dict()
    expected = {"key": "bar", "package_name": "bar", "installed_version": "4.1.0", "required_version": "Any"}
    assert expected == result
