from __future__ import annotations

from email.message import Message
from importlib.metadata import PackageNotFoundError
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock, Mock

import pytest
from packaging.specifiers import SpecifierSet

from pipdeptree._models import DistPackage, ReqPackage
from pipdeptree._models.package import Package

if TYPE_CHECKING:
    from pytest_mock import MockerFixture

    from tests.conftest import MockDistMaker


def sort_map_values(m: dict[str, Any]) -> dict[str, Any]:
    return {k: sorted(v) for k, v in m.items()}


def test_guess_version_setuptools(mocker: MockerFixture) -> None:
    mocker.patch("pipdeptree._models.package.version", side_effect=PackageNotFoundError)
    r = MagicMock()
    r.name = "setuptools"
    result = ReqPackage(r).installed_version
    assert result == "?"


def test_package_as_frozen_repr(mocker: MockerFixture) -> None:
    foo = Mock(metadata={"Name": "foo"}, version="1.2.3")
    dp = DistPackage(foo)
    expected = "test"
    mocker.patch("pipdeptree._models.package.distribution_to_specifier", Mock(return_value=expected))
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
    assert dp.render_as_root(frozen=False) == "foo==20.4.1"


def test_dist_package_render_as_branch() -> None:
    foo = Mock(metadata={"Name": "foo"}, version="20.4.1")
    bar = Mock(metadata={"Name": "bar"}, version="4.1.0")
    bar_req = MagicMock(version="4.1.0", specifier=[">=4.0"])
    bar_req.name = "bar"
    rp = ReqPackage(bar_req, dist=bar)
    dp = DistPackage(foo).as_parent_of(rp)
    assert dp.render_as_branch(frozen=False) == "foo==20.4.1 [requires: bar>=4.0]"


