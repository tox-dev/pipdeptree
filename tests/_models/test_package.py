from __future__ import annotations

from importlib.metadata import PackageNotFoundError
from typing import TYPE_CHECKING, Any
from unittest.mock import Mock

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
