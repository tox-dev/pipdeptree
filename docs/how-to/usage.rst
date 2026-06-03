Usage patterns
==============

Running in virtualenvs
----------------------

By default pipdeptree auto-detects your active virtual environment (venv, virtualenv, conda, or poetry) and inspects
it. When no virtual environment is active, it falls back to the interpreter running pipdeptree, so a globally
installed pipdeptree keeps inspecting the global packages:

.. code-block:: console

    $ pipdeptree

To inspect a specific interpreter regardless of what is active, pass its path to ``--python``:

.. code-block:: console

    $ pipdeptree --python /path/to/venv/bin/python
    covdefaults==2.3.0
    └── coverage [required: >=6.0.2, installed: 7.13.5]
    ...

Use ``--python auto`` to force auto-detection of the active virtualenv and fail if none can be found (unlike the
default, which silently falls back to the running interpreter):

.. code-block:: console

    $ pipdeptree --python auto
    covdefaults==2.3.0
    └── coverage [required: >=6.0.2, installed: 7.13.5]
    ...

Alternatively, install pipdeptree inside the virtualenv and run it directly.

from-index (resolve by querying the index)
-------------------------------------------

pipdeptree inspects an installed environment by default. The ``from-index`` subcommand resolves a set of
requirements by querying the package index (PyPI) and shows the resulting tree **without installing or inspecting
anything**. It uses the optional index resolver, so install the extra first:

.. code-block:: console

    $ pip install pipdeptree[index]

You name each source; pipdeptree never guesses one from a path's shape. Positional arguments are inline PEP 508
requirements, the same strings you pass to ``pip install``. You supply files with repeatable flags:

- positional ``REQUIREMENT`` -- an inline PEP 508 requirement string, version specifiers and extras included;
- ``--requirements FILE`` -- a standard ``requirements.txt`` or ``.in`` style file;
- ``--pyproject FILE`` -- a ``pyproject.toml`` handed to the resolver, which reads ``[project].dependencies`` and
  honors its ``[tool.nab]`` configuration.

Pass at least one source. Each edge shows the candidate version the resolver selected, never a package on your
machine: the resolver produces a single version per package with no requirement range, so edges read
``[candidate: <version>]`` instead of the ``[required: ..., installed: ...]`` pair shown for an installed
environment.

Resolve inline requirements
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

A single requirement resolves to its full tree:

.. code-block:: console

    $ pipdeptree from-index "starlette"
    starlette==1.2.1
    ├── anyio [candidate: 4.13.0]
    │   ├── idna [candidate: 3.18]
    │   └── typing-extensions [candidate: 4.15.0]
    └── typing-extensions [candidate: 4.15.0]

Several requirements resolve together into one graph, and a version specifier bounds the pick:

.. code-block:: console

    $ pipdeptree from-index "fastapi<=0.115.2" starlette
    fastapi==0.115.2
    ├── pydantic [candidate: 2.13.4]
    │   ├── annotated-types [candidate: 0.7.0]
    │   ├── pydantic-core [candidate: 2.46.4]
    │   │   └── typing-extensions [candidate: 4.15.0]
    │   ├── typing-extensions [candidate: 4.15.0]
    │   └── typing-inspection [candidate: 0.4.2]
    │       └── typing-extensions [candidate: 4.15.0]
    ├── starlette [candidate: 0.40.0]
    │   └── anyio [candidate: 4.13.0]
    │       ├── idna [candidate: 3.18]
    │       └── typing-extensions [candidate: 4.15.0]
    └── typing-extensions [candidate: 4.15.0]

Request extras with the ``name[extra]`` syntax. The resolver pulls the extra's dependencies into the tree, where
they appear as ordinary children (here ``pysocks``) with the pinned version the resolve picked, not as edges
labeled with the extra:

.. code-block:: console

    $ pipdeptree from-index "requests[socks]"
    requests==2.34.2
    ├── certifi [candidate: 2026.5.20]
    ├── charset-normalizer [candidate: 3.4.7]
    ├── idna [candidate: 3.18]
    ├── pysocks [candidate: 1.7.1]
    └── urllib3 [candidate: 2.7.0]

An environment marker gates a requirement on the interpreter the resolve targets: when the marker is true the
requirement resolves and shows in the tree, when false it drops out. Quote the whole argument so the shell keeps
the marker attached:

.. code-block:: console

    $ pipdeptree from-index 'idna; python_version >= "3.10"'
    idna==3.18

