#!/usr/bin/env python

# This is a small tool to create a pickle file for a set of packages for the
# purposes of writing tests

import pickle
import sys

import pip


def main():
    default_skip = ['setuptools', 'pip', 'python', 'distribute']
    skip = default_skip + ['pipdeptree']
    pkgs = pip.get_installed_distributions(local_only=True, skip=skip)
    pickle.dump(pkgs, sys.stdout)
    return 0


if __name__ == '__main__':
    sys.exit(main())
