

testenv:
	virtualenv testenv
	testenv/bin/pip install -U pip setuptools
	testenv/bin/pip install -r testenv_requirements.txt
	testenv/bin/python pickle_env.py > testenv.pickle


cyclicenv:
	virtualenv cyclicenv
	cyclicenv/bin/pip install -U pip setuptools
	cyclicenv/bin/pip install -r cyclicenv_requirements.txt
	cyclicenv/bin/python pickle_env.py > cyclicenv.pickle