Resolve from a requirements file
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Point ``--requirements`` at a ``requirements.txt``:

.. code-block:: console

    $ pipdeptree from-index --requirements requirements.txt

pipdeptree parses the file as a standard requirements file, so a real-world one resolves as-is. Take this
``requirements.txt``:

.. code-block:: text

    -r base.txt                        # nested include, followed
    -c constraints.txt                 # constraints, fed to the resolver
    httpx[http2]                       # extras kept
    tomli; python_version < "3.11"     # environment marker kept
    # pin chosen by the security team   <- comment, ignored
    requests==2.32.3 \
        --hash=sha256:0000000000000000000000000000000000000000000000000000000000000000

Each directive maps as follows: the ``-r base.txt`` include is read inline, the ``-c constraints.txt`` pins bound
the resolve, the marker and the ``[http2]`` extra reach the resolver intact, the comment drops out, and the
``--hash`` line resolves ``requests`` while the hash itself is ignored (the resolver verifies nothing from the
index). The same goes for ``--index-url`` and similar pip-only options.

Resolve from a pyproject.toml
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Give ``--pyproject`` as the only source and the resolver reads it natively: the full ``[project]`` table and any
``[tool.nab]`` configuration in the file:

.. code-block:: console

    $ pipdeptree from-index --pyproject pyproject.toml

Add any other source and the ``[project].dependencies`` from that pyproject merge into one combined resolve
instead. Its ``[tool.nab]`` settings drop out on this path:

.. code-block:: console

    $ pipdeptree from-index --pyproject pyproject.toml httpx

Combine and repeat sources
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Both flags repeat, and every source folds into a single resolve alongside the positional requirements:

.. code-block:: console

    $ pipdeptree from-index --requirements a.txt --requirements b.txt --pyproject p.toml extra-pkg

Use a private or custom index
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

By default the resolve runs against PyPI. Point it at an internal index with ``--index-url`` and add more with
``--extra-index-url`` (repeatable):

.. code-block:: console

    $ pipdeptree from-index "internal-lib" --index-url https://nexus.corp/repository/pypi/simple
    $ pipdeptree from-index "internal-lib" --extra-index-url https://nexus.corp/repository/pypi/simple

``--index-url`` replaces PyPI as the primary index, matching pip's ``--index-url``. ``--extra-index-url`` keeps
PyPI as the primary and appends each extra after it. When a flag is absent, the value falls back to the environment:
``--index-url`` reads ``PIP_INDEX_URL`` then ``UV_INDEX_URL``, and ``--extra-index-url`` reads
``PIP_EXTRA_INDEX_URL`` then ``UV_EXTRA_INDEX_URL`` (both whitespace separated, like pip and uv). With nothing set
the resolve uses PyPI.

The resolver searches indexes in order and the first index that has a package wins. This differs from pip, which
merges every index and picks the highest version across all of them. Order your indexes so the one you trust for a
given package comes first.

The index flags and their environment fallbacks override a ``--pyproject``'s own ``[tool.nab].indexes``. With no
flag and no environment override, the resolve uses the indexes declared in the pyproject.

.. code-block:: console

    $ PIP_INDEX_URL=https://nexus.corp/repository/pypi/simple pipdeptree from-index "internal-lib"
    $ pipdeptree from-index --pyproject pyproject.toml --index-url https://nexus.corp/repository/pypi/simple

Apply render flags
~~~~~~~~~~~~~~~~~~~

The graph and render flags behave as they do for the default command. Emit JSON for tooling:

.. code-block:: console

    $ pipdeptree from-index "starlette" -o json
    [
        {
            "package": {
                "key": "anyio",
                "package_name": "anyio",
                "candidate_version": "4.13.0"
            },
            "dependencies": [
                {
                    "key": "idna",
                    "package_name": "idna",
                    "candidate_version": "3.18"
                },
                {
                    "key": "typing-extensions",
                    "package_name": "typing-extensions",
                    "candidate_version": "4.15.0"
                }
            ]
        },
        {
            "package": {
                "key": "idna",
                "package_name": "idna",
                "candidate_version": "3.18"
            },
            "dependencies": []
        },
        {
            "package": {
                "key": "starlette",
                "package_name": "starlette",
                "candidate_version": "1.2.1"
            },
            "dependencies": [
                {
                    "key": "anyio",
                    "package_name": "anyio",
                    "candidate_version": "4.13.0"
                },
                {
                    "key": "typing-extensions",
                    "package_name": "typing-extensions",
                    "candidate_version": "4.15.0"
                }
            ]
        },
        {
            "package": {
                "key": "typing-extensions",
                "package_name": "typing-extensions",
                "candidate_version": "4.15.0"
            },
            "dependencies": []
        }
    ]

