from __future__ import annotations

from importlib import metadata
from pathlib import Path
from typing import TYPE_CHECKING, Final, cast

import pytest

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

_ROOT: Final = Path(__file__).parents[1]


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption("--update-docs", action="store_true", help="rewrite documented console outputs in place")
    parser.addoption("--online", action="store_true", help="also run console examples marked runs-online")


@pytest.fixture
def update_docs(request: pytest.FixtureRequest) -> bool:
    return bool(request.config.getoption("--update-docs"))


@pytest.fixture
def online(request: pytest.FixtureRequest) -> bool:
    return bool(request.config.getoption("--online"))


def pytest_generate_tests(metafunc: pytest.Metafunc) -> None:
    if "console_document" not in metafunc.fixturenames:
        return
    documents = sorted(
        path for path in (_ROOT / "docs").rglob("*.rst") if "$ pipdeptree" in path.read_text(encoding="utf-8")
    )
    metafunc.parametrize(
        "console_document",
        documents,
        ids=[str(path.relative_to(_ROOT)) for path in documents],
    )


@pytest.fixture
def entry_point() -> Callable[[Sequence[str] | None], int | None]:
    console_script = metadata.distribution("pipdeptree").entry_points["pipdeptree"]
    return cast("Callable[[Sequence[str] | None], int | None]", console_script.load())


@pytest.fixture
def package_path(tmp_path: Path) -> Path:
    packages = {
        "root-1.dist-info": (
            "Name: root\nVersion: 1\nRequires-Dist: child>=1\n"
            "Requires-Dist: optional; extra == 'feature'\nProvides-Extra: feature\n"
            "License-Expression: MIT\nRequires-Python: >=3.10\n"
        ),
        "child-1.dist-info": "Name: child\nVersion: 1\nLicense: BSD-3-Clause\n",
        "optional-1.dist-info": "Name: optional\nVersion: 1\n",
        "orphan-1.dist-info": "Name: orphan\nVersion: 1\n",
    }
    for directory, metadata_text in packages.items():
        path = tmp_path / directory
        path.mkdir()
        (path / "METADATA").write_text(metadata_text)
    return tmp_path


@pytest.fixture
def conflicting_documentation_path(tmp_path_factory: pytest.TempPathFactory) -> Path:
    root = tmp_path_factory.mktemp("conflicting")
    packages: Final = {
        "Jinja2-2.11.2.dist-info": "Name: Jinja2\nVersion: 2.11.2\nRequires-Dist: MarkupSafe>=0.23\n",
        "MarkupSafe-0.22.dist-info": "Name: MarkupSafe\nVersion: 0.22\n",
    }
    for directory, metadata_text in packages.items():
        path = root / directory
        path.mkdir()
        (path / "METADATA").write_text(metadata_text)
    return root


@pytest.fixture
def documentation_path(tmp_path: Path) -> Path:
    package_metadata: Final = {
        "pipdeptree": ("License-Expression: MIT\nSummary: Display installed Python package dependencies as a tree\n"),
        "pytest": "License-Expression: MIT\nRequires-Python: >=3.10\n",
        "iniconfig": "License-Expression: MIT\n",
        "pluggy": "License: MIT License\n",
        "packaging": "License-Expression: Apache-2.0 OR BSD-2-Clause\n",
        "Pygments": "License-Expression: BSD-2-Clause\n",
        "requests": "Provides-Extra: socks\n",
        "oauthlib": "Provides-Extra: signedtoken\n",
    }
    distributions = {
        "build": ("1.5.1", ("packaging>=24.0", "pyproject_hooks")),
        "chardet": ("7.4.3", ()),
        "covdefaults": ("2.3.0", ("coverage>=6.0.2",)),
        "coverage": ("7.15.1", ()),
        "diff_cover": (
            "10.3.0",
            ("chardet>=3.0.0", "Jinja2>=2.7.1", "pluggy>=0.13.1,<2", "Pygments>=2.19.1,<3.0.0"),
        ),
        "certifi": ("2024.8.30", ()),
        "charset_normalizer": ("3.4.0", ()),
        "cryptography": ("2.7", ()),
        "idna": ("3.10", ()),
        "iniconfig": ("2.3.0", ()),
        "installer": ("1.0.1", ()),
        "Jinja2": ("3.1.6", ("MarkupSafe>=2.0",)),
        "MarkupSafe": ("3.0.3", ()),
        "oauthlib": (
            "3.0.0",
            ("cryptography; extra == 'signedtoken'", "pyjwt>=1.0.0; extra == 'signedtoken'"),
        ),
        "pyjwt": ("1.7.1", ()),
        "PySocks": ("1.7.1", ()),
        "requests": (
            "2.32.3",
            (
                "certifi>=2017.4.17",
                "charset_normalizer>=2,<4",
                "idna>=2.5,<4",
                "urllib3>=1.21.1,<3",
                "PySocks>=1.5.6,!=1.5.7; extra == 'socks'",
            ),
        ),
        "nab-index": (
            "0.0.8",
            ("packaging>=24.0", "truststore>=0.10", "typing_extensions>=4.6", "urllib3>=2.0"),
        ),
        "nab-python": (
            "0.0.8",
            (
                "build>=1.2",
                "installer>=0.7",
                "nab-index==0.0.8",
                "nab-resolver==0.0.8",
                "pyproject_hooks>=1.2",
                "tomli>=2.0",
                "tomli_w>=1.2",
                "typing_extensions>=4.6",
            ),
        ),
        "nab-resolver": ("0.0.8", ("typing_extensions>=4.6",)),
        "packaging": ("26.2", ()),
        "pipdeptree": ("4.0.0", ("nab-index>=0.0.8", "nab-python>=0.0.8")),
        "pluggy": ("1.6.0", ()),
        "Pygments": ("2.20.0", ()),
        "pyproject_hooks": ("1.2.0", ()),
        "pytest": ("9.1.1", ("iniconfig>=1.0.1", "packaging>=22", "pluggy>=1.5,<2", "Pygments>=2.7.2")),
        "pytest-cov": ("7.1.0", ("coverage>=7.10.6", "pluggy>=1.2", "pytest>=7")),
        "tomli": ("2.4.1", ()),
        "tomli_w": ("1.2.0", ()),
        "truststore": ("0.10.4", ()),
        "typing_extensions": ("4.16.0", ()),
        "urllib3": ("2.7.0", ()),
    }
    for name, (version, requirements) in distributions.items():
        metadata_dir = tmp_path / f"{name}-{version}.dist-info"
        metadata_dir.mkdir()
        requires = "".join(f"Requires-Dist: {requirement}\n" for requirement in requirements)
        (metadata_dir / "METADATA").write_text(
            f"Name: {name}\nVersion: {version}\n{requires}{package_metadata.get(name, '')}"
        )
    return tmp_path
