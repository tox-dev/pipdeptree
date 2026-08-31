###########
 Changelog
###########

.. towncrier-draft-entries:: Unreleased

.. towncrier release notes start

*******************
 4.2.3 (2026-08-31)
*******************

Features - 4.2.3
================

- Publish Windows ``arm64`` wheels. Every Windows wheel was built for ``AMD64``, so ``pip`` and ``uv`` fell back to the
  source distribution on Windows on ARM, where building the Rust extension needs a local ``cargo`` and MSVC toolchain.
  The ``cp310`` abi3 wheel and the free-threaded ``cp314t`` and ``cp315t`` wheels now ship for that platform too; PyPy
  publishes no Windows ``arm64`` interpreter, so ``pp311`` stays ``AMD64`` only. (:issue:`693`)

*******************
 4.2.2 (2026-08-26)
*******************

Bug fixes - 4.2.2
=================

- Run under an interpreter built from a git checkout. Such a build reports its version with a trailing plus
  (``3.13.5+``), which PEP 440 reads as an empty local segment and rejects, so every run stopped with ``found a `+`
  indicating the start of a local component in a version``. The trailing plus is now dropped, and a marker value that
  still fails to parse names the interpreter versions it came from. (:issue:`656`)
- Stop warning about the console-script launcher on Windows. Python puts the running ``pipdeptree.exe`` on
  ``sys.path``, and every file on the search path counted as an archive, so each run reported ``unsupported archives on
  the search path``. Only files whose suffix is ``.egg``, ``.pyz``, ``.pyzw``, ``.whl`` or ``.zip`` are now reported. (:issue:`669`)
- Replace the removed ``nab-python`` dependency with ``nab-project``. (:issue:`681`)

Packaging updates - 4.2.2
=========================

- Build the wheels for each interpreter beside each other in CI, rather than one after another in a single job, and let
  the macOS builds share one Cargo target directory. The wheel matrix used to hold a pull request for 17 minutes. (:issue:`648`)

*******************
 4.2.0 (2026-07-31)
*******************

Features - 4.2.0
================

- Publish ``cp315t`` wheels, so a free-threaded 3.15 installs a wheel instead of compiling the Rust extension. (:issue:`644`)

Bug fixes - 4.2.0
=================

- Publish Linux ``aarch64`` wheels. 4.1.0 shipped none, so ``pip`` and ``uv`` fell back to the source distribution on
  ARM64 hosts, where building the Rust extension needs a local ``cargo`` and C toolchain. (:issue:`640`)
- Build from source on a free-threaded interpreter. The package asked for the limited API unconditionally and
  meson-python refuses to pair it with a free-threaded CPython, so the source build stopped before it started. (:issue:`643`)

Packaging updates - 4.2.0
=========================

- Take the released version from the git tag rather than from a file in the tree, so a release can no longer ship
  artifacts labeled with the previous version. 4.1.1 and 4.1.2 were tagged that way and reached no index. (:issue:`647`)

Releases up to 4.1.0 are recorded on the `GitHub releases page
<https://github.com/tox-dev/pipdeptree/releases>`_.
