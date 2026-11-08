"""Build docs against the installed pipdeptree version."""

from __future__ import annotations

import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Final

from pipdeptree.version import __version__

company: Final[str] = "tox-dev"
name: Final[str] = "pipdeptree"
version: Final[str] = ".".join(__version__.split(".")[:2])
release: Final[str] = __version__
globals()["copyright"] = f"2014-{datetime.now(tz=UTC).year}, {company}"

extensions: Final[list[str]] = [
    "sphinx_llm.txt",
    "sphinx.ext.autosectionlabel",
    "sphinx.ext.doctest",
    "sphinx.ext.extlinks",
    "sphinx.ext.intersphinx",
    "sphinx_copybutton",
    "sphinx_inline_tabs",
    "sphinxcontrib.mermaid",
    "sphinxcontrib.towncrier.ext",  # render the unreleased news fragments as a draft section
]

intersphinx_mapping: Final[dict[str, tuple[str, None]]] = {
    "python": ("https://docs.python.org/3", None),
}

autosectionlabel_prefix_document: Final[bool] = True
# Release categories repeat across versions and have explicit per-release targets.
autosectionlabel_maxdepth: Final[int] = 1

templates_path: Final[list[str]] = []
unused_docs: Final[list[str]] = []
source_suffix: Final[str] = ".rst"
exclude_patterns: Final[list[str]] = ["_build", "changelog/*"]  # towncrier assembles the fragments; they are not pages

main_doc: Final[str] = "index"
pygments_style = "default"
project: Final[str] = name
today_fmt: Final[str] = "%B %d, %Y"

html_theme: Final[str] = "furo"
html_title, html_last_updated_fmt = project, datetime.now(tz=UTC).isoformat()
pygments_style, pygments_dark_style = "sphinx", "monokai"
html_static_path: Final[list[str]] = ["_static"]
html_css_files: Final[list[str]] = ["custom.css"]
html_favicon: Final[str] = "_static/pipdeptree.svg"
html_theme_options: Final[dict[str, str]] = {
    "light_logo": "pipdeptree.svg",
    "dark_logo": "pipdeptree.svg",
}
html_show_sourcelink: Final[bool] = False

towncrier_draft_autoversion_mode: Final[str] = "draft"
towncrier_draft_include_empty: Final[bool] = True
towncrier_draft_working_directory: Final[Path] = Path(__file__).parent.parent

extlinks: Final[dict[str, tuple[str, str]]] = {
    "issue": ("https://github.com/tox-dev/pipdeptree/issues/%s", "#%s"),
    "pull": ("https://github.com/tox-dev/pipdeptree/pull/%s", "PR #%s"),
    "pr": ("https://github.com/tox-dev/pipdeptree/pull/%s", "PR #%s"),
    "user": ("https://github.com/%s", "@%s"),
    "pypi": ("https://pypi.org/project/%s", "%s"),
}

markdown_http_base: Final[str] = os.environ.get("READTHEDOCS_CANONICAL_URL", "")
