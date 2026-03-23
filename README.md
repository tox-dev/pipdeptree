# pipdeptree

[![PyPI](https://img.shields.io/pypi/v/pipdeptree?style=flat-square)](https://pypi.org/project/pipdeptree)
[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/pipdeptree?style=flat-square)](https://pypi.org/project/pipdeptree)
[![Downloads](https://static.pepy.tech/badge/pipdeptree/month)](https://pepy.tech/project/pipdeptree)
[![Documentation](https://readthedocs.org/projects/pipdeptree/badge/?version=latest&style=flat-square)](https://pipdeptree.readthedocs.io)
[![PyPI - License](https://img.shields.io/pypi/l/pipdeptree?style=flat-square)](https://opensource.org/licenses/MIT)
[![check](https://github.com/tox-dev/pipdeptree/actions/workflows/check.yaml/badge.svg)](https://github.com/tox-dev/pipdeptree/actions/workflows/check.yaml)

A command-line utility for displaying installed Python packages as a dependency tree. While `pip freeze` shows a flat
list, `pipdeptree` reveals which packages are top-level and what they depend on, including conflicting or circular
dependencies.

## Quick start

```bash
pip install pipdeptree
pipdeptree
```

```text
Flask==0.10.1
  - itsdangerous [required: >=0.21, installed: 0.24]
  - Jinja2 [required: >=2.4, installed: 2.11.2]
    - MarkupSafe [required: >=0.23, installed: 0.22]
  - Werkzeug [required: >=0.7, installed: 0.11.2]
```

Find out why a package is installed:

```bash
pipdeptree --reverse --packages markupsafe
```

Output as JSON, Mermaid, or Graphviz:

```bash
pipdeptree -o json
pipdeptree -o mermaid
pipdeptree -o graphviz-svg > deps.svg
```

For the full documentation, visit [pipdeptree.readthedocs.io](https://pipdeptree.readthedocs.io).

- [Documentation](https://pipdeptree.readthedocs.io)
- [Installation](https://pipdeptree.readthedocs.io/en/latest/tutorial/getting-started.html)
- [Usage](https://pipdeptree.readthedocs.io/en/latest/how-to/usage.html)
- [Changelog](https://github.com/tox-dev/pipdeptree/releases)
- [Issues](https://github.com/tox-dev/pipdeptree/issues)
- [PyPI](https://pypi.org/project/pipdeptree)
- [GitHub](https://github.com/tox-dev/pipdeptree)
