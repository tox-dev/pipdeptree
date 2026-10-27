###########
 Changelog
###########

.. towncrier-draft-entries:: Unreleased

.. towncrier release notes start

.. _release-4-2-10:

*********************
 4.2.10 (2026-10-27)
*********************

.. _release-4-2-10-fixed:

Fixed
-----

- Remove the module import fallback for dependency versions. Dependencies without distribution metadata now report an
  unknown version and are treated as missing across environment scans, lock inputs and the Python API (:pr:`743`) by
  :user:`kemzeb`.

.. _release-4-2-9:

********************
 4.2.9 (2026-10-19)
********************

.. _packaging-updates-4-2-9:

.. _release-4-2-9-packaging:

Packaging
---------

- Publish GitHub Releases with changelog notes, PyPI links, and version comparisons (:pull:`739`) by
  :user:`gaborbernat`.

.. _release-4-2-8:

********************
 4.2.8 (2026-10-15)
********************

.. _features-4-2-8:

.. _release-4-2-8-added:

Added
-----

- Add ``-o cyclonedx-json`` and ``render(output_format="cyclonedx-json")`` to export CycloneDX 1.5 JSON using
  ``cyclonedx-bom``, including dependency relationships, available installed licenses and extras, component external
  references, a timestamp, and a unique serial number. The renderer supports installed environments, PEP 751 locks, and
  index resolution (:pull:`731`) by :user:`kemzeb`.

.. _release-4-2-7:

********************
 4.2.7 (2026-10-10)
********************

.. _features-4-2-7:

.. _release-4-2-7-added:

Added
-----

- Show declared requirement ranges, markers and extras for dependencies resolved with ``from-index`` (:issue:`723`;
  :pull:`727`) by :user:`gaborbernat`.

.. _release-4-2-6:

********************
 4.2.6 (2026-10-10)
********************

.. _bug-fixes-4-2-6:

.. _release-4-2-6-fixed:

Fixed
-----

- Wrap rich summary values to fit the terminal width, preserving table borders when license breakdowns are long.
  (:issue:`725`; :pull:`726`) by :user:`gaborbernat`.

.. _release-4-2-5:

********************
 4.2.5 (2026-09-08)
********************

.. _packaging-updates-4-2-5:

.. _release-4-2-5-packaging:

Packaging
---------

- Remove the tracked ``VERSION`` file. Resolve build versions from ``PIPDEPTREE_VERSION``, Git tags, or sdist metadata,
  falling back to ``0.0.0`` when none is available (:issue:`699`; :pull:`705`) by :user:`gaborbernat`.

.. _release-4-2-4:

********************
 4.2.4 (2026-09-08)
********************

.. _bug-fixes-4-2-4:

.. _release-4-2-4-fixed:

Fixed
-----

- Fix ``from-index`` with nab 0.0.17 by adapting to its configuration and resolver APIs (:issue:`697`; :pull:`704`) by
  :user:`gaborbernat`.

.. _release-4-2-3:

********************
 4.2.3 (2026-08-31)
********************

.. _features-4-2-3:

.. _release-4-2-3-added:

Added
-----

- Publish Windows ``arm64`` wheels. Every Windows wheel was built for ``AMD64``, so ``pip`` and ``uv`` fell back to the
  source distribution on Windows on ARM, where building the Rust extension needs a local ``cargo`` and MSVC toolchain.
  The ``cp310`` abi3 wheel and the free-threaded ``cp314t`` and ``cp315t`` wheels now ship for that platform too; PyPy
  publishes no Windows ``arm64`` interpreter, so ``pp311`` stays ``AMD64`` only (:pull:`695`) by :user:`gaborbernat`.

.. _release-4-2-2:

********************
 4.2.2 (2026-08-26)
********************

.. _bug-fixes-4-2-2:

.. _release-4-2-2-fixed:

Fixed
-----

- Replace the removed ``nab-python`` dependency with ``nab-project`` (:issue:`681`; :pull:`683`) by :user:`gaborbernat`.

.. _release-4-2-1:

********************
 4.2.1 (2026-08-15)
********************

.. _release-4-2-1-fixed:

Fixed
-----

