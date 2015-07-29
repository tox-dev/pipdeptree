
clean:
	find . -name '*.pyc' -exec rm -f {} +
	find . -name '*.pyo' -exec rm -f {} +
	find . -name '*~' -exec rm -f {} +

clean-env:
	rm -rf tests/virtualenvs/{testenv,cyclicenv}
	rm tests/virtualenvs/*.pickle

test-env:
	cd tests/virtualenvs; make testenv cyclicenv

test: test-env
	tox -e py27

test-tox: test-env
	tox
