from __future__ import print_function
import sys
from itertools import chain, tee
from collections import defaultdict
import argparse

import pip


__version__ = '0.4.3'


flatten = chain.from_iterable


def req_version(req):
    """Builds the version string for the requirement instance

    :param req: requirement object
    :returns: the version in desired format
    :rtype: string or NoneType

    """
    return ''.join(req.specs[0]) if req.specs else None


def top_pkg_name(pkg):
    """Builds the package name for top level package

    This just prints the name and the version of the package which may
    not necessarily match with the output of `pip freeze` which also
    includes info such as VCS source for editable packages

    :param pkg: pkg_resources.Distribution
    :returns: the package name and version in the desired format
    :rtype: string

    """
    return '{0}=={1}'.format(pkg.project_name, pkg.version)


def non_top_pkg_name(req, pkg):
    """Builds the package name for a non-top level package

    For the dependencies of the top level packages, the installed
    version as well as the version required by it's parent package
    will be specified with it's name

    :param req: requirements instance
    :param pkg: pkg_resources.Distribution
    :returns: the package name and version in the desired format
    :rtype: string

    """
    vers = []
    req_ver = req_version(req)
    if req_ver:
        vers.append(('required', req_ver))
    if pkg:
        vers.append(('installed', pkg.version))
    if not vers:
        return req.key
    ver_str = ', '.join(['{0}: {1}'.format(k, v) for k, v in vers])
    return '{0} [{1}]'.format(pkg.project_name, ver_str)


def non_bottom_pkg_name(pkg, req_key):
    """*(reverse mode)* Builds the package name for a non-bottom level package

    For the dependents of the bottom level packages, the name and version installed
    will be listed along with a requirement for the specified dependency

    :param pkg: pkg_resources.Distribution
    :param req_pkg: pkg_resources.Distribution
    :returns: the package name, version and dependency requirement in the desired format
    :rtype: string

    """
    for r in pkg.requires():
        if r.key == req_key:
            return '{0} [requires: {1}]'.format(top_pkg_name(pkg), r)


def top_pkg_src(pkg):
    """Returns the frozen package name

    The may or may not be the same as the package name.

    :param pkg: pkg_resources.Distribution
    :returns: frozen name of the package
    :rtype: string

    """
    return str(pip.FrozenRequirement.from_dist(pkg, [])).strip()


def non_top_pkg_src(_req, pkg):
    """Returns frozen package name for non top level package

    :param _req: the requirements instance
    :param pkg: pkg_resources.Distribution
    :returns: frozen name of the package
    :rtype: string

    """
    return top_pkg_src(pkg)


def non_bottom_pkg_src(pkg, _req_pkg):
    """*(reverse mode)* Returns frozen package name for non bottom level package

    :param pkg: pkg_resources.Distribution
    :param _req_pkg: pkg_resources.Distribution
    :returns: frozen name of the package
    :rtype: string

    """
    return top_pkg_src(pkg)


def has_multi_versions(reqs):
    vers = (req_version(r) for r in reqs)
    return len(set(vers)) > 1


def confusing_deps(req_map):
    """Returns group of dependencies that are possibly confusing

    eg. if pkg1 requires pkg3>=1.0 and pkg2 requires pkg3>=1.0,<=2.0

    :param dict req_map: mapping of pkgs with the list of their deps
    :returns: groups of dependencies paired with their top level pkgs
    :rtype: list of list of pairs

    """
    deps = defaultdict(list)
    for p, rs in req_map.items():
        for r in rs:
            deps[r.key].append((p, r))
    return [ps for r, ps in deps.items()
            if len(ps) > 1
            and has_multi_versions(d for p, d in ps)]


def render_tree(pkgs, pkg_index, req_map,
                list_all=False,
                top_pkg_str=top_pkg_name,
                non_top_pkg_str=non_top_pkg_name,
                non_bottom_pkg_str=non_bottom_pkg_name,
                bullets=True,
                reverse=False):
    """Renders a package dependency tree as a string

    :param list pkgs: pkg_resources.Distribution instances
    :param dict pkg_index: mapping of pkgs with their respective keys
    :param dict req_map: mapping of pkgs with the list of their deps
    :param bool list_all: whether to show globally installed pkgs
                          if inside a virtualenv with global access
    :param function top_pkg_str: function to render a top level
                                 package as string
    :param function non_top_pkg_str: function to render a non-top
                                     level package as string
    :param bool bullets: whether or not to show bullets for child
                         dependencies [default: True]
    :param bool reverse: reverse dependency tree to show which packages
                         depend on bottom-level dependencies
    :returns: dependency tree encoded as string
    :rtype: str

    """
    if not reverse:
        non_top = set(r.key for r in flatten(req_map.values()))
        top = [p for p in pkgs if p.key not in non_top]
    else:
        top = [k for k, r in req_map.items() if r == []]
        parents = defaultdict(list)
        for p, rs in req_map.items():
            for r in rs:
                parents[r.key].append(p)

    def aux(pkg, indent=0, chain=None, reverse=False):
        if chain is None:
            chain = [pkg.project_name]

        # In this function, pkg can either be a Distribution or
        # Requirement instance
        if indent > 0:
            if not reverse:
                # this is definitely a Requirement (due to positive
                # indent) so we need to find the Distribution instance for
                # it from the pkg_index
                dist = pkg_index.get(pkg.key)
                string_generator = non_top_pkg_str          
            else:
                # to find requirement in reverse, need to know it's name
                # which is already held in the chain list
                dist = chain[-2].lower()
                string_generator = non_bottom_pkg_str

            # FixMe! Some dependencies are not present in the result of
            # `pip.get_installed_distributions`
            # eg. `testresources`. This is a hack around it.
            name = pkg.project_name if dist is None else string_generator(pkg, dist)
            result = [' '*indent + ('-' if bullets else ' ') + ' ' + name]
        else:
            result = [top_pkg_str(pkg)]

        # FixMe! in case of some pkg not present in list of all
        # packages, eg. `testresources`, this will fail
        if pkg.key in pkg_index:
            pkg_deps = pkg_index[pkg.key].requires() if not reverse else parents[pkg.key]
            filtered_deps = [
                aux(d, indent=indent+2, chain=chain+[d.project_name], reverse=reverse)
                for d in pkg_deps
                if d.project_name not in chain]
            result += list(flatten(filtered_deps))
        return result

    lines = flatten([aux(p, reverse=reverse) for p in (pkgs if list_all else top)])
    return '\n'.join(lines)