Trace why the resolver pulled a package in with ``--reverse`` (``-r``):

.. code-block:: console

    $ pipdeptree from-index "fastapi<=0.115.2" --reverse --packages anyio
    anyio==4.13.0
    └── starlette==0.40.0 [requires: anyio==4.13.0]
        └── fastapi==0.115.2 [requires: starlette==0.40.0]

The rest carry over too: ``-o mermaid`` and the ``graphviz-*`` formats, ``--depth`` (``-d``) to cap the tree,
``--packages`` (``-p``) and ``--exclude`` (``-e``) to filter, ``--extras`` (``-x``) to control optional edges, and
``--encoding``:

.. code-block:: console

    $ pipdeptree from-index "fastapi<=0.115.2" --depth 1
    $ pipdeptree from-index "fastapi<=0.115.2" -o mermaid
    $ pipdeptree from-index "fastapi<=0.115.2" --packages starlette
    $ pipdeptree from-index "fastapi<=0.115.2" --exclude anyio
    $ pipdeptree from-index "requests[socks]" --extras none

Resolve editable, local and git requirements
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

For a requirement that points at a checkout instead of the index, the resolver reads the target's PEP 621
metadata. It reads the project's ``[project]`` table (name, version, dependencies) statically, with no build, and
falls back to a build backend only when the target declares its dependencies dynamically. A project with a static
``[project]`` resolves with no build; a dynamic-metadata project triggers its backend.

Editable installs are a ``--requirements`` file directive, so pass them through a file:

.. code-block:: console

    $ printf -- '-e ./mypkg\n' > requirements.txt
    $ pipdeptree from-index --requirements requirements.txt

