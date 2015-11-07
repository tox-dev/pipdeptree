from __future__ import print_function
import sys
from itertools import chain, tee
from collections import defaultdict
import argparse

import pip


__version__ = '0.4.3'


flatten = chain.from_iterable


def _peek_into(iterator):
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
    

class pipdeptree(object):
    """Object that contains all methods necessary
    
    """
    
    DEFAULT_SKIP = ['setuptools', 'pip', 'python', 'distribute']
    # List of packages to skip when importing package info from pip
    SKIP = DEFAULT_SKIP + ['pipdeptree']
    
    
    def __init__(self, local_only=True, pkgs=None):
        """Initiated object, builds pkg_index and req_map
        
        :param bool local_only: If in a virtualenv that has global access,
                                do not show globally installed packages
        
        """
        
        if pkgs:
            self.pkgs = pkgs
        else:
            self.pkgs = pip.get_installed_distributions(local_only=local_only,
                                                        skip=self.SKIP)
        """List of packages imported from pip.
        
        {pkg_resources.Distribution, ...]
        
        """
        self.pkg_index = dict((p.key, p) for p in self.pkgs)
        """Map of package key to it's package object.
        
        {pkg_key: pkg_resources.Distribution, ...}
        
        """
        self.req_map = dict((p.key, [req.key for req in p.requires()]) for p in self.pkgs)
        """Map of package key to it's dependency keys.
        
        {pkg_key: [req_key, ...], ...}
        
        """
        parent_map = defaultdict(list)
        for pkg_key, req_keys in self.req_map.items():
            for req_key in req_keys:
                parent_map[req_key].append(pkg_key)
        self.parent_map = parent_map
        """Map of dependency key to it's parent package keys.
        
        {req_key: [pkg_key, ...], ...}
        
        """
        
        
    def cyclic_deps(self):
        """Generator that produces cyclic dependencies

        :returns: generator that yields str representation of cyclic
                  dependencies
        :rtype: generator

        """
        
        def aux(pkg, chain):
            if pkg.key in self.pkg_index:
                for d in self.pkg_index[pkg.key].requires():
                    if d.project_name in chain:
                        yield ' => '.join([str(p) for p in chain] + [str(d)])
                    else:
                        for cycle in aux(d, chain=chain+[d.project_name]):
                            yield cycle

        for cycle in flatten([aux(p, chain=[]) for p in self.pkgs]):
            yield cycle
        
        
    def build_ver_str(self, pkg_name, vers):
        """Builds the version string from a package name and dictionary of versions.
        
        Called by non_top_pkg_name and non_bottom_pkg_name.
        
        :param string pkg_name: Name of package
        :param dict vers: Dictionary to append in {key: value,...] format
        :returns: the package name and version(s)
        :rtype: string
        
        """
        
        if not vers:
            return req.key
        ver_str = ', '.join(['{0}: {1}'.format(k, v) for k, v in vers])
        return '{0} [{1}]'.format(pkg_name, ver_str)
    
    
    def get_requirement_instance(self, pkg_key, req_key):
        """ Returns the requirement instance a package has for the dependency
        specified by req_key
        
        :param string pkg_key: Key of the package
        :param string req_key: Key of the dependency
        
        """
        
        for req_inst in self.pkg_index[pkg_key].requires():
            if req_inst.key == req_key:
                return req_inst


    def req_version(self, req):
        """Builds the version string for the requirement instance

        :param req: requirement object
        :returns: the version in desired format
        :rtype: string or NoneType

        """
        
        return ''.join(req.specs[0]) if req.specs else None
    
    
    def top_pkg_name(self, pkg_key):
        """Builds the package name for top level package

        This just prints the name and the version of the package which may
        not necessarily match with the output of `pip freeze` which also
        includes info such as VCS source for editable packages

        :param string pkg_key: The package key to return formatted
        :returns: the package name and version in the desired format
        :rtype: string

        """
        
        pkg = self.pkg_index[pkg_key]
        return '{0}=={1}'.format(pkg.project_name, pkg.version)
    
    
    def non_top_pkg_name(self, pkg_key, parent_key):
        """Builds the package name for a non-top level package

        For the dependencies of the top level packages, the installed
        version as well as the version required by it's parent package
        will be specified (if applicable) with it's name

        :param string pkg_key: The package key to return formatted
        :param string parent_key: The key of the package that requires by pkg_key
        :returns: the package name and version in the desired format
        :rtype: string

        """
        
        pkg = self.pkg_index[pkg_key]
        vers = []
        parent_req = self.get_requirement_instance(parent_key, pkg_key)
        parent_req_ver = self.req_version(parent_req)
        if parent_req_ver:
            vers.append(('required', parent_req_ver))
        if pkg:
            vers.append(('installed', pkg.version))
        return self.build_ver_str(pkg.project_name, vers)
    
    
    def non_bottom_pkg_name(self, pkg_key, child_key):
        """*(reverse mode)* Builds the package name for a non-bottom level package

        For the dependents of the bottom level packages, the name and version
        installed will be listed along with a requirement for the specified dependency
        (if applicable)

        :param string pkg_key: Package key
        :param string child_key: The key of the package that is required by pkg_key
        :returns: the package name and version in the desired format
        :rtype: string

        """
        
        pkg = self.pkg_index[pkg_key]
        vers = []
        pkg_req = self.get_requirement_instance(pkg_key, child_key)
        pkg_req_ver = self.req_version(pkg_req)
        if pkg:
            vers.append(('installed', pkg.version))
        if pkg_req_ver:
            vers.append(('requires', pkg_req))
        return self.build_ver_str(pkg.project_name, vers)


    def top_pkg_src(self, pkg_key):
        """Returns the frozen package name

        The may or may not be the same as the package name.

        :param string pkg_key: Package key
        :returns: frozen name of the package
        :rtype: string

        """
        
        pkg = self.pkg_index[pkg_key]
        return str(pip.FrozenRequirement.from_dist(pkg, [])).strip()


    def non_top_pkg_src(self, pkg_key, _req_key):
        """Returns frozen package name for non top level package

        :param string pkg_key: Package key
        :param string _red_key: Requirement key (not used)
        :returns: frozen name of the package
        :rtype: string

        """
        
        return self.top_pkg_src(pkg_key)


    def non_bottom_pkg_src(self, pkg_key, _req_key):
        """*(reverse mode)* Returns frozen package name for non bottom level package

        :param pkg: pkg_resources.Distribution
        :param _req_pkg: pkg_resources.Distribution
        :returns: frozen name of the package
        :rtype: string

        """
        
        return self.top_pkg_src(pkg_key)


    def has_multi_versions(self, reqs):
        """Returns True if reqs contains different version specifications"

        :param reqs: pkg_resources.Distribution
        :param _req_pkg: pkg_resources.Distribution
        :returns: frozen name of the package
        :rtype: string

        """
        
        vers = (self.req_version(r) for r in reqs)
        return len(set(vers)) > 1
    
    
    def confusing_deps(self):
        """Returns group of dependencies that are possibly confusing

        eg. if pkg1 requires pkg3>=1.0 and pkg2 requires pkg3>=1.0,<=2.0

        :returns: groups of dependencies paired with their top level pkgs
        :rtype: list of list of pairs

        """
        
        confusing = []
        for req_key, pkg_keys in self.parent_map.items():
            if self.has_multi_versions([self.get_requirement_instance(pkg_key, req_key) for pkg_key in pkg_keys]):
                confusing.append([(pkg_key, req_key) for pkg_key in pkg_keys])
        return confusing
    
    
    def render_tree(self, list_all=False, bullets=True, reverse=False):
        """Renders a package dependency tree as a string

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
        
        if bullets:
            top_pkg_str = getattr(self, 'top_pkg_name')
            non_top_pkg_str = getattr(self, 'non_top_pkg_name')
            non_bottom_pkg_str = getattr(self, 'non_bottom_pkg_name')
        else:
            top_pkg_str = getattr(self, 'top_pkg_src')
            non_top_pkg_str = getattr(self, 'non_top_pkg_src')
            non_bottom_pkg_str = getattr(self, 'non_bottom_pkg_src')
            
        if reverse:
            non_top_pkg_str = non_bottom_pkg_str
            top = [k for k, r in self.req_map.items() if r == []]
            map = self.parent_map
        else:
            non_top = set(r for r in flatten(self.req_map.values()))
            top = [p for p in self.pkg_index if p not in non_top]
            map = self.req_map
        
        
        def aux(pkg_key, indent=0, chain=None, reverse=False):
            if chain is None:
                chain = [pkg_key]

            if indent > 0:
                try:
                    dist = self.pkg_index[pkg_key]
                    name = non_top_pkg_str(pkg_key, chain[-2])
                except KeyError:
                    # FixMe! Some dependencies are not present in the result of
                    # `pip.get_installed_distributions`
                    # eg. `testresources`. This is a hack around it.
                    name = pkg_key
                result = [' '*indent + ('-' if bullets else ' ') + ' ' + name]
            else:
                result = [top_pkg_str(pkg_key)]

            # FixMe! in case of some pkg not present in list of all
            # packages, eg. `testresources`, this will fail
            if pkg_key in self.pkg_index:
                filtered_deps = [
                    aux(d, indent=indent+2, chain=chain+[d])
                    for d in map[pkg_key]
                    if d not in chain]
                result += list(flatten(filtered_deps))
            return result
        
        lines = flatten([aux(p) for p in sorted(self.pkg_index if list_all else top)])
        return '\n'.join(lines)


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

    pdt = pipdeptree(local_only=args.local_only)
    # show warnings about possibly confusing deps if found and
    # warnings are enabled
    if not args.nowarn:
        confusing = pdt.confusing_deps()
        if confusing:
            print('Warning!!! Possible confusing dependencies found:', file=sys.stderr)
            for xs in confusing:
                for i, (p, d) in enumerate(xs):
                    if d in pdt.SKIP:
                        continue
                    pkg = pdt.top_pkg_name(p)
                    req = pdt.non_top_pkg_name(d, p)
                    tmpl = '  {0} -> {1}' if i > 0 else '* {0} -> {1}'
                    print(tmpl.format(pkg, req), file=sys.stderr)
            print('-'*72, file=sys.stderr)
        
        cyclic_generator = pdt.cyclic_deps()
        is_empty, cyclic = _peek_into(cyclic_generator)
        if not is_empty:
            print('Warning!!! Cyclic dependencies found:', file=sys.stderr)
            for xs in cyclic:
                print('- {0}'.format(xs), file=sys.stderr)
            print('-'*72, file=sys.stderr)
    
    tree = pdt.render_tree(list_all=args.all,
                           bullets=not args.freeze,
                           reverse=args.reverse)
    print(tree)
    return 0


if __name__ == '__main__':
    sys.exit(main())
