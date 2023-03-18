# Changelog

## 2.6.0

- Handle mermaid output for a reversed tree

## 2.5.2

- Fix Mermaid not working with reserved keyword package names.

## 2.5.1

- Fix Mermaid flag.

## 2.5.0

- Implements Mermaid output.

## 2.4.0

- Make the output of the dot format deterministic and stable.

## 2.3.3

- Update README for tested Python versions.

## 2.3.2

- Generalize license.

## 2.3.1

- Use `importlib.metadata` to guess version of package before fallback to `pkg.__version__`.

## 2.3.0

- Move to a package layout
- Add support for invocation via `-m`
- Support Python 3.11
- Code now formatted via isort/black and linted via flake8
- Move readme and changelog to markdown
- Now packaged via hatchling instead of setuptools

## 2.2.1

- Fix `--user-only` and `--freeze` flags which were broken after the last release.
- Fix for compatibility with new version of `graphviz` (\>= 0.18.1).

## 2.2.0

- Fix pipdeptree to work with pip version 21.3. The \_internal pip api that was being used earlier is now replaced with
  new functions. (PR #154)

## 2.1.0

- JSON output is sorted alphabetically to make it deterministic
- Fix \--freeze option due to breaking changes in pip\'s internal api in version \> 21.1.1
- Include license file in dist package

## 2.0.0

- Support for running in the context of a virtualenv (without installing pipdeptree inside the virtualenv)
- Avoid crash when rendering cyclic dependencies
- Fix graphviz (dot file) output
- Handle a (rare) case while guessing version of a package
- Migrate from travisCI to Github workflows
- Improve integration tests

## 2.0.0b1 (beta version)

- In this first beta release targeting [2.0.0]{.title-ref}, the underlying code is heavily refactored to make different
  CLI options work well with each other. This was a serious limitation in older version [\<=1.0.0]{.title-ref} which
  made it difficult to extend the tool.

  For more information about the plans for 2.0.0 release, please check [docs/v2beta-opts.org]{.title-ref} file.

  > - The [\--reverse]{.title-ref}, [\--packages]{.title-ref} and [\--exclude]{.title-ref} flags now work with
  >   [\--json-tree]{.title-ref} and [\--graph-output]{.title-ref}
  > - Dropped support for python [3.3]{.title-ref} and added support for python [3.7]{.title-ref} and [3.8]{.title-ref}

- Another problem with older version was that tests setup was convoluted and involved loading packages pickled from one
  env into the current env (in which tests are run). Moreover there was no separation between unit tests and integration
  tests (flaky)

  > - Tests have been separated into 2 suites (1) unit tests that totally rely on mock objects and run on every commit (
  >   travis.ci) and (2) end-to-end tests that need to be run manually.
  > - The test setup for end-to-end tests has been greatly simplified although the \"flakyness\"\" still remains because
  >   these tests are run against unpinned versions of [pip]{.title-ref}. However this is by design because we want to
  >   know when [pipdeptree]{.title-ref} fails with a new version of [pip]{.title-ref}.

- Move continuous integration from Travis to Github Actions.

## 1.0.0

- Use [pkg_resources]{.title-ref} vendored with [pip]{.title-ref}.
- Besides this, there\'s no other change in this major version release.

## 0.13.2

- Fixed call to [FrozenRequirement.to_dist]{.title-ref} to handle changes to the internal api of pip version 19.0. The
  api change is because dependency links support has been removed in pip 19.0

  See more:

  - <https://github.com/pypa/pip/pull/6060>
  - <https://github.com/pypa/pip/pull/5881/commits/46ffb13f13f69c509fd253329da49889008f8e23>

## 0.13.1

- Fixed import after changes in pip.\_internal introduced in pip version 18.1

## 0.13.0

- Added [\--exclude]{.title-ref} option to exclude packages specified as CSV
- In case of multiple version specs eg. \<x,\>=y, fix the order to ensure consistent output. The sorting is naive - puts
  the \'\>\' prior to \'\<\', and \'!\'.
- \[Developer affecting\] Updated dependencies in test environments, thereby fixing the long standing issue of
  inconsistent test behaviour.

## 0.12.1

- Fix import of \'FrozenRequirement\' for pip 10.0.0

## 0.12.0

- Changes to make pipdeptree work with pip 10.0.0. This change is backward compatible.

## 0.11.0

- Added support for nested json output ([\--json-tree]{.title-ref} flag). Behaviour of [\--json]{.title-ref} stays the
  same.
- Test environments have been updated to fix the builds.

## 0.10.1

- Fixed change of behaviour due to support for `--json` and `--packages` together. PR #65 was reverted for this.

## 0.10.0

- Dropped support for Python 2.6.
- `--json` and `--packages` options can now be used together.
- Fixed binary graphviz output on Python 3

## 0.9.0

- Support for visualizing dependency tree of packages using Graphviz in various formats.
- Support to consider only packages installed in the user directory.
- Fix the output to use a better term, \"Any\" instead of \"None\" if a dependency doesn\'t need to be of a specific
  version.
- CLI option to print version.

## 0.8.0

- Use pip\'s list of excluded default packages. This means that the `pipdeptree` package itself is no longer excluded
  and will appear in the output tree.
- Fix the bug that caused a package to appear in conflicting deps although it\'s installed version could be guessed.

## 0.7.0

- Fix for a bug in reverse mode.
- Alphabetical sorting of packages in the output.
- Fallback to guess installed version of packages \"skipped\" by pip.

## 0.6.0

- Better checking for possibly \"confusing\" dependencies, hence the word \"confusing\" in the warning message is now
  replaced with \"coflicting\" \[PR#37\]
- Fix a bug when rendering dependencies of packages \[PR#38\]
- The `--nowarn` flag is now replaced with `--warn` with \'silence\', \'suppress\' and \'fail\' as possible values, thus
  giving more control over what should happen when there are warnings. The default behaviour (ie. when the flag is not
  specified) remains the same. \[PR#39\]
- Fixes for Python 3.5 support \[PR#40\]

## 0.5.0

- Add [\--reverse]{.title-ref} flag to show the dependency tree upside down.
- Add [\--packages]{.title-ref} flag to show only select packages in output.
- Add [\--json]{.title-ref} flag to output dependency tree as json that may be used by external tools.

## 0.4.3

- Add python support classifiers to setup.py
- Include license and changelog in distribution tar ball
- Removed bullets from output of pipdeptree if the [freeze]{.title-ref} (-f) flag is set.
- Changes related to test setup and travis-ci integration.

## 0.4.2

- Fix Python 3.x incompatibility ([next()]{.title-ref} instead of [.next()]{.title-ref})
- Suppress error if a dep is in skipped packages

## 0.4.1

- Fix: Show warning about cyclic deps only if found

## 0.4

- Python 2.6 compatibility
- Fix infinite recursion in case of cyclic dependencies
- Show warnings about cyclic dependencies
- Travis integration and other improvements

## 0.3

- Add [\--freeze]{.title-ref} flag
- Warn about possible confusing dependencies
- Some minor help text and README fixes

## 0.2

- Minor fixes

## 0.1

First version