- Run under an interpreter built from a git checkout. Such a build reports its version with a trailing plus
  (``3.13.5+``), which PEP 440 rejects as an empty local segment. The trailing plus is now dropped, and an invalid
  marker names the interpreter versions it came from. (:issue:`656`; :pull:`657`) by :user:`gaborbernat`.
- Stop warning about the console-script launcher on Windows. Python puts ``pipdeptree.exe`` on ``sys.path``, but it is
  not an archive. Only files with archive suffixes now trigger the warning. (:issue:`669`; :pull:`671`) by
  :user:`gaborbernat`.

.. _release-4-2-1-documentation:

Documentation
-------------

- Publish llms.txt from the docs build (:pull:`668`) by :user:`gaborbernat`.

.. _release-4-2-0:

********************
 4.2.0 (2026-07-31)
********************

.. _features-4-2-0:

.. _release-4-2-0-added:

Added
-----

- Publish ``cp315t`` wheels, so a free-threaded 3.15 installs a wheel instead of compiling the Rust extension.
  (:pull:`644`) by :user:`gaborbernat`.

.. _bug-fixes-4-2-0:

.. _release-4-2-0-fixed:

Fixed
-----

- Publish Linux ``aarch64`` wheels. 4.1.0 shipped none, so ``pip`` and ``uv`` fell back to the source distribution on
  ARM64 hosts, where building the Rust extension needs a local ``cargo`` and C toolchain (:pull:`640`) by
  :user:`gaborbernat`.
- Build from source on a free-threaded interpreter. The package asked for the limited API unconditionally and
  meson-python refuses to pair it with a free-threaded CPython, so the source build stopped before it started.
  (:pull:`643`) by :user:`gaborbernat`.

.. _packaging-updates-4-2-0:

.. _release-4-2-0-packaging:

Packaging
---------

- Take the released version from the git tag rather than from a file in the tree, so a release can no longer ship
  artifacts labeled with the previous version. 4.1.1 and 4.1.2 were tagged that way and reached no index (:pull:`647`)
  by :user:`gaborbernat`.

.. _release-4-1-0:

********************
 4.1.0 (2026-07-21)
********************

.. _release-4-1-0-added:

Added
-----

- Support Python 3.15 (:pull:`626`) by :user:`gaborbernat`.

.. _release-4-1-0-packaging:

Packaging
---------

- Ship a free-threaded wheel (:pull:`628`) by :user:`gaborbernat`.

.. _release-4-0-0:

********************
 4.0.0 (2026-07-20)
********************

.. _release-4-0-0-changes:

Changes
-------

- Replace the Python engine with a Rust extension (:pull:`618`) by :user:`gaborbernat`.

.. _release-4-0-0-performance:

Performance
-----------

- Cut startup and graph costs (:pull:`611`) by :user:`gaborbernat`.
- Cache rendered metadata (:pull:`612`) by :user:`gaborbernat`.
- Halve package size stat calls (:pull:`613`) by :user:`gaborbernat`.
- Cache frozen package specifiers (:pull:`614`) by :user:`gaborbernat`.
- Reuse computed package sizes (:pull:`615`) by :user:`gaborbernat`.

.. _release-4-0-0-packaging:

Packaging
---------

- Publish PyPy wheels (:pull:`624`) by :user:`gaborbernat`.

.. _release-3-1-1:

********************
 3.1.1 (2026-07-03)
********************

.. _release-3-1-1-fixed:

Fixed
-----

- Validate archive hash parts (:pull:`606`) by :user:`CodingFeng101`.
- Scope optional deps to requesting edge (:pull:`608`) by :user:`gaborbernat`.

.. _release-3-1-0:

********************
 3.1.0 (2026-06-03)
********************

.. _release-3-1-0-added:

Added
-----

- Add --summary health report (text/rich/json) (:pull:`597`) by :user:`gaborbernat`.

.. _release-3-0-0:

********************
 3.0.0 (2026-06-03)
********************

.. _release-3-0-0-added:

Added
-----

- Accept extras in --packages filter (:pull:`589`) by :user:`gaborbernat`.
- Add programmatic render() for notebooks (:pull:`590`) by :user:`gaborbernat`.
- Add from-index subcommand to resolve a tree from a package index (:pull:`593`) by :user:`gaborbernat`.
- Add from-lock subcommand to render a PEP 751 lock offline (:pull:`595`) by :user:`gaborbernat`.

