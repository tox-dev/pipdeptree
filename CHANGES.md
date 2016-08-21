Changelog
=========

0.7.0
-----

* Fix for a bug in reverse mode.
* Alphabetical sorting of packages in the output.
* Fallback to guess installed version of packages "skipped" by pip.

0.6.0
-----

* Better checking for possibly "confusing" dependencies, hence the
  word "confusing" in the warning message is now replaced with
  "coflicting" [PR#37]
* Fix a bug when rendering dependencies of packages [PR#38]
* The ``--nowarn`` flag is now replaced with ``--warn`` with
  'silence', 'suppress' and 'fail' as possible values, thus giving
  more control over what should happen when there are warnings. The
  default behaviour (ie. when the flag is not specified) remains the
  same.  [PR#39]
* Fixes for Python 3.5 support [PR#40]

0.5.0
-----

* Add `--reverse` flag to show the dependency tree upside down.
* Add `--packages` flag to show only select packages in output.
* Add `--json` flag to output dependency tree as json that may be used
  by external tools.


0.4.3
-----

* Add python support classifiers to setup.py
* Include license and changelog in distribution tar ball
* Removed bullets from output of pipdeptree if the `freeze` (-f) flag
  is set.
* Changes related to test setup and travis-ci integration.


0.4.2
-----

* Fix Python 3.x incompatibility (`next()` instead of `.next()`)
* Suppress error if a dep is in skipped packages

0.4.1
-----

* Fix: Show warning about cyclic deps only if found

0.4
---

* Python 2.6 compatibility
* Fix infinite recursion in case of cyclic dependencies
* Show warnings about cyclic dependencies
* Travis integration and other improvements

0.3
---

* Add `--freeze` flag
* Warn about possible confusing dependencies
* Some minor help text and README fixes

0.2
---

* Minor fixes

0.1
---

First version
