from __future__ import annotations

import locale
from importlib.metadata import Distribution, PackageMetadata
from pathlib import Path
from random import shuffle
from typing import TYPE_CHECKING, Protocol
from unittest.mock import Mock

import pytest

from pipdeptree._models import PackageDAG

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator

    from pytest_mock import MockerFixture

    from tests.our_types import MockGraph


@pytest.fixture(scope="session")
def mock_pkgs() -> Callable[[MockGraph], Iterator[Mock]]:
    def func(simple_graph: MockGraph) -> Iterator[Mock]:
        for node, children in simple_graph.items():
            nk, nv = node
            m = Mock(metadata={"Name": nk}, version=nv)
            reqs = []
            for ck, cv in children:
                r = ck
                for item in cv:
                    if item:
                        rs, rv = item
                        r = r + rs + rv
                    if item != cv[-1]:
                        r += ","
                reqs.append(r)
            m.requires = reqs
            yield m

    return func


@pytest.fixture
def example_dag(mock_pkgs: Callable[[MockGraph], Iterator[Mock]]) -> PackageDAG:
    packages: MockGraph = {
        ("a", "3.4.0"): [("b", [(">=", "2.0.0")]), ("c", [(">=", "5.7.1")])],
        ("b", "2.3.1"): [("d", [(">=", "2.30"), ("<", "2.42")])],
        ("c", "5.10.0"): [("d", [(">=", "2.30")]), ("e", [(">=", "0.12.1")])],
        ("d", "2.35"): [("e", [(">=", "0.9.0")])],
        ("e", "0.12.1"): [],
        ("f", "3.1"): [("b", [(">=", "2.1.0")])],
        ("g", "6.8.3rc1"): [("e", [(">=", "0.9.0")]), ("f", [(">=", "3.0.0")])],
    }
    return PackageDAG.from_pkgs(list(mock_pkgs(packages)))


@pytest.fixture
def randomized_example_dag(example_dag: PackageDAG) -> PackageDAG:
    """Returns a copy of the package tree fixture with dependencies in randomized order."""
    # Extract the dependency graph from the package tree and randomize it.
    randomized_graph = {}
    randomized_nodes = list(example_dag._obj.keys())  # noqa: SLF001
    shuffle(randomized_nodes)
    for node in randomized_nodes:
        edges = example_dag._obj[node].copy()  # noqa: SLF001
        shuffle(edges)
        randomized_graph[node] = edges
    assert set(randomized_graph) == set(example_dag._obj)  # noqa: SLF001

    # Create a randomized package tree.
    randomized_dag = PackageDAG(randomized_graph)
    assert len(example_dag) == len(randomized_dag)
    return randomized_dag


class MockDistMaker(Protocol):
    def __call__(
        self,
        name: str,
        version: str,
        requires: list[str] | None = None,
        provides_extras: list[str] | None = None,
        *,
        license_expression: str | None = None,
        requires_python: list[str] | None = None,
    ) -> Distribution: ...


@pytest.fixture
def make_mock_dist(mocker: MockerFixture) -> MockDistMaker:
    def func(
        name: str,
        version: str,
        requires: list[str] | None = None,
        provides_extras: list[str] | None = None,
        *,
        license_expression: str | None = None,
        requires_python: list[str] | None = None,
    ) -> Distribution:
        metadata = mocker.create_autospec(PackageMetadata, instance=True)
        metadata.__getitem__.side_effect = {"Name": name, "License-Expression": license_expression}.get
        get_all = {"Provides-Extra": provides_extras, "Requires-Python": requires_python}
        metadata.get_all.side_effect = lambda key, failobj=None: get_all.get(key, failobj)
        dist = mocker.create_autospec(Distribution, instance=True)
        dist.metadata = metadata
        dist.version = version
        dist.requires = requires
        return dist

    return func


@pytest.fixture
def fake_dist(tmp_path: Path) -> Path:
    """Creates a fake site package (that you get using Path.parent) and a fake dist-info called bar-2.4.5.dist-info."""
    fake_site_pkgs = tmp_path / "site-packages"
    fake_dist_path = fake_site_pkgs / "bar-2.4.5.dist-info"
    fake_dist_path.mkdir(parents=True)
    fake_metadata = Path(fake_dist_path) / "METADATA"
    with fake_metadata.open("w", encoding=locale.getpreferredencoding(False)) as f:
        f.write("Metadata-Version: 2.3\nName: bar\nVersion: 2.4.5\n")

    return fake_dist_path


@pytest.fixture
def fake_dist_with_invalid_metadata(tmp_path: Path) -> Path:
    "Similar to `fake_dist()`, but creates an invalid METADATA file."
    fake_site_pkgs = tmp_path / "site-packages"
    fake_dist_path = fake_site_pkgs / "bar-2.4.5.dist-info"
    fake_dist_path.mkdir(parents=True)
    fake_metadata = Path(fake_dist_path) / "METADATA"
    fake_metadata.touch()
    return fake_dist_path