.. _release-3-0-0-changes:

Changes
-------

- Auto-detect active virtualenv by default (:pull:`588`) by :user:`gaborbernat`.
- Default --extras to explicit, add active/none modes (:pull:`587`) by :user:`gaborbernat`.
- Resolve the setuptools version through the normal import fallback when distribution metadata is missing (:pull:`585`)
  by :user:`kemzeb`.

.. _release-2-35-3:

*********************
 2.35.3 (2026-05-17)
*********************

.. _release-2-35-3-performance:

Performance
-----------

- Make --extras tractable on real environments (:pull:`580`) by :user:`gaborbernat`.

.. _release-2-35-2:

*********************
 2.35.2 (2026-05-01)
*********************

.. _release-2-35-2-fixed:

Fixed
-----

- Fix dependency sorting for freeze, text, and rich output formats (:pull:`578`) by :user:`kemzeb`.

.. _release-2-35-1:

*********************
 2.35.1 (2026-04-10)
*********************

.. _release-2-35-1-fixed:

Fixed
-----

- Fix metadata lookup to use distribution object (:pull:`569`) by :user:`gaborbernat`.

.. _release-2-35-0:

*********************
 2.35.0 (2026-04-10)
*********************

.. _release-2-35-0-added:

Added
-----

- Add --metadata and --computed options (:pull:`563`) by :user:`gaborbernat`.

.. _release-2-35-0-fixed:

Fixed
-----

- Write binary graphviz output to temp file when stdout is tty (:pull:`564`) by :user:`BlocksecPHD`.

.. _release-2-35-0-documentation:

Documentation
-------------

- Show ``pipdeptree`` as the program name in the generated CLI reference (:pull:`561`) by :user:`kemzeb`.

.. _release-2-34-0:

*********************
 2.34.0 (2026-03-23)
*********************

.. _release-2-34-0-documentation:

Documentation
-------------

- Add Sphinx documentation site (:pull:`557`) by :user:`gaborbernat`.
- Simplify README, link to Sphinx docs (:pull:`558`) by :user:`gaborbernat`.

.. _release-2-33-0:

*********************
 2.33.0 (2026-03-21)
*********************

.. _release-2-33-0-fixed:

Fixed
-----

- Allow fallback to different env detectors (:pull:`555`) by :user:`kemzeb`.

.. _release-2-33-0-packaging:

Packaging
---------

- Drop pip dependency, use stdlib for metadata (:pull:`552`) by :user:`gaborbernat`.

.. _release-2-32-0:

*********************
 2.32.0 (2026-03-19)
*********************

.. _release-2-32-0-added:

Added
-----

- Add --extras flag for optional deps (:pull:`549`) by :user:`gaborbernat`.
- Add Rich library support for enhanced tree output (:pull:`551`) by :user:`gaborbernat`.

.. _release-2-32-0-fixed:

Fixed
-----

- Expect dist.metadata to be None or raise an exception if invalid (:pull:`554`) by :user:`frenzymadness`.

.. _release-2-32-0-documentation:

Documentation
-------------

- Add security policy (:pull:`541`) by :user:`gaborbernat`.

.. _release-2-31-0:

*********************
 2.31.0 (2026-02-20)
*********************

.. _release-2-31-0-added:

Added
-----

- Support --depth for graphviz output format (:pull:`538`) by :user:`Fridayai700`.

.. _release-2-30-0:

*********************
 2.30.0 (2025-11-12)
*********************

.. _release-2-30-0-added:

Added
-----

- Implement --output to centralize choosing an output format (:pull:`519`) by :user:`kemzeb`.

.. _release-2-29-0:

*********************
 2.29.0 (2025-10-10)
*********************

.. _release-2-29-0-added:

Added
-----

- Support Python 3.14 (:pull:`500`) by :user:`kemzeb`.
- Drop 3.9 support (:pull:`512`) by :user:`gaborbernat`.

.. _release-2-29-0-changes:

Changes
-------

- Have render functions call print() themselves rather than the caller (:pull:`506`) by :user:`kemzeb`.
- Require a value for ``--warn`` instead of accepting the bare option (:pull:`511`) by :user:`kemzeb`.

.. _release-2-28-0:

*********************
 2.28.0 (2025-07-20)