Local paths (``./mypkg``, ``file:///abs/path``) work the same, as positional arguments or file lines. For a pinned
git requirement, the resolver clones the repo to its cache and reads the metadata:

.. code-block:: console

    $ pipdeptree from-index "mypkg @ git+https://github.com/o/r.git@<full-40-char-commit-sha>"

The git ref must be a full 40-character commit sha; pipdeptree refuses a tag or branch so the resolve stays
reproducible. Bare wheel/sdist archive URLs and non-git VCS schemes (``hg+``/``bzr+``/``svn+``) stay out of scope.

Handle errors
~~~~~~~~~~~~~

A ``--requirements`` or ``--pyproject`` file must exist; a missing one stops the command. Positional arguments are
requirement strings, never file paths:

.. code-block:: console

    $ pipdeptree from-index --requirements missing.txt
    source file does not exist: missing.txt

A bare wheel/sdist archive URL or a non-git VCS scheme (``hg+``/``bzr+``/``svn+``) has no index mapping, so
pipdeptree names the file and line that carried it:

.. code-block:: console

    $ pipdeptree from-index --requirements requirements.txt
    URL requirements are not supported by the index resolver: foo @ https://h/foo-1.0-py3-none-any.whl (requirements.txt:3)

An unpinned git ref fails the same way, and so does a constraint that carries extras or a URL.

The installed-only display options inspect on-disk files, so ``from-index`` does not accept them. Passing one is an
error:

.. code-block:: console

    $ pipdeptree from-index "starlette" --metadata license
    ...
    pipdeptree: error: unrecognized arguments: --metadata license

The same holds for ``--computed`` (``-c``), ``--license``, and the environment-inspection options (``--python``,
``--path``, ``-l``/``-u``): none have a downloaded package or an environment to read. Giving no source at all is
also an error:

.. code-block:: console

    $ pipdeptree from-index
    ...
    pipdeptree: error: from-index needs at least one REQUIREMENT, --requirements FILE, or --pyproject FILE

Limitations
~~~~~~~~~~~

- A ``--requirements`` or ``--pyproject`` file must exist, or the command errors (shown above). Positional
  arguments are always requirement strings, never file paths.
- Extras resolve everywhere a requirement can appear: a positional ``requests[socks]``, a ``requests[socks]`` line
  in a ``--requirements`` file (including nested ``-r`` includes), and ``[project.optional-dependencies]`` reached
  through a ``--pyproject``. The one exception is a ``-c`` constraint line: pip and the resolver both reject an
  extra on a constraint (``foo[bar]<2``), because a constraint bounds a version without pulling the package in, so
  the extra has nothing to attach to.
- The resolver reads PEP 621 metadata for editable installs (``-e``), local paths (``./pkg``, ``file://``) and
  pinned git requirements (``package @ git+https://...@<sha>``), as the resolve subsection covers above. Bare
  wheel/sdist archive URLs and non-git VCS (``hg+``/``bzr+``/``svn+``) stay out of scope and error with the
  offending file and line; a constraint that carries a URL fails the same way.
- ``from-index`` rejects the installed-only display options (``--metadata``/``-m``, ``--computed``/``-c``,
  ``--license``) and the environment-inspection options (``--python``, ``--path``, ``-l``/``-u``), since the
  resolver produces only names, versions and dependency edges. Extras (``-x``) work, since they are part of the
  resolved graph.
- A ``--pyproject`` keeps its ``[tool.nab]`` configuration only when it is the lone source; mixing it with other
  sources merges its ``[project].dependencies`` and drops its ``[tool.nab]``.
- The subcommand needs network access and the ``pipdeptree[index]`` extra. Without the extra installed, it errors
  with an install hint.

from-lock (render a PEP 751 lock)
---------------------------------

The ``from-lock`` subcommand reads a `PEP 751 <https://peps.python.org/pep-0751/>`_ lock file
(``pylock.toml``) and renders its dependency tree. A lock is already resolved: it records the pinned packages,
their versions and the edges between them. ``from-lock`` runs **offline** with no package index, no network and no
extra, and it works on every supported Python. The standard-library ``tomllib`` parses the file on 3.11+, and
:pypi:`tomli` parses it on 3.10.

.. code-block:: console

    $ pipdeptree from-lock pylock.toml
    build==1.5.0
    ├── packaging [candidate: 26.2]
    └── pyproject-hooks [candidate: 1.2.0]

Each edge shows the ``candidate:`` version the lock pinned, not a package on your machine. pipdeptree reads
nothing off disk and installs nothing.

Producing a pylock.toml
~~~~~~~~~~~~~~~~~~~~~~~~

Any PEP 751 emitter writes a file ``from-lock`` can read. :pypi:`uv` exports one from a project:

.. code-block:: console

    $ uv export -o pylock.toml          # or: uv lock then export
    $ pipdeptree from-lock pylock.toml

Render flags on a lock
~~~~~~~~~~~~~~~~~~~~~~~~

The lock supplies every name, version and edge, so the graph and render flags behave as they do for the default
command: ``--packages`` (``-p``), ``--exclude`` (``-e``), ``--depth`` (``-d``), ``--extras`` (``-x``),
``--reverse`` (``-r``), ``--encoding`` and every output format from ``-o``.

Emit JSON for another tool to consume:

.. code-block:: console

    $ pipdeptree from-lock pylock.toml -o json
    [
        {
            "package": {
                "key": "build",
                "package_name": "build",
                "candidate_version": "1.5.0"
            },
            "dependencies": [
                {
                    "key": "packaging",
                    "package_name": "packaging",
                    "candidate_version": "26.2"
                },
                {
                    "key": "pyproject-hooks",
                    "package_name": "pyproject-hooks",
                    "candidate_version": "1.2.0"
                }
            ]
        },
        {
            "package": {
                "key": "packaging",
                "package_name": "packaging",
                "candidate_version": "26.2"
            },
            "dependencies": []
        },
        {
            "package": {
                "key": "pyproject-hooks",
                "package_name": "pyproject-hooks",
                "candidate_version": "1.2.0"
            },
            "dependencies": []
        }
    ]

Flip the edges with ``--reverse`` to see which packages pull in a given dependency:

.. code-block:: console

    $ pipdeptree from-lock pylock.toml --reverse
    packaging==26.2
    └── build==1.5.0 [requires: packaging==26.2]
    pyproject-hooks==1.2.0
    └── build==1.5.0 [requires: pyproject-hooks==1.2.0]

Draw a Mermaid diagram for a docs page or chat client:

.. code-block:: console

    $ pipdeptree from-lock pylock.toml -o mermaid

Narrow the tree the same way you would for an installed environment. Keep one root with ``--packages``:

.. code-block:: console

    $ pipdeptree from-lock pylock.toml --packages build

Hide a package with ``--exclude``:

.. code-block:: console

    $ pipdeptree from-lock pylock.toml --exclude packaging

Stop after the first level with ``--depth``:

.. code-block:: console

    $ pipdeptree from-lock pylock.toml --depth 1

Locks without edges
~~~~~~~~~~~~~~~~~~~~~

A valid PEP 751 lock may pin packages without recording the edges between them. ``from-lock`` then renders a flat
list of pinned packages, each with no children:

.. code-block:: console

    $ pipdeptree from-lock pylock.toml
    build==1.5.0
    packaging==26.2
    pyproject-hooks==1.2.0

Lock limitations
~~~~~~~~~~~~~~~~~

A lock carries only names, versions and edges, so the installed-only display options have nothing to read. The
subcommand omits them, and passing one errors:

.. code-block:: console

    $ pipdeptree from-lock pylock.toml --metadata license
    ...
    pipdeptree: error: unrecognized arguments: --metadata license
    $ pipdeptree from-lock pylock.toml --license

The same holds for ``--computed`` (``-c``) and the environment-inspection options (``--python``, ``--path``,
``-l``/``-u``): a lock has no ``METADATA`` file, no on-disk sizes and no environment to point at.

A missing lock file stops the command with a message and exit code 1:

.. code-block:: console

    $ pipdeptree from-lock missing.toml
    lock file does not exist: missing.toml
    $ echo $?
    1

A malformed lock fails the same way. ``from-lock`` rejects a file that parses as TOML but has no ``packages``
array:

.. code-block:: console

    $ pipdeptree from-lock pylock.toml
    not a valid PEP 751 lock file: pylock.toml (missing 'packages' array)

A package entry without a ``name`` key, or a file that is not TOML at all, reports the offending file too:

.. code-block:: console

    $ pipdeptree from-lock pylock.toml
    not a valid PEP 751 lock file: pylock.toml (a package entry is missing 'name')

Filtering packages
------------------

By default, pipdeptree shows the full dependency tree of your environment:

.. code-block:: console

    $ pipdeptree
    covdefaults==2.3.0
    └── coverage [required: >=6.0.2, installed: 7.13.5]
    diff_cover==10.2.0
    ├── Jinja2 [required: >=2.7.1, installed: 3.1.6]
    │   └── MarkupSafe [required: >=2.0, installed: 3.0.3]
    ├── Pygments [required: >=2.19.1,<3.0.0, installed: 2.19.2]
    ├── chardet [required: >=3.0.0, installed: 7.1.0]
    └── pluggy [required: >=0.13.1,<2, installed: 1.6.0]
    graphviz==0.21
    pipdeptree==2.33.0
    └── packaging [required: >=26, installed: 26.0]
    pytest-cov==7.0.0
    ├── coverage [required: >=7.10.6, installed: 7.13.5]
    ├── pluggy [required: >=1.2, installed: 1.6.0]
    └── pytest [required: >=7, installed: 9.0.2]
        ├── iniconfig [required: >=1.0.1, installed: 2.3.0]
        ├── packaging [required: >=22, installed: 26.0]
        ├── pluggy [required: >=1.5,<2, installed: 1.6.0]
        └── Pygments [required: >=2.7.2, installed: 2.19.2]
    ...

Show only specific packages with ``--packages`` (``-p``):

.. code-block:: console

    $ pipdeptree --packages pytest
    pytest==9.0.2
    ├── iniconfig [required: >=1.0.1, installed: 2.3.0]
    ├── packaging [required: >=22, installed: 26.0]
    ├── pluggy [required: >=1.5,<2, installed: 1.6.0]
    └── Pygments [required: >=2.7.2, installed: 2.19.2]

Multiple packages can be comma-separated, and wildcards are supported:

.. code-block:: console

    $ pipdeptree --packages "pytest*"
    pytest-cov==7.0.0
    ├── coverage [required: >=7.10.6, installed: 7.13.5]
    ├── pluggy [required: >=1.2, installed: 1.6.0]
    └── pytest [required: >=7, installed: 9.0.2]
        ├── iniconfig [required: >=1.0.1, installed: 2.3.0]
        ├── packaging [required: >=22, installed: 26.0]
        ├── pluggy [required: >=1.5,<2, installed: 1.6.0]
        └── Pygments [required: >=2.7.2, installed: 2.19.2]
    pytest-mock==3.15.1
    └── pytest [required: >=6.2.5, installed: 9.0.2]
        ├── iniconfig [required: >=1.0.1, installed: 2.3.0]
        ├── packaging [required: >=22, installed: 26.0]
        ├── pluggy [required: >=1.5,<2, installed: 1.6.0]
        └── Pygments [required: >=2.7.2, installed: 2.19.2]
    pytest-subprocess==1.5.3
    └── pytest [required: >=4.0.0, installed: 9.0.2]
        ├── iniconfig [required: >=1.0.1, installed: 2.3.0]
        ├── packaging [required: >=22, installed: 26.0]
        ├── pluggy [required: >=1.5,<2, installed: 1.6.0]
        └── Pygments [required: >=2.7.2, installed: 2.19.2]

A package entry may carry an extras spec such as ``somepackage[extra1,extra2]`` to also include the dependencies
gated behind those extras (and their subtrees). The extras spec is parsed off before the name is matched, so
wildcards keep working, for example ``somepackage*[extra1]``. An extra requested this way is always surfaced, even
with ``--extras none``:

.. code-block:: console

    $ pipdeptree --packages "requests[socks]"
    requests==2.32.3
    ├── certifi [required: >=2017.4.17, installed: 2024.8.30]
    ├── charset-normalizer [required: >=2,<4, installed: 3.4.0]
    ├── idna [required: >=2.5,<4, installed: 3.10]
    ├── urllib3 [required: >=1.21.1,<3, installed: 2.2.3]
    └── PySocks [required: >=1.5.6,!=1.5.7, installed: 1.7.1, extra: socks]

Excluding packages
------------------

Use ``--exclude`` (``-e``) to hide specific packages:

.. code-block:: console

    $ pipdeptree --exclude pip,pipdeptree,setuptools,wheel
    covdefaults==2.3.0
    └── coverage [required: >=6.0.2, installed: 7.13.5]
    diff_cover==10.2.0
    ├── Jinja2 [required: >=2.7.1, installed: 3.1.6]
    │   └── MarkupSafe [required: >=2.0, installed: 3.0.3]
    ├── Pygments [required: >=2.19.1,<3.0.0, installed: 2.19.2]
    ├── chardet [required: >=3.0.0, installed: 7.1.0]
    └── pluggy [required: >=0.13.1,<2, installed: 1.6.0]
    graphviz==0.21
    pytest-cov==7.0.0
    ├── coverage [required: >=7.10.6, installed: 7.13.5]
    ├── pluggy [required: >=1.2, installed: 1.6.0]
    └── pytest [required: >=7, installed: 9.0.2]
        ├── iniconfig [required: >=1.0.1, installed: 2.3.0]
        ├── packaging [required: >=22, installed: 26.0]
        ├── pluggy [required: >=1.5,<2, installed: 1.6.0]
        └── Pygments [required: >=2.7.2, installed: 2.19.2]
    ...

Add ``--exclude-dependencies`` to also hide their transitive dependencies:

.. code-block:: console

    $ pipdeptree --exclude pipdeptree --exclude-dependencies
    covdefaults==2.3.0
    └── coverage [required: >=6.0.2, installed: 7.13.5]
    diff_cover==10.2.0
    ├── Jinja2 [required: >=2.7.1, installed: 3.1.6]
    │   └── MarkupSafe [required: >=2.0, installed: 3.0.3]
    ├── Pygments [required: >=2.19.1,<3.0.0, installed: 2.19.2]
    ├── chardet [required: >=3.0.0, installed: 7.1.0]
    └── pluggy [required: >=0.13.1,<2, installed: 1.6.0]
    graphviz==0.21
    pytest-cov==7.0.0
    ├── coverage [required: >=7.10.6, installed: 7.13.5]
    ├── pluggy [required: >=1.2, installed: 1.6.0]
    └── pytest [required: >=7, installed: 9.0.2]
        ├── iniconfig [required: >=1.0.1, installed: 2.3.0]
        ├── pluggy [required: >=1.5,<2, installed: 1.6.0]
        └── Pygments [required: >=2.7.2, installed: 2.19.2]
    ...

Note that ``packaging`` no longer appears under ``pytest`` because it was excluded as a transitive dependency of
``pipdeptree``.

Reverse dependency lookup
-------------------------

Use ``--reverse`` (``-r``) with ``--packages`` to find out why a package is installed:

.. code-block:: console

    $ pipdeptree --reverse --packages pygments
    Pygments==2.19.2
    ├── rich==14.3.3 [requires: Pygments>=2.13.0,<3.0.0]
    ├── diff_cover==10.2.0 [requires: Pygments>=2.19.1,<3.0.0]
    └── pytest==9.0.2 [requires: Pygments>=2.7.2]
        ├── pytest-mock==3.15.1 [requires: pytest>=6.2.5]
        ├── pytest-subprocess==1.5.3 [requires: pytest>=4.0.0]
        └── pytest-cov==7.0.0 [requires: pytest>=7]

Writing requirements files
--------------------------

Extract top-level packages from the tree output:

.. code-block:: console

    $ pipdeptree --warn silence | grep -E '^\w+'
    covdefaults==2.3.0
    diff_cover==10.2.0
    graphviz==0.21
    pipdeptree==2.33.0
    pytest-cov==7.0.0
    pytest-mock==3.15.1
    pytest-subprocess==1.5.3
    rich==14.3.3
    virtualenv==20.39.1

Or use freeze format for pip-compatible output:

.. code-block:: console

    $ pipdeptree -o freeze --warn silence | grep -E '^[a-zA-Z0-9\-]+' > requirements.txt

The freeze output can also serve as a human-readable lock file with indented dependencies:

.. code-block:: console

    $ pipdeptree --packages pytest -o freeze
    pytest==9.0.2
      iniconfig==2.3.0
      packaging==26.0
      pluggy==1.6.0
      Pygments==2.19.2

Warning control
---------------

pipdeptree warns about conflicting and circular dependencies on stderr. Control this with ``-w``:

- ``-w suppress`` (default) -- show warnings, exit 0.
- ``-w silence`` -- hide warnings, exit 0.
- ``-w fail`` -- show warnings, exit 1 if any found (useful in CI).

.. code-block:: console

    $ pipdeptree -w fail
    $ echo $?
    0

When conflicts exist, the output includes warnings and a non-zero exit code:

.. code-block:: console

    $ pipdeptree -w fail
    Warning!!! Possibly conflicting dependencies found:
    * Jinja2==2.11.2
     - MarkupSafe [required: >=0.23, installed: 0.22]
    $ echo $?
    1

Use from Python or a notebook
-----------------------------

When you do not have command-line access -- for example inside a Jupyter or JupyterLite cell -- call
:func:`pipdeptree.render` to obtain the dependency tree as a string instead of going through ``argv`` and stdout:

.. code-block:: python

    import pipdeptree

    print(pipdeptree.render())                       # text tree of the current env
    data = pipdeptree.render(output_format="json")   # JSON string, e.g. for json.loads
    sub = pipdeptree.render(packages="rich", reverse=True)

``output_format`` accepts ``text`` (default), ``json``, ``json-tree``, ``mermaid`` and ``dot`` (Graphviz source).
Binary Graphviz formats such as ``png`` or ``svg`` cannot be returned as text and raise ``ValueError``; use ``dot`` to
get the source, or the command-line interface for binary rendering.

The return value is always a ``str``, so ``print``, slicing and comparisons behave as usual. For the default ``text``
format it is also rich-displayable: in a Jupyter or JupyterLite cell the result renders as a Mermaid dependency
diagram (natively, with no extra dependency and no Graphviz binary -- which also works in Pyodide/JupyterLite), falling
back to an HTML ``<pre>`` and then plain text on front-ends that do not render Mermaid. ``str(render())`` and
``print(render())`` always give the plain text tree. The other formats (``json``, ``json-tree``, ``mermaid``, ``dot``)
return a plain string with no rich display, so their JSON or source shows verbatim.

Unlike the CLI, warnings are silenced by default (``warn="silence"``) so a notebook cell stays free of stderr noise;
pass ``warn="suppress"`` or ``warn="fail"`` to opt back in.

Depth limiting
--------------

Limit how deep the tree renders with ``-d``:

.. code-block:: console

    $ pipdeptree -d 1 --packages pytest-cov,rich
    pytest-cov==7.0.0
    ├── coverage [required: >=7.10.6, installed: 7.13.5]
    ├── pluggy [required: >=1.2, installed: 1.6.0]
    └── pytest [required: >=7, installed: 9.0.2]
    rich==14.3.3
    ├── markdown-it-py [required: >=2.2.0, installed: 4.0.0]
    └── Pygments [required: >=2.13.0,<3.0.0, installed: 2.19.2]

Use ``-d 0`` to show only top-level packages with no dependencies:

.. code-block:: console

    $ pipdeptree -d 0 --packages pytest-cov,rich
    pytest-cov==7.0.0
    rich==14.3.3

Package metadata
----------------

Display metadata fields from the package's ``METADATA`` file with ``--metadata`` (``-m``). Pass a comma-separated list
of field names. Metadata is shown on every package in the tree in parentheses:

.. code-block:: console

    $ pipdeptree --metadata license --packages rich
    rich==14.3.3 (MIT License)
    ├── markdown-it-py [required: >=2.2.0, installed: 4.0.0] (MIT License)
    │   └── mdurl [required: ~=0.1, installed: 0.1.2] (MIT License)
    └── Pygments [required: >=2.13.0,<3.0.0, installed: 2.19.2] (BSD License)

Multiple fields can be combined:

.. code-block:: console

    $ pipdeptree --metadata license,summary --packages rich -d 0
    rich==14.3.3 (MIT License, Render rich text, tables, progress bars, syntax highlighting, markdown and more to the terminal)

Common metadata fields: ``license``, ``summary``, ``author``, ``author-email``, ``home-page``, ``requires-python``.
Any field from the package's ``METADATA`` file is accepted.

.. note::

   The ``--license`` flag still works for backwards compatibility but is deprecated. Use ``--metadata license``
   instead.

Computed fields
---------------

Display computed package information with ``--computed`` (``-c``):

- ``size`` -- installed size on disk (human-readable)
- ``size-raw`` -- installed size in bytes (integer, useful for JSON output)
- ``unique-deps-count`` -- number of dependencies exclusive to this package (hidden when 0)
- ``unique-deps-names`` -- names of dependencies exclusive to this package (hidden when empty)
- ``unique-deps-size`` -- total installed size of exclusive dependencies (hidden when 0)

Unique dependencies are transitive: if removing a package would orphan a dependency, and that orphaned dependency
would in turn orphan its own dependencies, all of them are counted. In rich output, unique dependencies are marked
with a ⭐ icon (alongside ✗ or ⚠ if applicable).

.. code-block:: console

    $ pipdeptree --computed size --packages rich -d 0
    rich==14.3.3 (1.2 MB)

.. code-block:: console

    $ pipdeptree --computed unique-deps-count,unique-deps-names,unique-deps-size --packages rich
    rich==14.3.3 (2 unique deps, unique: markdown-it-py | mdurl, unique size: 248.2 KB)
    ├── markdown-it-py [required: >=2.2.0, installed: 4.0.0] (1 unique deps, unique: mdurl, unique size: 22.9 KB)
    │   └── mdurl [required: ~=0.1, installed: 0.1.2]
    └── Pygments [required: >=2.13.0,<3.0.0, installed: 2.19.2]

Both ``--metadata`` and ``--computed`` can be combined and work with all output formats. In JSON output, ``size_raw``
and ``unique_deps_count`` are native integers, ``unique_deps_names`` is a list of strings.

Including extras
----------------

Show optional (extras) dependencies in the tree with ``--extras`` (``-x``):

.. code-block:: console

    $ pipdeptree --extras --packages pytest
    pytest==9.0.2
    ├── iniconfig [required: >=1.0.1, installed: 2.3.0]
    ├── packaging [required: >=22, installed: 26.0]
    ├── pluggy [required: >=1.5,<2, installed: 1.6.0]
    └── Pygments [required: >=2.7.2, installed: 2.19.2]

Without ``--extras``, only mandatory dependencies are shown. Packages that declare optional dependency groups (extras)
will have those additional dependencies included when this flag is set.

Edges added through an extra are annotated with that extra's name:

.. code-block:: console

    $ pipdeptree --extras --packages oauthlib
    oauthlib==3.0.0
    ├── cryptography [required: Any, installed: 2.7, extra: signedtoken]
    └── pyjwt [required: >=1.0.0, installed: 1.7.1, extra: signedtoken]

An extra is included not only when a parent explicitly requested it (e.g. ``oauthlib[signedtoken]``)
but also when every dependency that the extra would require is already installed in the
environment. See :doc:`/explanation` for the rationale.

To surface a single package's extra without enabling extras globally, request it through ``--packages`` using
the ``somepackage[extra]`` syntax shown in the "Filtering packages" section above; that extra is shown even with
``--extras none``.