def cyclic_deps(pkgs, pkg_index):
    """Generator that produces cyclic dependencies

    :param list pkgs: pkg_resources.Distribution instances
    :param dict pkg_index: mapping of pkgs with their respective keys
    :returns: generator that yields str representation of cyclic
              dependencies
    :rtype: generator

    """
    def aux(pkg, chain):
        if pkg.key in pkg_index:
            for d in pkg_index[pkg.key].requires():
                if d.project_name in chain:
                    yield ' => '.join([str(p) for p in chain] + [str(d)])
                else:
                    for cycle in aux(d, chain=chain+[d.project_name]):
                        yield cycle

    for cycle in flatten([aux(p, chain=[]) for p in pkgs]):
        yield cycle


def peek_into(iterator):
    """Peeks into an iterator to check if it's empty

    :param iterator: an iterator
    :returns: tuple of boolean representing whether the iterator is
              empty or not and the iterator itself.
    :rtype: tuple

    """
    a, b = tee(iterator)
    is_empty = False
    try:
        next(a)
    except StopIteration:
        is_empty = True
    return is_empty, b


def main():
    parser = argparse.ArgumentParser(description=(
        'Dependency tree of the installed python packages'
    ))
    parser.add_argument('-f', '--freeze', action='store_true',
                        help='Print names so as to write freeze files')
    parser.add_argument('-a', '--all', action='store_true',
                        help='list all deps at top level')
    parser.add_argument('-l', '--local-only',
                        action='store_true', help=(
                            'If in a virtualenv that has global access '
                            'donot show globally installed packages'
                        ))
    parser.add_argument('-w', '--nowarn', action='store_true',
                        help=(
                            'Inhibit warnings about possibly '
                            'confusing packages'
                        ))
    parser.add_argument('-r', '--reverse', action='store_true',
                        help=(
                            'reverse dependency tree to show which '
                            'packages depend on bottom-level dependencies'
                        ))
    args = parser.parse_args()

    default_skip = ['setuptools', 'pip', 'python', 'distribute']
    skip = default_skip + ['pipdeptree']
    pkgs = pip.get_installed_distributions(local_only=args.local_only,
                                           skip=skip)

    pkg_index = dict((p.key, p) for p in pkgs)
    req_map = dict((p, p.requires()) for p in pkgs)

    # show warnings about possibly confusing deps if found and
    # warnings are enabled
    if not args.nowarn:
        confusing = confusing_deps(req_map)
        if confusing:
            print('Warning!!! Possible confusing dependencies found:', file=sys.stderr)
            for xs in confusing:
                for i, (p, d) in enumerate(xs):
                    if d.key in skip:
                        continue
                    pkg = top_pkg_name(p)
                    req = non_top_pkg_name(d, pkg_index[d.key])
                    tmpl = '  {0} -> {1}' if i > 0 else '* {0} -> {1}'
                    print(tmpl.format(pkg, req), file=sys.stderr)
            print('-'*72, file=sys.stderr)

        is_empty, cyclic = peek_into(cyclic_deps(pkgs, pkg_index))
        if not is_empty:
            print('Warning!!! Cyclic dependencies found:', file=sys.stderr)
            for xs in cyclic:
                print('- {0}'.format(xs), file=sys.stderr)
            print('-'*72, file=sys.stderr)

    if args.freeze:
        top_pkg_str, non_top_pkg_str, non_bottom_pkg_str = top_pkg_src, non_top_pkg_src, non_bottom_pkg_src
    else:
        top_pkg_str, non_top_pkg_str, non_bottom_pkg_str = top_pkg_name, non_top_pkg_name, non_bottom_pkg_name

    tree = render_tree(pkgs,
                       pkg_index=pkg_index,
                       req_map=req_map,
                       list_all=args.all,
                       top_pkg_str=top_pkg_str,
                       non_top_pkg_str=non_top_pkg_str,
                       non_bottom_pkg_str=non_bottom_pkg_str,
                       bullets=not args.freeze,
                       reverse=args.reverse
                       )
    print(tree)
    return 0


if __name__ == '__main__':
    sys.exit(main())
