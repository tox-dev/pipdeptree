

testenv:
	virtualenv --python=python2.7 testenv
	testenv/bin/pip install -U pip setuptools
	testenv/bin/pip install -r testenv_requirements.txt
	testenv/bin/python pickle_env.py > testenv.pickle


cyclicenv:
	virtualenv --python=python2.7 cyclicenv
	cyclicenv/bin/pip install -U pip setuptools
	cyclicenv/bin/pip install -r cyclicenv_requirements.txt
	cyclicenv/bin/python pickle_env.py > cyclicenv.pickle

unsatisfiedenv:
	virtualenv --python=python2.7 unsatisfiedenv
	unsatisfiedenv/bin/pip install -U pip setuptools
	unsatisfiedenv/bin/pip install -r unsatisfiedenv_requirements.txt
	# test case where simplejson is required but not installed
	unsatisfiedenv/bin/pip install uritemplate==0.6 --no-dependencies
	unsatisfiedenv/bin/python pickle_env.py > unsatisfiedenv.pickle
