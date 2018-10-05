#!/usr/bin/env python

# This is a small tool to create a pickle file for a set of packages for the
# purposes of writing tests

import pickle
import pkg_resources
import sys


def main():
    skip = {'setuptools', 'pip', 'python', 'distribute', 'pipdeptree'}
    pkgs = [p for p in pkg_resources.working_set if str(p) not in skip]
    pickle.dump(pkgs, sys.stdout)


if __name__ == '__main__':
    main()