*********************

.. _release-2-28-0-added:

Added
-----

- Allow --exclude to be used with --include (:pull:`491`) by :user:`kemzeb`.

.. _release-2-27-0:

*********************
 2.27.0 (2025-07-11)
*********************

.. _release-2-27-0-added:

Added
-----

- Implement --exclude-dependencies (:pull:`488`) by :user:`kemzeb`.

.. _release-2-26-1:

*********************
 2.26.1 (2025-04-20)
*********************

.. _release-2-26-1-fixed:

Fixed
-----

- Handle exceptions when passed an invalid interpreter (:pull:`471`) by :user:`kemzeb`.

.. _release-2-26-0:

*********************
 2.26.0 (2025-03-24)
*********************

.. _release-2-26-0-added:

Added
-----

- Support for License-Expression field (:pull:`465`) by :user:`PalmtopTiger`.

.. _release-2-25-1:

*********************
 2.25.1 (2025-03-11)
*********************

.. _release-2-25-1-documentation:

Documentation
-------------

- Update CLI usage for --all by moving it to the "render" group (:pull:`458`) by :user:`kemzeb`.
- Update outdated graphviz docs (:pull:`463`) by :user:`kemzeb`.

.. _release-2-25-1-packaging:

Packaging
---------

- Use SPDX license identifier (:pull:`448`) by :user:`cdce8p`.

.. _release-2-25-0:

*********************
 2.25.0 (2025-01-26)
*********************

.. _release-2-25-0-added:

Added
-----

- Drop support for Python 3.8 (:pull:`444`) by :user:`kemzeb`.

.. _release-2-24-0:

*********************
 2.24.0 (2024-11-26)
*********************

.. _release-2-24-0-added:

Added
-----

- Implement --path argument (:pull:`429`) by :user:`kemzeb`.

.. _release-2-23-4:

*********************
 2.23.4 (2024-09-17)
*********************

.. _release-2-23-3:

*********************
 2.23.3 (2024-09-07)
*********************

.. _release-2-23-2:

*********************
 2.23.2 (2024-09-07)
*********************

.. _release-2-23-2-added:

Added
-----

- Declare 3.13 support (:pull:`406`) by :user:`gaborbernat`.

.. _release-2-23-1:

*********************
 2.23.1 (2024-07-12)
*********************

.. _release-2-23-1-changes:

Changes
-------

- Allow pre-releases when detecting version conflicts (:pull:`394`) by :user:`kemzeb`.

.. _release-2-23-1-fixed:

Fixed
-----

- Use ``__contains__`` to avoid ``KeyError`` with importlib_metadata==8.0.0 (:pull:`384`) by :user:`kemzeb`.

.. _release-2-23-0:

*********************
 2.23.0 (2024-06-17)
*********************

.. _release-2-23-0-changes:

Changes
-------

- Print resolved interpreter when using env detection (:pull:`379`) by :user:`stasfilin`.

.. _release-2-22-0:

*********************
 2.22.0 (2024-06-03)
*********************

.. _release-2-22-0-fixed:

Fixed
-----

- Warn about and ignore invalid package metadata in the environment (:pull:`373`) by :user:`kemzeb`.

.. _release-2-21-0:

*********************
 2.21.0 (2024-05-20)
*********************

.. _release-2-21-0-added:

Added
-----

- Implement --python auto for virtual environment detection (:pull:`366`) by :user:`kemzeb`.

.. _release-2-20-0:

*********************
 2.20.0 (2024-05-07)
*********************

.. _release-2-20-0-fixed:

Fixed
-----

- Mimic pip when handling --user-only in a virtual environment (:pull:`364`) by :user:`kemzeb`.

.. _release-2-19-1:

*********************
 2.19.1 (2024-04-29)
*********************

.. _release-2-19-1-documentation:

Documentation
-------------

- Point "Changelog" project URL at Releases page (:pull:`359`) by :user:`jwodder`.

.. _release-2-19-0:

*********************
 2.19.0 (2024-04-28)
*********************

.. _release-2-19-0-fixed:

Fixed
-----

- Have duplicate metadata and invalid req strings honor --warn option (:pull:`357`) by :user:`kemzeb`.

.. _release-2-18-1:

*********************
 2.18.1 (2024-04-13)
