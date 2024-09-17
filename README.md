# pipdeptree

[![PyPI](https://img.shields.io/pypi/v/pipdeptree)](https://pypi.org/project/pipdeptree/)
[![Supported Python
versions](https://img.shields.io/pypi/pyversions/pipdeptree.svg)](https://pypi.org/project/pipdeptree/)
[![Downloads](https://static.pepy.tech/badge/pipdeptree/month)](https://pepy.tech/project/pipdeptree)
[![check](https://github.com/tox-dev/pipdeptree/actions/workflows/check.yaml/badge.svg)](https://github.com/tox-dev/pipdeptree/actions/workflows/check.yaml)
[![pre-commit.ci status](https://results.pre-commit.ci/badge/github/tox-dev/pipdeptree/main.svg)](https://results.pre-commit.ci/latest/github/tox-dev/pipdeptree/main)

`pipdeptree` is a command line utility for displaying the installed python packages in form of a dependency tree. It
works for packages installed globally on a machine as well as in a virtualenv. Since `pip freeze` shows all dependencies
as a flat list, finding out which are the top level packages and which packages do they depend on requires some effort.
It\'s also tedious to resolve conflicting dependencies that could have been installed because older version of `pip`
didn\'t have true dependency resolution[^1]. `pipdeptree` can help here by identifying conflicting dependencies
installed in the environment.

To some extent, `pipdeptree` is inspired by the `lein deps :tree` command of [Leiningen](http://leiningen.org/).

## Installation

```bash
pip install pipdeptree
```

## Running in virtualenvs

`New in ver. 2.0.0`

If you want to run pipdeptree in the context of a particular virtualenv, you can specify the `--python` option. Note
that this capability has been recently added in version `2.0.0`.

Alternatively, you may also install pipdeptree inside the virtualenv and then run it from there.

As of version `2.21.0`, you may also pass `--python auto`, where it will attempt to detect your virtual environment and grab the interpreter from there. It will fail if it is unable to detect one.

## Usage and examples

To give you a brief idea, here is the output of `pipdeptree` compared with `pip freeze`:

```bash
$ pip freeze
Flask==0.10.1
itsdangerous==0.24
Jinja2==2.11.2
-e git+git@github.com:naiquevin/lookupy.git@cdbe30c160e1c29802df75e145ea4ad903c05386#egg=Lookupy
MarkupSafe==0.22
pipdeptree @ file:///private/tmp/pipdeptree-2.0.0b1-py3-none-any.whl
Werkzeug==0.11.2
```

And now see what `pipdeptree` outputs,

```bash
$ pipdeptree
Warning!!! Possibly conflicting dependencies found:
* Jinja2==2.11.2
 - MarkupSafe [required: >=0.23, installed: 0.22]
------------------------------------------------------------------------
Flask==0.10.1
  - itsdangerous [required: >=0.21, installed: 0.24]
  - Jinja2 [required: >=2.4, installed: 2.11.2]
    - MarkupSafe [required: >=0.23, installed: 0.22]
  - Werkzeug [required: >=0.7, installed: 0.11.2]
Lookupy==0.1
pipdeptree==2.0.0b1
  - pip [required: >=6.0.0, installed: 20.1.1]
setuptools==47.1.1
wheel==0.34.2
```

## Is it possible to find out why a particular package is installed?

`New in ver. 0.5.0`

Yes, there\'s a `--reverse` (or simply `-r`) flag for this. To find out which packages depend on a particular
package(s), it can be combined with `--packages` option as follows:

```bash
$ pipdeptree --reverse --packages itsdangerous,MarkupSafe
Warning!!! Possibly conflicting dependencies found:
* Jinja2==2.11.2
 - MarkupSafe [required: >=0.23, installed: 0.22]
------------------------------------------------------------------------
itsdangerous==0.24
  - Flask==0.10.1 [requires: itsdangerous>=0.21]
MarkupSafe==0.22
  - Jinja2==2.11.2 [requires: MarkupSafe>=0.23]
    - Flask==0.10.1 [requires: Jinja2>=2.4]
```

## What\'s with the warning about conflicting dependencies?

As seen in the above output, `pipdeptree` by default warns about possible conflicting dependencies. Any package that\'s
specified as a dependency of multiple packages with different versions is considered as a conflicting dependency.
Conflicting dependencies are possible if older version of pip\<=20.2
([without the new resolver](https://github.com/pypa/pip/issues/988)[^2]) was ever used to install dependencies at some
point. The warning is printed to stderr instead of stdout and it can be completely silenced by specifying the
`-w silence` or `--warn silence` option. On the other hand, it can be made mode strict with `--warn fail`, in which case
the command will not only print the warnings to stderr but also exit with a non-zero status code. This is useful if you
want to fit this tool into your CI pipeline.

**Note**: The `--warn` option is added in version `0.6.0`. If you are using an older version, use `--nowarn` flag to
silence the warnings.

## Warnings about circular dependencies

In case any of the packages have circular dependencies (eg. package A depends on package B and package B depends on
package A), then `pipdeptree` will print warnings about that as well.

```bash
$ pipdeptree --exclude pip,pipdeptree,setuptools,wheel
Warning!!! Cyclic dependencies found:
- CircularDependencyA => CircularDependencyB => CircularDependencyA
- CircularDependencyB => CircularDependencyA => CircularDependencyB
------------------------------------------------------------------------
wsgiref==0.1.2
argparse==1.2.1
```

Similar to the warnings about conflicting dependencies, these too are printed to stderr and can be controlled using the
`--warn` option.

In the above example, you can also see `--exclude` option which is the opposite of `--packages` ie. these packages will
be excluded from the output.

## Using pipdeptree to write requirements.txt file

If you wish to track only top level packages in your `requirements.txt` file, it\'s possible by grep-ing[^3]. only the
top-level lines from the output,

```bash
$ pipdeptree --warn silence | grep -E '^\w+'
Flask==0.10.1
gnureadline==8.0.0
Lookupy==0.1
pipdeptree==2.0.0b1
setuptools==47.1.1
wheel==0.34.2
```

There is a problem here though - The output doesn\'t mention anything about `Lookupy` being installed as an _editable_
package (refer to the output of `pip freeze` above) and information about its source is lost. To fix this, `pipdeptree`
must be run with a `-f` or `--freeze` flag.

```bash
$ pipdeptree -f --warn silence | grep -E '^[a-zA-Z0-9\-]+'
Flask==0.10.1
gnureadline==8.0.0
-e git+git@github.com:naiquevin/lookupy.git@cdbe30c160e1c29802df75e145ea4ad903c05386#egg=Lookupy
pipdeptree @ file:///private/tmp/pipdeptree-2.0.0b1-py3-none-any.whl
setuptools==47.1.1
wheel==0.34.2

$ pipdeptree -f --warn silence | grep -E '^[a-zA-Z0-9\-]+' > requirements.txt
```

The freeze flag will not prefix child dependencies with hyphens, so you could dump the entire output of `pipdeptree -f`
to the requirements.txt file thus making it human-friendly (due to indentations) as well as pip-friendly.

```bash
$ pipdeptree -f | tee locked-requirements.txt
Flask==0.10.1
  itsdangerous==0.24
  Jinja2==2.11.2
    MarkupSafe==0.23
  Werkzeug==0.11.2
gnureadline==8.0.0
-e git+git@github.com:naiquevin/lookupy.git@cdbe30c160e1c29802df75e145ea4ad903c05386#egg=Lookupy
pipdeptree @ file:///private/tmp/pipdeptree-2.0.0b1-py3-none-any.whl
  pip==20.1.1
setuptools==47.1.1
wheel==0.34.2
```

On confirming that there are no conflicting dependencies, you can even treat this as a \"lock file\" where all packages,
including the transient dependencies will be pinned to their currently installed versions. Note that the
`locked-requirements.txt` file could end up with duplicate entries. Although `pip install` wouldn\'t complain about
that, you can avoid duplicate lines (at the cost of losing indentation) as follows,

```bash
$ pipdeptree -f | sed 's/ //g' | sort -u > locked-requirements.txt
```

## Using pipdeptree with external tools

`New in ver. 0.5.0`

It\'s also possible to have `pipdeptree` output json representation of the dependency tree so that it may be used as
input to other external tools.

```bash
$ pipdeptree --json
```

Note that `--json` will output a flat list of all packages with their immediate dependencies. This is not very useful in
itself. To obtain nested json, use `--json-tree`

`New in ver. 0.11.0`

```bash
$ pipdeptree --json-tree
```

## Visualizing the dependency graph

The dependency graph can also be visualized using [GraphViz](http://www.graphviz.org/):

```bash
$ pipdeptree --graph-output dot > dependencies.dot
$ pipdeptree --graph-output pdf > dependencies.pdf
$ pipdeptree --graph-output png > dependencies.png
$ pipdeptree --graph-output svg > dependencies.svg
```

Note that `graphviz` is an optional dependency ie. required only if you want to use `--graph-output`. If the version of
`graphviz` installed in the env is older than 0.18.1, then a warning will be displayed about upgrading `graphviz`.
Support for older versions of graphviz will be dropped soon.

Since version `2.0.0b1`, `--package` and `--reverse` flags are supported for all output formats ie. text, json,
json-tree and graph.

In earlier versions, `--json`, `--json-tree` and `--graph-output` options override `--package` and `--reverse`.

## Usage

```bash
% pipdeptree --help
usage: pipdeptree [-h] [-v] [-w [{silence,suppress,fail}]] [--python PYTHON] [-p P] [-e P] [-a] [-l | -u] [-f] [--encoding E] [-d D] [-r] [--license] [-j | --json-tree | --mermaid | --graph-output FMT]

Dependency tree of the installed python packages

options:
  -h, --help          show this help message and exit
  -v, --version       show program's version number and exit
  -w [{silence,suppress,fail}], --warn [{silence,suppress,fail}]
                      warning control: suppress will show warnings but return 0 whether or not they are present; silence will not show warnings at all and always return 0; fail will show warnings and return 1 if any are present (default:
                      suppress)

select:
  choose what to render

  --python PYTHON     Python interpreter to inspect (default: /usr/local/bin/python)
  -p P, --packages P  comma separated list of packages to show - wildcards are supported, like 'somepackage.*' (default: None)
  -e P, --exclude P   comma separated list of packages to not show - wildcards are supported, like 'somepackage.*'. (cannot combine with -p or -a) (default: None)
  -a, --all           list all deps at top level (default: False)
  -l, --local-only    if in a virtualenv that has global access do not show globally installed packages (default: False)
  -u, --user-only     only show installations in the user site dir (default: False)

render:
  choose how to render the dependency tree (by default will use text mode)

  -f, --freeze        print names so as to write freeze files (default: False)
  --encoding E        the encoding to use when writing to the output (default: utf-8)
  -d D, --depth D     limit the depth of the tree (text render only) (default: inf)
  -r, --reverse       render the dependency tree in the reverse fashion ie. the sub-dependencies are listed with the list of packages that need them under them (default: False)
  --license           list the license(s) of a package (text render only) (default: False)
  -j, --json          raw JSON - this will yield output that may be used by external tools (default: False)
  --json-tree         nested JSON - mimics the text format layout (default: False)
  --mermaid           https://mermaid.js.org flow diagram (default: False)
  --graph-output FMT  Graphviz rendering with the value being the graphviz output e.g.: dot, jpeg, pdf, png, svg (default: None)
```

## Known issues

1.  `pipdeptree` relies on the internal API of `pip`. I fully understand that it\'s a bad idea but it mostly works! On
    rare occasions, it breaks when a new version of `pip` is out with backward incompatible changes in internal API. So
    beware if you are using this tool in environments in which `pip` version is unpinned, specially automation or CD/CI
    pipelines.

## Limitations & Alternatives

`pipdeptree` merely looks at the installed packages in the current environment using pip, constructs the tree, then
outputs it in the specified format. If you want to generate the dependency tree without installing the packages, then
you need a dependency resolver. You might want to check alternatives such as
[pipgrip](https://github.com/ddelange/pipgrip) or [poetry](https://github.com/python-poetry/poetry).

## License

MIT (See [LICENSE](./LICENSE))

## Footnotes

[^1]:
    pip version 20.3 has been released in Nov 2020 with the dependency resolver
    \<<https://blog.python.org/2020/11/pip-20-3-release-new-resolver.html>\>\_

[^2]:
    pip version 20.3 has been released in Nov 2020 with the dependency resolver
    \<<https://blog.python.org/2020/11/pip-20-3-release-new-resolver.html>\>\_

[^3]:
    If you are on windows (powershell) you can run `pipdeptree --warn silence | Select-String -Pattern '^\w+'` instead
    of grep
