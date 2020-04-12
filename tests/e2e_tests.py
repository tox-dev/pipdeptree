import json
import os
import shlex
import subprocess

from jinja2 import Environment, BaseLoader
import pytest


## Uncomment following lines for running in shell
# os.environ['TEST_PROFILE_DIR'] = 'profiles/webapp'
# os.environ['PIPDEPTREE_EXE'] = 'profiles/webapp/.env_python3.6_pip-latest/bin/pipdeptree'


test_profile_dir = os.environ['TEST_PROFILE_DIR']
pipdeptree_path = os.environ['PIPDEPTREE_EXE']


def load_test_spec():
    test_spec_path = os.path.join(test_profile_dir, 'test_spec.json')
    with open(test_spec_path) as f:
        return json.load(f)


test_spec = load_test_spec()


def final_command(s):
    tmpl = Environment(loader=BaseLoader).from_string(s)
    return tmpl.render(pipdeptree=pipdeptree_path)


def _test_cmp_with_file_contents(spec):
    p = subprocess.Popen(shlex.split(spec['command']),
                         stdout=subprocess.PIPE,
                         stderr=subprocess.PIPE)
    out, err = p.communicate()
    if spec['expected_output_file'] is not None:
        exp_output_file = os.path.join(test_profile_dir,
                                       spec['expected_output_file'])
        with open(exp_output_file, 'rb') as f:
            expected_output = f.read()
        assert expected_output == out
    else:
        assert out == b''

    if spec['expected_err_file'] is not None:
        exp_err_file = os.path.join(test_profile_dir,
                                    spec['expected_err_file'])
        with open(exp_err_file, 'rb') as f:
            expected_err = f.read()
        assert expected_err == err
    else:
        assert err == b''


@pytest.mark.parametrize('spec', test_spec)
def test_all_tests_in_profile(spec):
    spec['command'] = final_command(spec['command'])
    if spec['method'] == 'cmp_with_file_contents':
        _test_cmp_with_file_contents(spec)