*********************

.. _release-2-18-0:

*********************
 2.18.0 (2024-04-10)
*********************

.. _release-2-18-0-fixed:

Fixed
-----

- Handle invalid requirement strings when using importlib.metadata (:pull:`345`) by :user:`kemzeb`.
- Discover packages through the selected interpreter for custom environments (:issue:`343`; :pull:`346`) by
  :user:`xiacunshun`.

.. _release-2-17-0:

*********************
 2.17.0 (2024-04-04)
*********************

.. _release-2-17-0-changes:

Changes
-------

- Replace pkg_resources with importlib.metadata and packaging (:pull:`333`) by :user:`xiacunshun`.

.. _release-2-17-0-fixed:

Fixed
-----

- Handle duplicated package metadata when using importlib.metadata (:pull:`342`) by :user:`kemzeb`.

.. _release-2-16-2:

*********************
 2.16.2 (2024-03-25)
*********************

.. _release-2-16-2-packaging:

Packaging
---------

- List pip as dependency (:pull:`336`) by :user:`pawamoy`.

.. _release-2-16-1:

*********************
 2.16.1 (2024-03-04)
*********************

.. _release-2-16-0:

*********************
 2.16.0 (2024-03-02)
*********************

.. _release-2-16-0-fixed:

Fixed
-----

- Fix key mismatch between requirements and dists (:pull:`325`) by :user:`f3flight`.

.. _release-2-15-1:

*********************
 2.15.1 (2024-02-24)
*********************

.. _release-2-15-1-fixed:

Fixed
-----

- Have --license work with --reverse (:pull:`321`) by :user:`kemzeb`.

.. _release-2-15-0:

*********************
 2.15.0 (2024-02-23)
*********************

.. _release-2-15-0-changes:

Changes
-------

- Have --license and --reverse options in the "render" argument group (:pull:`320`) by :user:`kemzeb`.

.. _release-2-14-0:

*********************
 2.14.0 (2024-02-15)
*********************

.. _release-2-14-0-added:

Added
-----

- Implement --license option (:pull:`318`) by :user:`kemzeb`.

.. _release-2-13-2:

*********************
 2.13.2 (2024-01-10)
*********************

.. _release-2-13-2-fixed:

Fixed
-----

- Use "Any" value if necessary for required version in JSON render (:pull:`310`) by :user:`kemzeb`.

.. _release-2-13-1:

*********************
 2.13.1 (2023-11-09)
*********************

.. _release-2-13-1-documentation:

Documentation
-------------

- Update README to show 2.13.0 CLI syntax (:pull:`300`) by :user:`dlqqq`.

.. _release-2-13-0:

*********************
 2.13.0 (2023-08-14)
*********************

.. _release-2-13-0-added:

Added
-----

- Add missing ``user_only`` field in ``Options`` (:pull:`275`) by :user:`kemzeb`.

.. _release-2-13-0-fixed:

Fixed
-----

- Exit with error when ``-p`` given patterns that fail to match (:pull:`279`) by :user:`kemzeb`.

.. _release-2-12-0:

*********************
 2.12.0 (2023-07-30)
*********************

.. _release-2-12-0-fixed:

Fixed
-----

- Detect dependency cycles beyond a depth = 2 (:pull:`274`) by :user:`kemzeb`.

.. _release-2-11-0:

*********************
 2.11.0 (2023-07-22)
*********************

.. _release-2-11-0-fixed:

Fixed
-----

- Have --packages and --all work together (:pull:`273`) by :user:`kemzeb`.

.. _release-2-10-2:

*********************
 2.10.2 (2023-07-17)
*********************

.. _release-2-10-1:

*********************
 2.10.1 (2023-07-17)
*********************

.. _release-2-10-1-fixed:

Fixed
-----

- Fix graphviz CLI failing (:pull:`271`) by :user:`gaborbernat`.

.. _release-2-10-0:

*********************
 2.10.0 (2023-07-15)
*********************

.. _release-2-10-0-added:

Added
-----

- Drop 3.7 support (:pull:`263`) by :user:`gaborbernat`.

.. _release-2-10-0-changes:

Changes
-------

- Split project to parts (:pull:`261`) by :user:`gaborbernat`.
- Improve CLI (:pull:`265`) by :user:`gaborbernat`.

