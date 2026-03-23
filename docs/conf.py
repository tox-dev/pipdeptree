"""Sphinx configuration for pipdeptree documentation."""

from __future__ import annotations

from datetime import datetime, timezone

from pipdeptree.version import __version__

company = "tox-dev"
name = "pipdeptree"
version = ".".join(__version__.split(".")[:2])
release = __version__
copyright = f"2014-{datetime.now(tz=timezone.utc).year}, {company}"  # noqa: A001

extensions = [
    "sphinx.ext.autosectionlabel",
    "sphinx.ext.extlinks",
    "sphinx.ext.intersphinx",
    "sphinx_argparse_cli",
    "sphinx_copybutton",
    "sphinx_inline_tabs",
    "sphinxcontrib.mermaid",
]

intersphinx_mapping = {
    "python": ("https://docs.python.org/3", None),
}

autosectionlabel_prefix_document = True

templates_path = []
unused_docs = []
source_suffix = ".rst"
exclude_patterns = ["_build"]

main_doc = "index"
pygments_style = "default"
project = name
today_fmt = "%B %d, %Y"

html_theme = "furo"
html_title, html_last_updated_fmt = project, datetime.now(tz=timezone.utc).isoformat()
pygments_style, pygments_dark_style = "sphinx", "monokai"
html_static_path = ["_static"]
html_css_files = ["custom.css"]
html_favicon = "_static/pipdeptree.svg"
html_theme_options = {
    "light_logo": "pipdeptree.svg",
    "dark_logo": "pipdeptree.svg",
}
html_show_sourcelink = False

extlinks = {
    "issue": ("https://github.com/tox-dev/pipdeptree/issues/%s", "#%s"),
    "pull": ("https://github.com/tox-dev/pipdeptree/pull/%s", "PR #%s"),
    "user": ("https://github.com/%s", "@%s"),
    "pypi": ("https://pypi.org/project/%s", "%s"),
}
