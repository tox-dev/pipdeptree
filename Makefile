
clean:
	find . -name '*.pyc' -exec rm -f {} +
	find . -name '*.pyo' -exec rm -f {} +
	find . -name '*~' -exec rm -f {} +
	find . -name '__pycache__' -exec rmdir {} +

clean-env:
	rm -rf tests/virtualenvs/{testenv,cyclicenv,unsatisfiedenv}
	rm tests/virtualenvs/*.pickle

test-env:
	cd tests/virtualenvs; make testenv cyclicenv unsatisfiedenv

test: test-env
	tox -e py27

test-tox: test-env
	tox