.. _release-2-10-0-fixed:

Fixed
-----

- Fix entrypoints (:pull:`264`) by :user:`gaborbernat`.

.. _release-2-9-6:

********************
 2.9.6 (2023-07-14)
********************

.. _release-2-9-5:

********************
 2.9.5 (2023-07-11)
********************

.. _release-2-9-5-packaging:

Packaging
---------

- Add type information (:pull:`258`) by :user:`gaborbernat`.

.. _release-2-9-4:

********************
 2.9.4 (2023-07-07)
********************

.. _release-2-9-4-added:

Added
-----

- Allow to force encoding (:pull:`255`) by :user:`gaborbernat`.

.. _release-2-9-3:

********************
 2.9.3 (2023-06-16)
********************

.. _release-2-9-3-fixed:

Fixed
-----

- Retain casing of required package names (:pull:`248`) by :user:`kemzeb`.

.. _release-2-9-2:

********************
 2.9.2 (2023-06-15)
********************

.. _release-2-9-2-fixed:

Fixed
-----

- Resolve relative interpreter paths before inspecting a virtual environment (:pull:`247`) by :user:`gaborbernat`.

.. _release-2-9-1:

********************
 2.9.1 (2023-06-14)
********************

.. _release-2-9-0:

********************
 2.9.0 (2023-06-07)
********************

.. _release-2-9-0-added:

Added
-----

- Implement -d/--depth argument (:pull:`240`) by :user:`kemzeb`.

.. _release-2-8-0:

********************
 2.8.0 (2023-06-06)
********************

.. _release-2-8-0-changes:

Changes
-------

- Use unicode characters when rendering text (:pull:`239`) by :user:`kemzeb`.

.. _release-2-7-1:

********************
 2.7.1 (2023-05-11)
********************

.. _release-2-7-1-added:

Added
-----

- Add 3.12 support (:pull:`228`) by :user:`gaborbernat`.

.. _release-2-7-0:

********************
 2.7.0 (2023-03-25)
********************

.. _release-2-7-0-changes:

Changes
-------

- Implement: Use fnmatch for include and exclude #213 (:pull:`215`) by :user:`jensens`.

.. _release-2-6-0:

********************
 2.6.0 (2023-03-18)
********************

.. _release-2-6-0-fixed:

Fixed
-----

- Handle mermaid output for a reversed tree by :user:`ajkerrigan`.

.. _release-2-5-2:

********************
 2.5.2 (2023-03-04)
********************

.. _release-2-5-2-fixed:

Fixed
-----

- Fix Mermaid not working with reserved keyword package names by :user:`kdeldycke`.

.. _release-2-5-1:

********************
 2.5.1 (2023-03-03)
********************

.. _release-2-5-1-fixed:

Fixed
-----

- Fix Mermaid flag by :user:`kdeldycke`.

.. _release-2-5-0:

********************
 2.5.0 (2023-02-18)
********************

.. _release-2-5-0-added:

Added
-----

- Implements Mermaid output (:pull:`195`) by :user:`kdeldycke`.

.. _release-2-4-0:

********************
 2.4.0 (2023-02-17)
********************

.. _release-2-4-0-fixed:

Fixed
-----

- Make the output of the dot format deterministic and stable (:pull:`189`) by :user:`kdeldycke`.

.. _release-2-3-3:

********************
 2.3.3 (2022-10-30)
********************

.. _release-2-3-3-documentation:

Documentation
-------------

- Update README for tested Python versions (:pull:`178`) by :user:`tomkins`.

.. _release-2-3-2:

********************
 2.3.2 (2022-10-30)
********************

.. _release-2-3-2-changes:

Changes
-------

- Generalize license (:pull:`179`) by :user:`gaborbernat`.

.. _release-2-3-1:

********************
 2.3.1 (2022-09-08)
********************

.. _release-2-3-1-fixed:

Fixed
-----

- Use ``importlib.metadata`` to guess version of package before fallback to ``pkg.__version__`` by :user:`saaketp` and
  :user:`gaborbernat`.

.. _release-2-3-0:

********************
 2.3.0 (2022-09-06)
********************

.. _release-2-3-0-added:

Added
-----

- Add support for invocation via ``-m`` by :user:`gaborbernat`.
- Support Python 3.11 by :user:`dqkqd`.

