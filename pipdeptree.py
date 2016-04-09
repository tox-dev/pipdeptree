from __future__ import print_function
import sys
from itertools import chain, tee
from collections import defaultdict
import argparse
import json

import pip
import pkg_resources


__version__ = '0.6.0'


flatten = chain.from_iterable


def build_dist_index(pkgs):
    """Build an index pkgs by their key as a dict.

    :param list pkgs: list of pkg_resources.Distribution instances
    :returns: index of the pkgs by the pkg key
    :rtype: dict

    """
    return dict((p.key, DistPackage(p)) for p in pkgs)


def construct_tree(index):
    """Construct tree representation of the pkgs from the index.

    The keys of the dict representing the tree will be objects of type
    DistPackage and the values will be list of ReqPackage objects.

    :param dict index: dist index ie. index of pkgs by their keys
    :returns: tree of pkgs and their dependencies
    :rtype: dict

    """
    return dict((p, [ReqPackage(r, index.get(r.key))
                     for r in p.requires()])
                for p in index.values())


def reverse_tree(tree):
    """Reverse the dependency tree.

    ie. the keys of the resulting dict are objects of type
    ReqPackage and the values are lists of DistPackage objects.

    :param dict tree: the pkg dependency tree obtained by calling
                      `construct_tree` function
    :returns: reversed tree
    :rtype: dict

    """
    rtree = {}
    visited = set()
    child_keys = set(c.key for c in flatten(tree.values()))
    for k, vs in tree.items():
        for v in vs:
            if v not in rtree:
                rtree[v] = []
            rtree[v].append(k)
            visited.add(v.key)
        if k.key not in child_keys:
            rtree[k.as_requirement()] = []
    return rtree


class Package(object):
    """Abstract class for wrappers around objects that pip returns.

    This class needs to be subclassed with implementations for
    `render_as_root` and `render_as_branch` methods.

    """

    def __init__(self, obj):
        self._obj = obj
        self.project_name = obj.project_name
        self.key = obj.key
        # an instance of every subclass of Package will have a
        # DistPackage object associated with it. In case of
        # DistPackage class, it will be the object itself.
        self.dist = None

    def render_as_root(self, frozen):
        return NotImplementedError

    def render_as_branch(self, parent, frozen):
        return NotImplementedError

    def render(self, parent=None, frozen=False):
        if not parent:
            return self.render_as_root(frozen)
        else:
            return self.render_as_branch(parent, frozen)

    def frozen_repr(self):
        if self.dist:
            fr = pip.FrozenRequirement.from_dist(self.dist._obj, [])
            return str(fr).strip()
        else:
            return self.project_name

    def __getattr__(self, key):
        return getattr(self._obj, key)

    def __repr__(self):
        return '<{0}("{1}")>'.format(self.__class__.__name__, self.key)


class DistPackage(Package):
    """Wrapper class for pkg_resources.Distribution instances"""

    def __init__(self, obj):
        super(DistPackage, self).__init__(obj)
        # this itself is the associated dist package obj
        self.dist = self
        self.version_spec = None

    def render_as_root(self, frozen):
        if not frozen:
            return '{0}=={1}'.format(self.project_name, self.version)
        else:
            return self.frozen_repr()

    def render_as_branch(self, parent, frozen):
        if not frozen:
            parent_ver_spec = parent.version_spec
            parent_str = parent.project_name
            if parent_ver_spec:
                parent_str += parent_ver_spec
            return (
                '{0}=={1} [requires: {2}]'
            ).format(self.project_name, self.version, parent_str)
        else:
            return self.render_as_root(frozen)

    def as_requirement(self):
        return ReqPackage(self._obj.as_requirement(), dist=self)

    def as_dict(self):
        return {'key': self.key,
                'package_name': self.project_name,
                'installed_version': self.version}


