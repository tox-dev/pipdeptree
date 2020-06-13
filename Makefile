.PHONY: clean test-env test test-cov test-tox-all test-e2e

TOX_ENV ?= py36

E2E_PYTHON_EXE ?= python3.6

clean:
	find . -name '*.pyc' -exec rm -f {} +
	find . -name '*.pyo' -exec rm -f {} +
	find . -name '*~' -exec rm -f {} +
	find . -name '__pycache__' -exec rmdir {} +

test-env:
	pip install -r dev-requirements.txt

test:
	tox -e $(TOX_ENV)

test-cov:
	tox -e $(TOX_ENV) -- -x -vv --cov=pipdeptree --cov-report=xml --cov-report=html --cov-report=term-missing

# Requires all the versions of python executables to be present (See
# tox.ini for list of python versions)
test-tox-all:
	tox

test-e2e:
	rm -rf tests/profiles/*/.env_$(E2E_PYTHON_EXE)*
	cd tests && ./e2e-tests webapp
	cd tests && ./e2e-tests conflicting
	cd tests && ./e2e-tests cyclic

test-e2e-quick:
	cd tests && ./e2e-tests webapp
	cd tests && ./e2e-tests conflicting
	cd tests && ./e2e-tests cyclic
