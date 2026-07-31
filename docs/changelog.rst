###########
 Changelog
###########

.. towncrier-draft-entries:: Unreleased

.. towncrier release notes start

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