.. _release-2-3-0-packaging:

Packaging
---------

- Now packaged via hatchling instead of setuptools by :user:`gaborbernat`.

.. _release-2-2-1:

********************
 2.2.1 (2022-01-09)
********************

.. _release-2-2-1-fixed:

Fixed
-----

- Fix ``--user-only`` and ``--freeze`` flags which were broken after the last release by :user:`naiquevin`.
- Fix for compatibility with new version of ``graphviz`` (>= 0.18.1) by :user:`rodrigomologni` and :user:`naiquevin`.

.. _release-2-2-0:

********************
 2.2.0 (2021-10-12)
********************

.. _release-2-2-0-fixed:

Fixed
-----

- Fix pipdeptree to work with pip version 21.3. The _internal pip api that was being used earlier is now replaced with
  new functions (:pull:`154`) by :user:`stonebig`.

.. _release-2-1-0:

********************
 2.1.0 (2021-07-31)
********************

.. _release-2-1-0-changes:

Changes
-------

- JSON output is sorted alphabetically to make it deterministic by :user:`pjw91`.

.. _release-2-1-0-fixed:

Fixed
-----

- Fix --freeze option due to breaking changes in pip's internal api in version > 21.1.1 by :user:`naiquevin`.

.. _release-2-1-0-packaging:

Packaging
---------

- Include license file in dist package by :user:`milos-korenciak`.

.. _release-2-0-0:

********************
 2.0.0 (2020-12-25)
********************

.. _release-2-0-0-added:

Added
-----

- Support for running in the context of a virtualenv (without installing pipdeptree inside the virtualenv) by
  :user:`gaborbernat`.

.. _release-2-0-0-fixed:

Fixed
-----

- Avoid crash when rendering cyclic dependencies by :user:`StephenWeber`.
- Fix graphviz (dot file) output by :user:`foreignmeloman`.
- Handle a (rare) case while guessing version of a package by :user:`naiquevin`.

.. _release-2-0-0b1:

**********************
 2.0.0b1 (2020-06-13)
**********************

.. _release-2-0-0b1-added:

Added
-----

- Support Python ``3.7`` and ``3.8``; drop Python ``3.3`` support by :user:`naiquevin`.

.. _release-2-0-0b1-changes:

Changes
-------

- In this first beta release targeting ``2.0.0``, the underlying code is heavily refactored to make different CLI
  options work well with each other. This was a serious limitation in older version ``<=1.0.0`` which made it difficult
  to extend the tool. For more information about the plans for 2.0.0 release, please check ``docs/v2beta-opts.org`` file
  by :user:`naiquevin`.
- The ``--reverse``, ``--packages`` and ``--exclude`` flags now work with ``--json-tree`` and ``--graph-output`` by
  :user:`naiquevin`.

.. _release-1-0-0:

********************
 1.0.0 (2020-06-13)
********************

.. _release-1-0-0-changes:

Changes
-------

- Use ``pkg_resources`` vendored with ``pip`` by :user:`sinoroc`.

.. _release-0-13-2:

*********************
 0.13.2 (2019-01-23)
*********************

.. _release-0-13-2-fixed:

Fixed
-----

- Fixed call to ``FrozenRequirement.to_dist`` to handle changes to the internal api of pip version 19.0. The api change
  is because dependency links support has been removed in pip 19.0 See more: https://github.com/pypa/pip/pull/6060
  https://github.com/pypa/pip/pull/5881/commits/46ffb13f13f69c509fd253329da49889008f8e23 by :user:`naiquevin`.

.. _release-0-13-1:

*********************
 0.13.1 (2018-10-08)
*********************

.. _release-0-13-1-fixed:

Fixed
-----

- Fixed import after changes in pip._internal introduced in pip version 18.1 by :user:`naiquevin`.

.. _release-0-13-0:

*********************
 0.13.0 (2018-07-01)
*********************

.. _release-0-13-0-added:

Added
-----

- Added ``--exclude`` option to exclude packages specified as CSV by :user:`ciarancourtney`.

.. _release-0-13-0-fixed:

Fixed
-----

- In case of multiple version specs eg. <x,>=y, fix the order to ensure consistent output. The sorting is naive - puts
  the '>' prior to '<', and '!' by :user:`pjw91`.

