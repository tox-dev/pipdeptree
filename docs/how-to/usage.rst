Usage patterns
==============

Running in virtualenvs
----------------------

By default pipdeptree auto-detects your active virtual environment (venv, virtualenv, conda, or poetry) and inspects
it. When no virtual environment is active, it falls back to the interpreter running pipdeptree. A system installation
therefore inspects the system packages:

.. code-block:: console

    $ pipdeptree

To inspect a specific interpreter regardless of what is active, pass its path to ``--python``:

.. code-block:: console

    $ pipdeptree --python /path/to/venv/bin/python

Use ``--python auto`` to require an active virtual environment. The command fails when it cannot find one:

.. code-block:: console

    $ pipdeptree --python auto

Installing pipdeptree inside the virtual environment and running it there gives the same result.

from-index (resolve by querying the index)
-------------------------------------------

pipdeptree inspects an installed environment by default. The ``from-index`` subcommand queries a package index and
returns the resolved tree before installation.

Positional arguments are PEP 508 requirements or local source paths, the same strings you pass to ``pip install``.
You supply files with repeatable flags:

- positional ``REQUIREMENT`` -- an inline PEP 508 requirement string, version specifiers and extras included;
- ``--requirements FILE`` -- a standard ``requirements.txt`` or ``.in`` style file;
- ``--pyproject FILE`` -- a ``pyproject.toml`` handed to the resolver, which reads ``[project].dependencies`` and
  honors its ``[tool.nab]`` configuration.

Pass at least one source. Each edge shows the candidate version the resolver selected rather than a package on your
machine. The resolver produces one version per package with no requirement range, so edges read
``[candidate: <version>]`` instead of the ``[required: ..., installed: ...]`` pair shown for an installed
environment.

Resolve inline requirements
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

A single requirement resolves to its full tree:

.. runs-online
.. code-block:: console

    $ pipdeptree from-index "starlette"
    starlette==1.3.1
    └── anyio [candidate: 4.14.2]
        └── idna [candidate: 3.18]

Several requirements resolve together into one graph, and a version specifier bounds the pick:

.. runs-online
.. code-block:: console

    $ pipdeptree from-index "fastapi<=0.115.2" starlette
    fastapi==0.115.2
    ├── pydantic [candidate: 2.13.4]
    │   ├── annotated-types [candidate: 0.7.0]
    │   ├── pydantic-core [candidate: 2.46.4]
    │   │   └── typing-extensions [candidate: 4.16.0]
    │   ├── typing-extensions [candidate: 4.16.0]
    │   └── typing-inspection [candidate: 0.4.2]
    │       └── typing-extensions [candidate: 4.16.0]
    ├── starlette [candidate: 0.40.0]
    │   └── anyio [candidate: 4.14.2]
    │       └── idna [candidate: 3.18]
    └── typing-extensions [candidate: 4.16.0]

Request extras with the ``name[extra]`` syntax. The resolver pulls the extra's dependencies into the tree. They appear
as children, such as ``pysocks`` below, with the pinned version from the resolve and no extra label:

.. runs-online
.. code-block:: console

    $ pipdeptree from-index "requests[socks]"
    requests==2.34.2
    ├── certifi [candidate: 2026.6.17]
    ├── charset-normalizer [candidate: 3.4.9]
    ├── idna [candidate: 3.18]
    ├── pysocks [candidate: 1.7.1]
    └── urllib3 [candidate: 2.7.0]

An environment marker gates a requirement on the interpreter that the resolve targets. A matching marker includes the
requirement; a non-matching marker drops it. Quote the argument so the shell keeps the marker attached:

.. runs-online
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
``--hash`` line resolves ``requests`` while pipdeptree ignores the hash (the resolver verifies nothing from the
index). The same applies to ``--index-url`` and other pip-specific options.

Resolve from a pyproject.toml
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

With ``--pyproject`` as the sole source, the resolver receives the full ``[project]`` table and the file's
``[tool.nab]`` configuration:

.. code-block:: console

    $ pipdeptree from-index --pyproject pyproject.toml

Add any other source and the ``[project].dependencies`` from that pyproject merge into one combined resolve
instead. Its ``[tool.nab]`` settings drop out on this path:

