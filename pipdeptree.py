import sys
from itertools import chain
import argparse

import pip


flatten = chain.from_iterable


def req_version(req):
    """Builds the version string for the requirement instance

    :param req : representing requirement
    :rtype     : string or NoneType

    """
    return ''.join(req.specs[0]) if req.specs else None


def top_pkg_name(pkg):
    """Builds the package name for top level package

    The format is the same that's used by `pip freeze`

    :param pkg : pkg_resources.Distribution
    :rtype     : string

    """
    return '{}=={}'.format(pkg.project_name, pkg.version)


def non_top_pkg_name(req, pkg):
    """Builds the package name for a non-top level package

    For the dependencies of the top level packages, the installed
    version as well as the version required by it's parent package
    will be specified with it's name

    :param req : requirements instance
    :param pkg : pkg_resources.Distribution
    :rtype     : string

    """
    vers = []
    req_ver = req_version(req)
    if req_ver:
        vers.append(('required', req_ver))
    if pkg:
        vers.append(('installed', pkg.version))
    if not vers:
        return req.key
    ver_str = ', '.join(['{}: {}'.format(k, v) for k, v in vers])
    return '{} [{}]'.format(pkg.project_name, ver_str)


def render_tree(pkgs, list_all):
    """Renders a package dependency tree

    :param pkgs     : list of pkg_resources.Distribution
    :param list_all : boolean
    :rtype          : string

    """
    pkg_index = {p.key: p for p in pkgs}
    non_top = set(flatten((x.key for x in p.requires())
                          for p in pkgs))
    top = [p for p in pkgs if p.key not in non_top]
    def aux(pkg, indent=0):
        if indent > 0:
            result = [' '*indent +
                      '- ' +
                      non_top_pkg_name(pkg, pkg_index.get(pkg.key))]
        else:
            result = [top_pkg_name(pkg)]
        if pkg.key in pkg_index:
            pkg_deps = pkg_index[pkg.key].requires()
            result += list(flatten([aux(d, indent=indent+2)
                                    for d in pkg_deps]))
        return result
    lines = flatten([aux(p) for p in (pkgs if list_all else top)])
    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser(description='Dependency tree of the installed python packages')
    parser.add_argument('-a', '--all', action='store_true', help='list all deps at top level')
    parser.add_argument('-l', '--local-only',
                        action='store_true', help=(
                            'list only the installations local to the '
                            'current virtualenv, if in a virtualenv'
                        ))
    args = parser.parse_args()
    default_skip = ['setuptools', 'pip', 'python', 'distribute']
    packages = pip.get_installed_distributions(local_only=args.local_only,
                                               skip=default_skip+['pipdeptree'])
    print(render_tree(packages, list_all=args.all))
    return 0


if __name__ == '__main__':
    sys.exit(main())