.. _release-0-12-1:

*********************
 0.12.1 (2018-04-15)
*********************

.. _release-0-12-1-fixed:

Fixed
-----

- Fix import of 'FrozenRequirement' for pip 10.0.0 by :user:`naiquevin`.

.. _release-0-12-0:

*********************
 0.12.0 (2018-04-15)
*********************

.. _release-0-12-0-fixed:

Fixed
-----

- Support pip 10.0.0 without dropping older pip versions by :user:`sourcenouveau`.

.. _release-0-11-0:

*********************
 0.11.0 (2018-02-24)
*********************

.. _release-0-11-0-added:

Added
-----

- Added support for nested json output (``--json-tree`` flag). Behavior of ``--json`` stays the same by
  :user:`haikoschol`.

.. _release-0-10-1:

*********************
 0.10.1 (2017-03-19)
*********************

.. _release-0-10-1-fixed:

Fixed
-----

- Revert PR #65 to restore ``--json`` with ``--packages`` by :user:`naiquevin`.

.. _release-0-10-0:

*********************
 0.10.0 (2017-03-19)
*********************

.. _release-0-10-0-added:

Added
-----

- Dropped support for Python 2.6 by :user:`naiquevin`.
- ``--json`` and ``--packages`` options can now be used together by :user:`kdeldycke`.

.. _release-0-10-0-fixed:

Fixed
-----

- Fixed binary graphviz output on Python 3 by :user:`jmbowman`.

.. _release-0-9-0:

********************
 0.9.0 (2017-01-07)
********************

.. _release-0-9-0-added:

Added
-----

- Support for visualizing dependency tree of packages using Graphviz in various formats by :user:`johnyf` and
  :user:`Dunedan`.
- Support to consider only packages installed in the user directory by :user:`naiquevin`.
- CLI option to print version by :user:`naiquevin`.

.. _release-0-9-0-fixed:

Fixed
-----

- Fix the output to use a better term, "Any" instead of "None" if a dependency doesn't need to be of a specific version
  by :user:`naiquevin`.

.. _release-0-8-0:

********************
 0.8.0 (2016-10-23)
********************

.. _release-0-8-0-changes:

Changes
-------

- Use pip's list of excluded default packages. This means that the ``pipdeptree`` package itself is no longer excluded
  and will appear in the output tree by :user:`jimbocoder`.

.. _release-0-8-0-fixed:

Fixed
-----

- Fix the bug that caused a package to appear in conflicting deps although it's installed version could be guessed by
  :user:`naiquevin`.

.. _release-0-7-0:

********************
 0.7.0 (2016-08-21)
********************

.. _release-0-7-0-changes:

Changes
-------

- Alphabetical sorting of packages in the output by :user:`naiquevin`.

.. _release-0-7-0-fixed:

Fixed
-----

- Fix for a bug in reverse mode by :user:`naiquevin`.
- Fallback to guess installed version of packages "skipped" by pip by :user:`naiquevin`.

.. _release-0-6-0:

********************
 0.6.0 (2016-04-09)
********************

.. _release-0-6-0-changes:

Changes
-------

- Better checking for possibly "confusing" dependencies, hence the word "confusing" in the warning message is now
  replaced with "conflicting" (:pull:`37`) by :user:`t0m`.
- The ``--nowarn`` flag is now replaced with ``--warn`` with 'silence', 'suppress' and 'fail' as possible values, thus
  giving more control over what should happen when there are warnings. The default behavior (ie. when the flag is not
  specified) remains the same (:pull:`39`) by :user:`t0m`.

.. _release-0-6-0-fixed:

Fixed
-----

- Fix a bug when rendering dependencies of packages (:pull:`38`) by :user:`chsava`.
- Fixes for Python 3.5 support (:pull:`40`) by :user:`adamchainz`.

.. _release-0-5-0:

********************
 0.5.0 (2015-11-14)
********************

.. _release-0-5-0-added:

Added
-----

- Add ``--reverse`` flag to show the dependency tree upside down by :user:`naiquevin`.
- Add ``--packages`` flag to show only select packages in output by :user:`naiquevin`.
- Add ``--json`` flag to output dependency tree as json that may be used by external tools by :user:`naiquevin`.