.. code-block:: console

    $ pipdeptree from-index --pyproject pyproject.toml httpx

Combine and repeat sources
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Both flags repeat. The resolver merges their sources with the positional requirements:

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

The resolver searches indexes in order and uses the first index that contains a package. pip merges index results and
picks the highest version. Put the trusted index for each package first.

The index flags and their environment fallbacks override a ``--pyproject``'s own ``[tool.nab].indexes``. With no
flag and no environment override, the resolve uses the indexes declared in the pyproject.

.. code-block:: console

    $ PIP_INDEX_URL=https://nexus.corp/repository/pypi/simple pipdeptree from-index "internal-lib"
    $ pipdeptree from-index --pyproject pyproject.toml --index-url https://nexus.corp/repository/pypi/simple

Apply render flags
~~~~~~~~~~~~~~~~~~~

The graph and render flags behave as they do for the default command. Emit JSON for tooling:

.. runs-online
.. code-block:: console

    $ pipdeptree from-index "starlette" -o json
    [
        {
            "package": {
                "key": "anyio",
                "package_name": "anyio",
                "candidate_version": "4.14.2"
            },
            "dependencies": [
                {
                    "key": "idna",
                    "package_name": "idna",
                    "candidate_version": "3.18"
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
                "candidate_version": "1.3.1"
            },
            "dependencies": [
                {
                    "key": "anyio",
                    "package_name": "anyio",
                    "candidate_version": "4.14.2"
                }
            ]
        }
    ]

Trace why the resolver pulled a package in with ``--reverse`` (``-r``):

.. runs-online
.. code-block:: console

    $ pipdeptree from-index "fastapi<=0.115.2" --reverse --packages anyio
    anyio==4.14.2
    └── starlette==0.40.0 [requires: anyio==4.14.2]
        └── fastapi==0.115.2 [requires: starlette==0.40.0]

Other supported flags include ``-o mermaid``, the ``graphviz-*`` formats, ``--depth`` (``-d``), package filters,
``--extras`` (``-x``) and ``--encoding``:

.. code-block:: console

    $ pipdeptree from-index "fastapi<=0.115.2" --depth 1
    $ pipdeptree from-index "fastapi<=0.115.2" -o mermaid
    $ pipdeptree from-index "fastapi<=0.115.2" --packages starlette
    $ pipdeptree from-index "fastapi<=0.115.2" --exclude anyio
    $ pipdeptree from-index "requests[socks]" --extras none

Resolve editable, local and git requirements
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

For a requirement that points at a checkout instead of the index, the resolver reads the target's PEP 621 metadata.
Static ``[project]`` data needs no build. A project that declares dynamic dependencies triggers its build backend.

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

A ``--requirements`` or ``--pyproject`` file must exist; a missing one stops the command. Positional arguments accept
requirement strings. Use the file flags for paths:

.. code-block:: console

    $ pipdeptree from-index --requirements missing.txt
    source file does not exist: missing.txt

A bare wheel/sdist archive URL or a non-git VCS scheme (``hg+``/``bzr+``/``svn+``) has no index mapping:

.. code-block:: text
    :caption: requirements.txt

    foo @ https://h/foo-1.0-py3-none-any.whl

.. code-block:: console

    $ pipdeptree from-index --requirements requirements.txt
    URL requirements are not supported by the index resolver: foo @ https://h/foo-1.0-py3-none-any.whl

An unpinned git ref fails the same way, and so does a constraint that carries extras or a URL.

The installed-environment display options inspect on-disk files, so ``from-index`` does not accept them:

.. code-block:: console

    $ pipdeptree from-index "starlette" --metadata license
    error: unexpected argument '--metadata' found
    ...

The same holds for ``--computed`` (``-c``), ``--license`` and the environment-inspection options (``--python``,
``--path``, ``-l``/``-u``). ``from-index`` has neither package files nor an environment to read. No source is an error:

.. code-block:: console

    $ pipdeptree from-index
    pipdeptree: error: from-index needs at least one REQUIREMENT, --requirements FILE, or --pyproject FILE

from-lock (render a PEP 751 lock)
---------------------------------

The ``from-lock`` subcommand reads a `PEP 751 <https://peps.python.org/pep-0751/>`_ lock file
(``pylock.toml``) and renders its dependency tree. A lock records the pinned packages, their versions and the edges
between them. ``from-lock`` runs **offline** with no package index or network on Python 3.10 through 3.14. The native
extension parses TOML with Rust's ``toml`` crate. Take this lock:

.. code-block:: toml
    :caption: pylock.toml

    lock-version = "1.0"

    [[packages]]
    name = "build"
    version = "1.5.0"
    dependencies = [{ name = "packaging" }, { name = "pyproject-hooks" }]

    [[packages]]
    name = "packaging"
    version = "26.2"

    [[packages]]
    name = "pyproject-hooks"
    version = "1.2.0"

.. code-block:: console

    $ pipdeptree from-lock pylock.toml
    build==1.5.0
    ├── packaging [candidate: 26.2]
    └── pyproject-hooks [candidate: 1.2.0]

Each edge shows the ``candidate:`` version the lock pinned, not a package on your machine. pipdeptree does not inspect
an installed environment or install anything.

Producing a pylock.toml
~~~~~~~~~~~~~~~~~~~~~~~~

PEP 751 emitters write files that ``from-lock`` can read. :pypi:`uv` exports one from a project:

.. code-block:: console

    $ uv export -o pylock.toml          # or: uv lock then export
    $ pipdeptree from-lock pylock.toml

Render flags on a lock
~~~~~~~~~~~~~~~~~~~~~~~~

The lock supplies names, versions and edges, so the graph and render flags behave as they do for the default command.
Use ``--packages`` (``-p``), ``--exclude`` (``-e``), ``--depth`` (``-d``), ``--extras`` (``-x``), ``--reverse``
(``-r``), ``--encoding`` or an output format from ``-o``.

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

Use the installed-environment filters on lock trees. Keep one root with ``--packages``:

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

.. code-block:: toml
    :caption: pylock.toml

    lock-version = "1.0"

    [[packages]]
    name = "build"
    version = "1.5.0"

    [[packages]]
    name = "packaging"
    version = "26.2"

    [[packages]]
    name = "pyproject-hooks"
    version = "1.2.0"

.. code-block:: console

    $ pipdeptree from-lock pylock.toml
    build==1.5.0
    packaging==26.2
    pyproject-hooks==1.2.0

Lock limitations
~~~~~~~~~~~~~~~~~

A lock carries names, versions and edges, so the installed-environment display options have nothing to read. The
subcommand omits them:

.. code-block:: console

    $ pipdeptree from-lock pylock.toml --metadata license
    error: unexpected argument '--metadata' found
    ...
    $ pipdeptree from-lock pylock.toml --license
    error: unexpected argument '--license' found
    ...

The same holds for ``--computed`` (``-c``) and the environment-inspection options (``--python``, ``--path``,
``-l``/``-u``): a lock has no ``METADATA`` file, no on-disk sizes and no environment to point at.

A missing lock file stops the command with a message and exit code 1:

.. code-block:: console

    $ pipdeptree from-lock missing.toml
    lock file does not exist: missing.toml
    $ echo $?
    1

Malformed TOML returns exit code 1. ``from-lock`` also rejects a TOML file with no ``packages`` array:

.. code-block:: toml
    :caption: pylock.toml

    lock-version = "1.0"

.. code-block:: console

    $ pipdeptree from-lock pylock.toml
    missing 'packages' array

pipdeptree reports the parse error for an invalid package entry:

.. code-block:: toml
    :caption: pylock.toml

    lock-version = "1.0"

    [[packages]]
    version = "1"

.. code-block:: console

    $ pipdeptree from-lock pylock.toml
    package is missing 'name'

Filtering packages
------------------

By default, pipdeptree shows the full dependency tree of your environment:

.. code-block:: console

    $ pipdeptree
    covdefaults==2.3.0
    └── coverage [required: >=6.0.2, installed: 7.15.1]
    cryptography==2.7
    diff_cover==10.3.0
    ├── chardet [required: >=3.0.0, installed: 7.4.3]
    ├── Jinja2 [required: >=2.7.1, installed: 3.1.6]
    │   └── MarkupSafe [required: >=2.0, installed: 3.0.3]
    ├── pluggy [required: >=0.13.1,<2, installed: 1.6.0]
    └── Pygments [required: >=2.19.1,<3.0.0, installed: 2.20.0]
    oauthlib==3.0.0
    pipdeptree==4.0.0
    ├── nab-index [required: >=0.0.8, installed: 0.0.8]
    │   ├── packaging [required: >=24.0, installed: 26.2]
    │   ├── truststore [required: >=0.10, installed: 0.10.4]
    │   ├── typing_extensions [required: >=4.6, installed: 4.16.0]
    │   └── urllib3 [required: >=2.0, installed: 2.7.0]
    └── nab-python [required: >=0.0.8, installed: 0.0.8]
        ├── build [required: >=1.2, installed: 1.5.1]
        │   ├── packaging [required: >=24.0, installed: 26.2]
        │   └── pyproject_hooks [required: Any, installed: 1.2.0]
        ├── installer [required: >=0.7, installed: 1.0.1]
        ├── nab-index [required: ==0.0.8, installed: 0.0.8]
        │   ├── packaging [required: >=24.0, installed: 26.2]
        │   ├── truststore [required: >=0.10, installed: 0.10.4]
        │   ├── typing_extensions [required: >=4.6, installed: 4.16.0]
        │   └── urllib3 [required: >=2.0, installed: 2.7.0]
        ├── nab-resolver [required: ==0.0.8, installed: 0.0.8]
        │   └── typing_extensions [required: >=4.6, installed: 4.16.0]
        ├── pyproject_hooks [required: >=1.2, installed: 1.2.0]
        ├── tomli [required: >=2.0, installed: 2.4.1]
        ├── tomli_w [required: >=1.2, installed: 1.2.0]
        └── typing_extensions [required: >=4.6, installed: 4.16.0]
    pyjwt==1.7.1
    PySocks==1.7.1
    pytest-cov==7.1.0
    ├── coverage [required: >=7.10.6, installed: 7.15.1]
    ├── pluggy [required: >=1.2, installed: 1.6.0]
    └── pytest [required: >=7, installed: 9.1.1]
        ├── iniconfig [required: >=1.0.1, installed: 2.3.0]
        ├── packaging [required: >=22, installed: 26.2]
        ├── pluggy [required: >=1.5,<2, installed: 1.6.0]
        └── Pygments [required: >=2.7.2, installed: 2.20.0]
    requests==2.32.3
    ├── certifi [required: >=2017.4.17, installed: 2024.8.30]
    ├── charset_normalizer [required: >=2,<4, installed: 3.4.0]
    ├── idna [required: >=2.5,<4, installed: 3.10]
    └── urllib3 [required: >=1.21.1,<3, installed: 2.7.0]

Show selected packages with ``--packages`` (``-p``):

.. code-block:: console

    $ pipdeptree --packages pytest
    pytest==9.1.1
    ├── iniconfig [required: >=1.0.1, installed: 2.3.0]
    ├── packaging [required: >=22, installed: 26.2]
    ├── pluggy [required: >=1.5,<2, installed: 1.6.0]
    └── Pygments [required: >=2.7.2, installed: 2.20.0]

Separate multiple packages with commas. You can use wildcards:

.. code-block:: console

    $ pipdeptree --packages 'pytest*'
    pytest-cov==7.1.0
    ├── coverage [required: >=7.10.6, installed: 7.15.1]
    ├── pluggy [required: >=1.2, installed: 1.6.0]
    └── pytest [required: >=7, installed: 9.1.1]
        ├── iniconfig [required: >=1.0.1, installed: 2.3.0]
        ├── packaging [required: >=22, installed: 26.2]
        ├── pluggy [required: >=1.5,<2, installed: 1.6.0]
        └── Pygments [required: >=2.7.2, installed: 2.20.0]

A package entry may carry an extras spec such as ``somepackage[extra1,extra2]`` to include its optional dependencies.
pipdeptree strips the extras spec before matching the name, so wildcards such as ``somepackage*[extra1]`` still work.
pipdeptree includes an extra requested through ``--packages`` even with ``--extras none``:

.. code-block:: console

    $ pipdeptree --packages "requests[socks]" --extras none
    requests==2.32.3
    ├── certifi [required: >=2017.4.17, installed: 2024.8.30]
    ├── charset_normalizer [required: >=2,<4, installed: 3.4.0]
    ├── idna [required: >=2.5,<4, installed: 3.10]
    ├── PySocks [required: >=1.5.6,!=1.5.7, installed: 1.7.1, extra: socks]
    └── urllib3 [required: >=1.21.1,<3, installed: 2.7.0]

Excluding packages
------------------

Use ``--exclude`` (``-e``) to hide specific packages:

.. code-block:: console

    $ pipdeptree --exclude pip,pipdeptree,setuptools,wheel
    covdefaults==2.3.0
    └── coverage [required: >=6.0.2, installed: 7.15.1]
    cryptography==2.7
    diff_cover==10.3.0
    ├── chardet [required: >=3.0.0, installed: 7.4.3]
    ├── Jinja2 [required: >=2.7.1, installed: 3.1.6]
    │   └── MarkupSafe [required: >=2.0, installed: 3.0.3]
    ├── pluggy [required: >=0.13.1,<2, installed: 1.6.0]
    └── Pygments [required: >=2.19.1,<3.0.0, installed: 2.20.0]
    nab-python==0.0.8
    ├── build [required: >=1.2, installed: 1.5.1]
    │   ├── packaging [required: >=24.0, installed: 26.2]
    │   └── pyproject_hooks [required: Any, installed: 1.2.0]
    ├── installer [required: >=0.7, installed: 1.0.1]
    ├── nab-index [required: ==0.0.8, installed: 0.0.8]
    │   ├── packaging [required: >=24.0, installed: 26.2]
    │   ├── truststore [required: >=0.10, installed: 0.10.4]
    │   ├── typing_extensions [required: >=4.6, installed: 4.16.0]
    │   └── urllib3 [required: >=2.0, installed: 2.7.0]
    ├── nab-resolver [required: ==0.0.8, installed: 0.0.8]
    │   └── typing_extensions [required: >=4.6, installed: 4.16.0]
    ├── pyproject_hooks [required: >=1.2, installed: 1.2.0]
    ├── tomli [required: >=2.0, installed: 2.4.1]
    ├── tomli_w [required: >=1.2, installed: 1.2.0]
    └── typing_extensions [required: >=4.6, installed: 4.16.0]
    oauthlib==3.0.0
    pyjwt==1.7.1
    PySocks==1.7.1
    pytest-cov==7.1.0
    ├── coverage [required: >=7.10.6, installed: 7.15.1]
    ├── pluggy [required: >=1.2, installed: 1.6.0]
    └── pytest [required: >=7, installed: 9.1.1]
        ├── iniconfig [required: >=1.0.1, installed: 2.3.0]
        ├── packaging [required: >=22, installed: 26.2]
        ├── pluggy [required: >=1.5,<2, installed: 1.6.0]
        └── Pygments [required: >=2.7.2, installed: 2.20.0]
    requests==2.32.3
    ├── certifi [required: >=2017.4.17, installed: 2024.8.30]
    ├── charset_normalizer [required: >=2,<4, installed: 3.4.0]
    ├── idna [required: >=2.5,<4, installed: 3.10]
    └── urllib3 [required: >=1.21.1,<3, installed: 2.7.0]

Use ``--exclude-dependencies`` to hide their transitive dependencies:

.. code-block:: console

    $ pipdeptree --exclude pipdeptree --exclude-dependencies
    covdefaults==2.3.0
    └── coverage [required: >=6.0.2, installed: 7.15.1]
    cryptography==2.7
    diff_cover==10.3.0
    ├── chardet [required: >=3.0.0, installed: 7.4.3]
    ├── Jinja2 [required: >=2.7.1, installed: 3.1.6]
    │   └── MarkupSafe [required: >=2.0, installed: 3.0.3]
    ├── pluggy [required: >=0.13.1,<2, installed: 1.6.0]
    └── Pygments [required: >=2.19.1,<3.0.0, installed: 2.20.0]
    oauthlib==3.0.0
    pyjwt==1.7.1
    PySocks==1.7.1
    pytest-cov==7.1.0
    ├── coverage [required: >=7.10.6, installed: 7.15.1]
    ├── pluggy [required: >=1.2, installed: 1.6.0]
    └── pytest [required: >=7, installed: 9.1.1]
        ├── iniconfig [required: >=1.0.1, installed: 2.3.0]
        ├── pluggy [required: >=1.5,<2, installed: 1.6.0]
        └── Pygments [required: >=2.7.2, installed: 2.20.0]
    requests==2.32.3
    ├── certifi [required: >=2017.4.17, installed: 2024.8.30]
    ├── charset_normalizer [required: >=2,<4, installed: 3.4.0]
    └── idna [required: >=2.5,<4, installed: 3.10]

``packaging`` no longer appears under ``pytest`` because the command excluded it as a transitive dependency of
``pipdeptree``.

Reverse dependency lookup
-------------------------

Use ``--reverse`` (``-r``) with ``--packages`` to find the packages that require a dependency:

.. code-block:: console

    $ pipdeptree --reverse --packages pygments
    Pygments==2.20.0
    ├── diff_cover==10.3.0 [requires: pygments>=2.19.1,<3.0.0]
    └── pytest==9.1.1 [requires: pygments>=2.7.2]
        └── pytest-cov==7.1.0 [requires: pytest>=7]

Writing requirements files
--------------------------

Extract top-level packages with a zero-depth tree:

.. code-block:: console

    $ pipdeptree --depth 0
    covdefaults==2.3.0
    cryptography==2.7
    diff_cover==10.3.0
    oauthlib==3.0.0
    pipdeptree==4.0.0
    pyjwt==1.7.1
    PySocks==1.7.1
    pytest-cov==7.1.0
    requests==2.32.3

Use freeze format for pip-compatible output:

.. code-block:: console

    $ pipdeptree -o freeze --warn silence | grep -E '^[a-zA-Z0-9\-]+' > requirements.txt

Freeze output is a human-readable lock file with indented dependencies:

.. code-block:: console

    $ pipdeptree --packages pytest -o freeze
    pytest==9.1.1
      iniconfig==2.3.0
      packaging==26.2
      pluggy==1.6.0
      Pygments==2.20.0

Warning control
---------------

pipdeptree warns about conflicting and circular dependencies on stderr. Control this with ``-w``:

- ``-w suppress`` (default): show warnings and exit 0.
- ``-w silence``: hide warnings and exit 0.
- ``-w fail``: show warnings and exit 1 if pipdeptree finds a problem (useful in CI).

.. code-block:: console

    $ pipdeptree -w fail
    $ echo $?
    0

A conflict adds warnings and a non-zero exit code:

.. conflicting-environment
.. code-block:: console

    $ pipdeptree -w fail
    Jinja2==2.11.2
    └── MarkupSafe [required: >=0.23, installed: 0.22]
    Warning: dependency problems found:
    * Jinja2==2.11.2
      - markupsafe [required: >=0.23, installed: 0.22]
    ------------------------------------------------------------------------
    $ echo $?
    1

Use from Python or a notebook
-----------------------------

Call :func:`pipdeptree.render` when a Jupyter cell or another environment has no command-line access. It returns the
dependency tree as a string without ``argv`` or stdout:

.. code-block:: python

    import pipdeptree

    print(pipdeptree.render())                       # text tree of the current env
    data = pipdeptree.render(output_format="json")   # JSON string, e.g. for json.loads
    sub = pipdeptree.render(packages="rich", reverse=True)

``output_format`` accepts ``text`` (default), ``json``, ``json-tree``, ``mermaid`` and ``dot`` (Graphviz source).
The programmatic renderer raises ``ValueError`` for binary Graphviz formats such as ``png`` or ``svg``. Use ``dot`` to
get the source, or use the command-line interface for binary rendering.

The return value is a ``str``, so ``print``, slicing and comparisons behave as usual. The default ``text`` format
implements notebook display hooks: the result renders as a Mermaid dependency diagram without a
Graphviz binary, falling back to an HTML ``<pre>`` and then plain text on front-ends that do not render Mermaid.
``str(render())`` and
``print(render())`` give the plain text tree. The other formats (``json``, ``json-tree``, ``mermaid``, ``dot``)
return a plain string with no rich display, so their JSON or source shows verbatim.

Unlike the CLI, :func:`pipdeptree.render` defaults to ``warn="silence"`` so a notebook cell stays free of stderr noise;
pass ``warn="suppress"`` to show warnings or ``warn="fail"`` to fail on them.

Depth limiting
--------------

Limit how deep the tree renders with ``-d``:

.. code-block:: console

    $ pipdeptree -d 1 --packages pytest-cov,pipdeptree
    pipdeptree==4.0.0
    ├── nab-index [required: >=0.0.8, installed: 0.0.8]
    └── nab-python [required: >=0.0.8, installed: 0.0.8]
    pytest-cov==7.1.0
    ├── coverage [required: >=7.10.6, installed: 7.15.1]
    ├── pluggy [required: >=1.2, installed: 1.6.0]
    └── pytest [required: >=7, installed: 9.1.1]

Use ``-d 0`` to show top-level packages without dependencies:

.. code-block:: console

    $ pipdeptree -d 0 --packages pytest-cov,pipdeptree
    pipdeptree==4.0.0
    pytest-cov==7.1.0

Package metadata
----------------

Display metadata fields from the package's ``METADATA`` file with ``--metadata`` (``-m``). Pass a comma-separated list
of field names. The renderer appends metadata to each package in parentheses:

.. code-block:: console

    $ pipdeptree --metadata license --packages pipdeptree --depth 0
    pipdeptree==4.0.0 (MIT License)

Combine multiple fields:

.. code-block:: console

    $ pipdeptree --metadata license,summary --packages pipdeptree --depth 0
    pipdeptree==4.0.0 (MIT License, Display installed Python package dependencies as a tree)

Common metadata fields: ``license``, ``summary``, ``author``, ``author-email``, ``home-page``, ``requires-python``.
pipdeptree accepts fields present in the package's ``METADATA`` file.

.. note::

   The ``--license`` flag still works for backwards compatibility. Use ``--metadata license`` instead; version 4
   deprecates ``--license``.

Computed fields
---------------

Display computed package information with ``--computed`` (``-c``):

- ``size`` -- installed size on disk (human-readable)
- ``size-raw`` -- installed size in bytes (integer, useful for JSON output)
- ``unique-deps-count`` -- number of dependencies exclusive to this package (hidden when there are none)
- ``unique-deps-names`` -- names of dependencies exclusive to this package (hidden when there are none)
- ``unique-deps-size`` -- total installed size of exclusive dependencies (hidden when there are none)

Unique dependencies are transitive: if removing a package would orphan a dependency, and that orphaned dependency
would in turn orphan its own dependencies, the renderer counts all of them. Rich output marks unique dependencies
with a ⭐ icon (alongside ✗ or ⚠ if applicable).

.. code-block:: console

    $ pipdeptree --computed size --packages pipdeptree --depth 0
    pipdeptree==4.0.0 (0 B)

.. code-block:: console

    $ pipdeptree --computed unique-deps-count,unique-deps-names,unique-deps-size --packages pipdeptree --depth 0
    pipdeptree==4.0.0 (12 unique deps, unique: build | installer | nab-index | nab-python | nab-resolver | packaging | pyproject-hooks | tomli | tomli-w | truststore | typing-extensions | urllib3, unique size: 0 B)

Both ``--metadata`` and ``--computed`` work with each output format. You can combine them. In JSON output, ``size_raw``
and ``unique_deps_count`` are native integers, while ``unique_deps_names`` is a list of strings.

Including extras
----------------

The default, ``--extras explicit``, follows an optional dependency when a parent requests that extra with
``name[extra]``. Use ``--extras active`` to show optional groups whose complete dependency set is present:

.. code-block:: console

    $ pipdeptree --extras active --packages oauthlib
    oauthlib==3.0.0
    ├── cryptography [required: Any, installed: 2.7, extra: signedtoken]
    └── pyjwt [required: >=1.0.0, installed: 1.7.1, extra: signedtoken]

Optional edges carry the extra's name. ``--extras none`` removes optional edges, while bare ``--extras`` is a
compatibility spelling of ``--extras explicit``. See :doc:`/explanation` for the three modes.

To surface one package's extra, request it through ``--packages`` using the ``somepackage[extra]`` syntax from the
"Filtering packages" section. pipdeptree shows that extra even with ``--extras none``.
