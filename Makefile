
clean:
	find . -name '*.pyc' -exec rm -f {} +
	find . -name '*.pyo' -exec rm -f {} +
	find . -name '*~' -exec rm -f {} +
	find . -name '__pycache__' -exec rm -rf {} +
	rm -rf htmlcov .tox

clean-env:
	cd tests/virtualenvs && make clean

test-env:
	cd tests/virtualenvs && make

test: test-env
	tox -e py27

test-tox: test-env
	tox

.PHONY: clean clean-env test test-env test-tox
