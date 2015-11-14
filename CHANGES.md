Changelog
=========

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