class ReqPackage(Package):
    """Wrapper class for Requirements instance"""

    def __init__(self, obj, dist=None):
        super(ReqPackage, self).__init__(obj)
        self.dist = dist

    @property
    def version_spec(self):
        specs = self._obj.specs
        return ','.join([''.join(sp) for sp in specs]) if specs else None

    @property
    def installed_version(self):
        # if the dist is None as in some cases, we don't know the
        # installed version
        return self.dist.version if self.dist else '?'

    def render_as_root(self, frozen):
        if not frozen:
            return '{0}=={1}'.format(self.project_name, self.installed_version)
        else:
            return self.frozen_repr()

    def render_as_branch(self, _parent, frozen):
        if not frozen:
            vers = []
            if self.version_spec:
                vers.append(('required', self.version_spec))
            if self.dist:
                vers.append(('installed', self.installed_version))
            if not vers:
                return self.key
            ver_str = ', '.join(['{0}: {1}'.format(k, v) for k, v in vers])
            return '{0} [{1}]'.format(self.project_name, ver_str)
        else:
            return self.render_as_root(frozen)

    def as_dict(self):
        return {'key': self.key,
                'package_name': self.project_name,
                'installed_version': self.installed_version,
                'required_version': self.version_spec}


def render_tree(tree, list_all=True, show_only=None, frozen=False):
    """Convert to tree to string representation

    :param dict tree: the package tree
    :param bool list_all: whether to list all the pgks at the root
                          level or only those that are the
                          sub-dependencies
    :param set show_only: set of select packages to be shown in the
                          output. This is optional arg, default: None.
    :param bool frozen: whether or not show the names of the pkgs in
                        the output that's favourable to pip --freeze
    :returns: string representation of the tree
    :rtype: str

    """
    branch_keys = set(r.key for r in flatten(tree.values()))
    nodes = tree.keys()
    use_bullets = not frozen

    key_tree = dict((k.key, v) for k, v in tree.items())

    def get_children(n):
        return key_tree[n.key]

    if show_only:
        nodes = [p for p in nodes
                 if p.key in show_only or p.project_name in show_only]
    elif not list_all:
        nodes = [p for p in nodes if p.key not in branch_keys]

    def aux(node, parent=None, indent=0, chain=None):
        if chain is None:
            chain = [node.project_name]
        node_str = node.render(parent, frozen)
        if parent:
            prefix = ' '*indent + ('-' if use_bullets else ' ') + ' '
            node_str = prefix + node_str
        result = [node_str]

        # the dist attr for some ReqPackage could be None
        # eg. testresources, setuptools which is a dependencies of
        # some pkg but doesn't get listed in the result of
        # pip.get_installed_distributions.
        if node.dist:
            children = [aux(c, node, indent=indent+2,
                            chain=chain+[c.project_name])
                        for c in get_children(node)
                        if c.project_name not in chain]
            result += list(flatten(children))
        return result

    lines = flatten([aux(p) for p in nodes])
    return '\n'.join(lines)


def jsonify_tree(tree, indent):
    """Converts the tree into json representation.

    The json repr will be a list of hashes, each hash having 2 fields:
      - package
      - dependencies: list of dependencies

    :param dict tree: dependency tree
    :param int indent: no. of spaces to indent json
    :returns: json representation of the tree
    :rtype: str

    """
    return json.dumps([{'package': k.as_dict(),
                        'dependencies': [v.as_dict() for v in vs]}
                       for k, vs in tree.items()],
                      indent=indent)


def conflicting_deps(tree):
    """Returns dependencies which are not present or conflict with the
    requirements of other packages.

    e.g. will warn if pkg1 requires pkg2==2.0 and pkg2==1.0 is installed

    :param tree: the requirements tree (dict)
    :returns: dict of DistPackage -> list of unsatisfied/unknown ReqPackage
    :rtype: dict

    """
    conflicting = defaultdict(list)
    req_parse = pkg_resources.Requirement.parse
    for p, rs in tree.items():
        for req in rs:
            if not req.dist:
                conflicting[p].append(req)
            else:
                req_version_str = '%s%s' % (req.project_name, (req.version_spec if req.version_spec else ''))
                if req.installed_version not in req_parse(req_version_str):
                    conflicting[p].append(req)
    return conflicting