def test_dist_package_render_as_root_with_frozen(mocker: MockerFixture) -> None:
    foo = Mock(metadata={"Name": "foo"}, version="1.2.3")
    dp = DistPackage(foo)
    expected = "test"
    mocker.patch("pipdeptree._models.package.distribution_to_specifier", Mock(return_value=expected))
    assert dp.render_as_root(frozen=True) == expected


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
            Mock(__getitem__=Mock(return_value=None), get_all=Mock(return_value=[])),
            Package.UNKNOWN_LICENSE_STR,
            id="no-license",
        ),
        pytest.param(
            Mock(
                __getitem__=Mock(return_value=None),
                get_all=Mock(
                    return_value=[
                        "License :: OSI Approved :: GNU General Public License v2 (GPLv2)",
                        "Operating System :: OS Independent",
                    ]
                ),
            ),
            "(GNU General Public License v2 (GPLv2))",
            id="one-license-with-one-non-license",
        ),
        pytest.param(
            Mock(
                __getitem__=Mock(return_value=None),
                get_all=Mock(
                    return_value=[
                        "License :: OSI Approved :: GNU General Public License v2 (GPLv2)",
                        "License :: OSI Approved :: Apache Software License",
                    ]
                ),
            ),
            "(GNU General Public License v2 (GPLv2), Apache Software License)",
            id="more-than-one-license",
        ),
        pytest.param(
            Mock(__getitem__=Mock(return_value="MIT"), get_all=Mock(return_value=[])),
            "(MIT)",
            id="license-expression",
        ),
        pytest.param(
            Mock(
                __getitem__=Mock(return_value="MIT"),
                get_all=Mock(
                    return_value=[
                        "License :: OSI Approved :: MIT License",
                    ]
                ),
            ),
            "(MIT)",
            id="license-expression-with-license-classifier",
        ),
    ],
)
def test_dist_package_licenses(mocked_metadata: Mock, expected_output: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("pipdeptree._models.package.metadata", Mock(return_value=mocked_metadata))
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
    bar_req = MagicMock(specifier=[">=4.0"])
    bar_req.name = "bar.bar-bar-bar"
    rp = ReqPackage(bar_req)
    assert rp.key == "bar-bar-bar-bar"


def test_req_package_render_as_root() -> None:
    bar = Mock(metadata={"Name": "bar"}, version="4.1.0")
    bar_req = MagicMock(specifier=[">=4.0"])
    bar_req.name = "bar"
    rp = ReqPackage(bar_req, dist=bar)
    assert rp.render_as_root(frozen=False) == "bar==4.1.0"


def test_req_package_render_as_root_with_frozen(mocker: MockerFixture) -> None:
    bar = Mock(metadata={"Name": "bar"}, version="4.1.0")
    dp = DistPackage(bar)
    bar_req = MagicMock(specifier=[">=4.0"])
    bar_req.name = "bar"
    rp = ReqPackage(bar_req, dp)
    expected = "test"
    mocker.patch("pipdeptree._models.package.distribution_to_specifier", Mock(return_value=expected))
    assert rp.render_as_root(frozen=True) == expected


def test_req_package_render_as_branch() -> None:
    bar = Mock(metadata={"Name": "bar"}, version="4.1.0")
    bar_req = MagicMock(specifier=[">=4.0"])
    bar_req.name = "bar"
    rp = ReqPackage(bar_req, dist=bar)
    assert rp.render_as_branch(frozen=False) == "bar [required: >=4.0, installed: 4.1.0]"


def test_req_package_is_conflicting_handle_dev_versions() -> None:
    # ensure that we can handle development versions when detecting conflicts
    # see https://github.com/tox-dev/pipdeptree/issues/393
    bar = Mock(metadata={"Name": "bar"}, version="1.2.3.dev0")
    bar_req = MagicMock(specifier=SpecifierSet(">1.2.0"))
    bar_req.name = "bar"
    rp = ReqPackage(bar_req, dist=bar)
    assert not rp.is_conflicting()


def test_req_package_as_dict() -> None:
    bar = Mock(metadata={"Name": "bar"}, version="4.1.0")
    bar_req = MagicMock(specifier=[">=4.0"])
    bar_req.name = "bar"
    rp = ReqPackage(bar_req, dist=bar)
    result = rp.as_dict()
    expected = {"key": "bar", "package_name": "bar", "installed_version": "4.1.0", "required_version": ">=4.0"}
    assert expected == result


def test_req_package_as_dict_with_no_version_spec() -> None:
    bar = Mock(key="bar", version="4.1.0")
    bar_req = MagicMock(specifier=[])
    bar_req.name = "bar"
    rp = ReqPackage(bar_req, dist=bar)
    result = rp.as_dict()
    expected = {"key": "bar", "package_name": "bar", "installed_version": "4.1.0", "required_version": "Any"}
    assert expected == result


def test_provides_extras_returns_extras(make_mock_dist: MockDistMaker) -> None:
    dist = make_mock_dist("foo", "1.0.0", provides_extras=["dev", "test"])
    dp = DistPackage(dist)
    assert dp.provides_extras == frozenset({"dev", "test"})


def test_provides_extras_empty_when_none(make_mock_dist: MockDistMaker) -> None:
    dist = make_mock_dist("foo", "1.0.0")
    dp = DistPackage(dist)
    assert dp.provides_extras == frozenset()


def test_requires_for_extras_yields_matching(make_mock_dist: MockDistMaker) -> None:
    dist = make_mock_dist(
        "oauthlib",
        "3.0.0",
        requires=["cryptography ; extra == 'signedtoken'", "pyjwt>=1.0.0 ; extra == 'signedtoken'"],
        provides_extras=["signedtoken", "rsa"],
    )
    dp = DistPackage(dist)
    results = list(dp.requires_for_extras(frozenset({"signedtoken"})))
    assert len(results) == 2
    assert results[0][0].name == "cryptography"
    assert results[0][1] == "signedtoken"
    assert results[1][0].name == "pyjwt"
    assert results[1][1] == "signedtoken"


def test_requires_for_extras_skips_non_matching(make_mock_dist: MockDistMaker) -> None:
    dist = make_mock_dist(
        "oauthlib",
        "3.0.0",
        requires=["cryptography ; extra == 'rsa'"],
        provides_extras=["signedtoken", "rsa"],
    )
    dp = DistPackage(dist)
    results = list(dp.requires_for_extras(frozenset({"signedtoken"})))
    assert len(results) == 0


def test_requires_for_extras_skips_regular_deps(make_mock_dist: MockDistMaker) -> None:
    dist = make_mock_dist(
        "foo",
        "1.0.0",
        requires=["bar>=1.0", "baz ; extra == 'dev'"],
        provides_extras=["dev"],
    )
    dp = DistPackage(dist)
    results = list(dp.requires_for_extras(frozenset({"dev"})))
    assert len(results) == 1
    assert results[0][0].name == "baz"


def test_requires_for_extras_handles_combined_markers(make_mock_dist: MockDistMaker) -> None:
    dist = make_mock_dist(
        "foo",
        "1.0.0",
        requires=["baz ; python_version >= \"3.0\" and extra == 'dev'"],
        provides_extras=["dev"],
    )
    dp = DistPackage(dist)
    results = list(dp.requires_for_extras(frozenset({"dev"})))
    assert len(results) == 1
    assert results[0][0].name == "baz"
    assert results[0][1] == "dev"


def test_requires_for_extras_skips_invalid_requirements(make_mock_dist: MockDistMaker) -> None:
    dist = make_mock_dist(
        "foo",
        "1.0.0",
        requires=["INVALID**req ; extra == 'dev'", "bar ; extra == 'dev'"],
        provides_extras=["dev"],
    )
    dp = DistPackage(dist)
    results = list(dp.requires_for_extras(frozenset({"dev"})))
    assert len(results) == 1
    assert results[0][0].name == "bar"


def test_req_package_render_as_branch_with_extra() -> None:
    bar = Mock(metadata={"Name": "bar"}, version="4.1.0")
    bar_req = MagicMock(specifier=[">=4.0"])
    bar_req.name = "bar"
    rp = ReqPackage(bar_req, dist=bar, extra="dev")
    assert rp.render_as_branch(frozen=False) == "bar [required: >=4.0, installed: 4.1.0, extra: dev]"


def test_req_package_edge_label_with_extra() -> None:
    bar_req = MagicMock(specifier=[">=4.0"])
    bar_req.name = "bar"
    rp = ReqPackage(bar_req, extra="signedtoken")
    assert rp.edge_label == "[signedtoken] >=4.0"


def test_req_package_as_dict_with_extra() -> None:
    bar = Mock(metadata={"Name": "bar"}, version="4.1.0")
    bar_req = MagicMock(specifier=[">=4.0"])
    bar_req.name = "bar"
    rp = ReqPackage(bar_req, dist=bar, extra="dev")
    result = rp.as_dict()
    assert result["extra"] == "dev"


def test_req_package_as_dict_without_extra() -> None:
    bar = Mock(metadata={"Name": "bar"}, version="4.1.0")
    bar_req = MagicMock(specifier=[">=4.0"])
    bar_req.name = "bar"
    rp = ReqPackage(bar_req, dist=bar)
    assert "extra" not in rp.as_dict()


def test_dist_package_render_as_branch_with_extra() -> None:
    foo = Mock(metadata={"Name": "foo"}, version="1.0.0")
    bar_req = MagicMock(specifier=[">=4.0"])
    bar_req.name = "bar"
    rp = ReqPackage(bar_req, dist=Mock(metadata={"Name": "bar"}, version="4.0.0"), extra="dev")
    dp = DistPackage(foo).as_parent_of(rp)
    assert dp.render_as_branch(frozen=False) == "foo==1.0.0 [requires: bar>=4.0, extra: dev]"


def test_dist_package_edge_label_with_extra() -> None:
    foo = Mock(metadata={"Name": "foo"}, version="1.0.0")
    bar_req = MagicMock(specifier=[">=4.0"])
    bar_req.name = "bar"
    rp = ReqPackage(bar_req, extra="signedtoken")
    dp = DistPackage(foo).as_parent_of(rp)
    assert dp.edge_label == "[signedtoken] >=4.0"


def test_get_metadata_license(mocker: MockerFixture) -> None:
    mocker.patch.object(Package, "licenses", return_value="(MIT)")
    dist = MagicMock(metadata={"Name": "foo"}, version="1.0")
    assert DistPackage(dist).get_metadata("license") == "MIT License"


def test_get_metadata_arbitrary_field(mocker: MockerFixture) -> None:

    msg = Message()
    msg["Summary"] = "A package"
    mocker.patch("pipdeptree._models.package.metadata", return_value=msg)
    dist = MagicMock(metadata={"Name": "foo"}, version="1.0")
    assert DistPackage(dist).get_metadata("Summary") == "A package"


def test_get_metadata_missing_field(mocker: MockerFixture) -> None:

    mocker.patch("pipdeptree._models.package.metadata", return_value=Message())
    dist = MagicMock(metadata={"Name": "foo"}, version="1.0")
    assert DistPackage(dist).get_metadata("Nonexistent") == "Unknown"


def test_get_metadata_unknown_package(mocker: MockerFixture) -> None:
    mocker.patch("pipdeptree._models.package.metadata", side_effect=PackageNotFoundError("x"))
    dist = MagicMock(metadata={"Name": "foo"}, version="1.0")
    assert DistPackage(dist).get_metadata("Summary") == "Unknown"


def test_get_metadata_dict(mocker: MockerFixture) -> None:

    mocker.patch.object(Package, "licenses", return_value="(MIT)")
    msg = Message()
    msg["Summary"] = "A package"
    mocker.patch("pipdeptree._models.package.metadata", return_value=msg)
    dist = MagicMock(metadata={"Name": "foo"}, version="1.0")
    result = DistPackage(dist).get_metadata_dict(["license", "Summary"])
    assert result == {"license": "MIT License", "Summary": "A package"}


def test_get_metadata_multi_value(mocker: MockerFixture) -> None:

    msg = Message()
    msg["Classifier"] = "Development Status :: 5 - Production/Stable"
    msg["Classifier"] = "License :: OSI Approved :: MIT License"
    msg["Classifier"] = "Programming Language :: Python :: 3"
    mocker.patch("pipdeptree._models.package.metadata", return_value=msg)
    dist = MagicMock(metadata={"Name": "foo"}, version="1.0")
    result = DistPackage(dist).get_metadata("Classifier")
    assert result == [
        "Development Status :: 5 - Production/Stable",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
    ]


def test_get_metadata_values_with_multi_value(mocker: MockerFixture) -> None:

    msg = Message()
    msg["Classifier"] = "Development Status :: 5 - Production/Stable"
    msg["Classifier"] = "License :: OSI Approved :: MIT License"
    mocker.patch("pipdeptree._models.package.metadata", return_value=msg)
    mocker.patch.object(Package, "licenses", return_value="(MIT)")
    dist = MagicMock(metadata={"Name": "foo"}, version="1.0")
    result = DistPackage(dist).get_metadata_values(["license", "Classifier"])
    assert result == [
        "MIT License",
        "Development Status :: 5 - Production/Stable",
        "License :: OSI Approved :: MIT License",
    ]


def test_get_metadata_dict_with_multi_value(mocker: MockerFixture) -> None:

    msg = Message()
    msg["Classifier"] = "Development Status :: 5 - Production/Stable"
    msg["Classifier"] = "License :: OSI Approved :: MIT License"
    mocker.patch("pipdeptree._models.package.metadata", return_value=msg)
    dist = MagicMock(metadata={"Name": "foo"}, version="1.0")
    result = DistPackage(dist).get_metadata_dict(["Classifier"])
    assert result == {
        "Classifier": [
            "Development Status :: 5 - Production/Stable",
            "License :: OSI Approved :: MIT License",
        ],
    }


def test_get_metadata_values(mocker: MockerFixture) -> None:
    mocker.patch.object(Package, "licenses", return_value="(MIT)")
    dist = MagicMock(metadata={"Name": "foo"}, version="1.0")
    assert DistPackage(dist).get_metadata_values(["license"]) == ["MIT License"]