def cyclic_deps(tree):
    """Generator that produces cyclic dependencies

    :param list pkgs: pkg_resources.Distribution instances
    :param dict pkg_index: mapping of pkgs with their respective keys
    :returns: generator that yields str representation of cyclic
              dependencies
    :rtype: generator

    """
    nodes = tree.keys()
    key_tree = dict((k.key, v) for k, v in tree.items())

    def get_children(n):
        return key_tree[n.key]

    def aux(node, chain):
        if node.dist:
            for c in get_children(node):
                if c.project_name in chain:
                    yield ' => '.join([str(p) for p in chain] + [str(c)])
                else:
                    for cycle in aux(c, chain=chain+[c.project_name]):
                        yield cycle

    for cycle in flatten([aux(n, chain=[]) for n in nodes]):
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
                            'do not show globally installed packages'
                        ))
    parser.add_argument('-w', '--warn', action='store', dest='warn',
                        nargs='?', default='suppress',
                        choices=('silence', 'suppress', 'fail'),
                        help=(
                            'Warning control. "suppress" will show warnings '
                            'but return 0 whether or not they are present. '
                            '"silence" will not show warnings at all and '
                            'always return 0. "fail" will show warnings and '
                            'return 1 if any are present. The default is '
                            '"suppress".'
                        ))
    parser.add_argument('-r', '--reverse', action='store_true',
                        default=False, help=(
                            'Shows the dependency tree in the reverse fashion '
                            'ie. the sub-dependencies are listed with the '
                            'list of packages that need them under them.'
                        ))
    parser.add_argument('-p', '--packages',
                        help=(
                            'Comma separated list of select packages to show '
                            'in the output. If set, --all will be ignored.'
                        ))
    parser.add_argument('-j', '--json', action='store_true', default=False,
                        help=(
                            'Display dependency tree as json. This will yield '
                            '"raw" output that may be used by external tools. '
                            'This option overrides all other options.'
                        ))
    args = parser.parse_args()

    default_skip = ['setuptools', 'pip', 'python', 'distribute']
    skip = default_skip + ['pipdeptree']
    pkgs = pip.get_installed_distributions(local_only=args.local_only,
                                           skip=skip)

    dist_index = build_dist_index(pkgs)
    tree = construct_tree(dist_index)

    if args.json:
        print(jsonify_tree(tree, indent=4))
        return 0

    return_code = 0

    # show warnings about possibly conflicting deps if found and
    # warnings are enabled
    if args.warn != 'silence':
        conflicting = conflicting_deps(tree)
        if conflicting:
            print('Warning!!! Possibly conflicting dependencies found:',
                  file=sys.stderr)
            for p, reqs in conflicting.items():
                pkg = p.render_as_root(False)
                print('* %s' % pkg, file=sys.stderr)
                for req in reqs:
                    if not req.dist:
                        req_str = (
                            '{0} [required: {1}, '
                            'installed: <unknown>]'
                        ).format(req.project_name, req.version_spec)
                    else:
                        req_str = req.render_as_branch(p, False)
                    print(' - %s' % req_str, file=sys.stderr)
            print('-'*72, file=sys.stderr)

        is_empty, cyclic = peek_into(cyclic_deps(tree))
        if not is_empty:
            print('Warning!!! Cyclic dependencies found:', file=sys.stderr)
            for xs in cyclic:
                print('- {0}'.format(xs), file=sys.stderr)
            print('-'*72, file=sys.stderr)

        if args.warn == 'fail' and (conflicting or not is_empty):
            return_code = 1

    show_only = set(args.packages.split(',')) if args.packages else None

    tree = render_tree(tree if not args.reverse else reverse_tree(tree),
                       list_all=args.all, show_only=show_only,
                       frozen=args.freeze)
    print(tree)
    return return_code


if __name__ == '__main__':
    sys.exit(main())
