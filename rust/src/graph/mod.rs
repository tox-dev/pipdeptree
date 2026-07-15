use std::borrow::Cow;
use std::collections::{BTreeMap, BTreeSet, HashMap, HashSet};
use std::ops::Range;
use std::str::FromStr;
use std::sync::OnceLock;

use pep508_rs::marker::{MarkerExpression, MarkerValueExtra};
use pep508_rs::pep440_rs::Version;
use pep508_rs::{ExtraName, MarkerEnvironment, MarkerTree, Requirement, VerbatimUrl, VersionOrUrl};

use crate::metadata::{Package, canonicalize_name};
use crate::options::ExtrasMode;

mod extras;
mod filter;
mod version;

pub use filter::FilterSpec;

#[derive(Debug)]
pub struct Dependency {
    pub requirement: Requirement<VerbatimUrl>,
    pub target: Option<usize>,
    pub activated_by: Option<String>,
    version_spec: OnceLock<Option<String>>,
}

impl Clone for Dependency {
    fn clone(&self) -> Self {
        Self {
            requirement: self.requirement.clone(),
            target: self.target,
            activated_by: self.activated_by.clone(),
            version_spec: OnceLock::new(),
        }
    }
}

#[derive(Debug)]
pub struct Node {
    pub package: Package,
    dependencies: Vec<Dependency>,
    mandatory: Range<usize>,
    optional: BTreeMap<String, Range<usize>>,
    parsed_version: OnceLock<Option<Version>>,
}

#[derive(Debug)]
pub struct Graph {
    pub nodes: Vec<Node>,
    pub visible: Vec<bool>,
    pub global_extras: HashMap<usize, BTreeSet<String>>,
    requested_extras: HashMap<usize, BTreeSet<String>>,
    missing_versions: HashMap<String, String>,
    expanded: OnceLock<Vec<Vec<usize>>>,
    reverse_edges: OnceLock<Vec<Vec<(usize, usize)>>>,
    cycles: OnceLock<Vec<Vec<usize>>>,
    unique_dependencies: OnceLock<UniqueDependencyCache>,
    pub warnings: Vec<String>,
}

pub struct Children<'a> {
    graph: &'a Graph,
    node: usize,
    indices: Cow<'a, [usize]>,
    position: usize,
}

pub enum ReverseRoot<'a> {
    Installed(usize),
    Missing {
        name: &'a str,
        parents: Vec<(usize, &'a Dependency)>,
    },
}

type UniqueDependencyCache = (Vec<usize>, Vec<OnceLock<BTreeSet<usize>>>);

#[derive(Debug, thiserror::Error)]
pub enum FilterError {
    #[error("No packages matched using the following patterns: {}", .0.join(", "))]
    Unmatched(Vec<String>),
    #[error("Cannot have --packages and --exclude contain the same entries")]
    Overlap,
}

impl Dependency {
    pub fn key(&self) -> &str {
        self.requirement.name.as_ref()
    }

    pub fn version_spec(&self) -> Option<String> {
        self.version_spec
            .get_or_init(|| match &self.requirement.version_or_url {
                Some(VersionOrUrl::VersionSpecifier(specifiers)) if !specifiers.is_empty() => {
                    Some(specifiers.to_string().replace(", ", ","))
                }
                _ => None,
            })
            .clone()
    }

    pub fn requested_extras(&self) -> BTreeSet<String> {
        self.requirement
            .extras
            .iter()
            .map(ToString::to_string)
            .collect()
    }

    pub fn is_conflicting(&self, graph: &Graph) -> bool {
        let Some(installed) = self.installed_version(graph) else {
            return true;
        };
        let Some(VersionOrUrl::VersionSpecifier(specifiers)) = &self.requirement.version_or_url
        else {
            return false;
        };
        self.target.map_or_else(
            || Version::from_str(installed).map_or(true, |version| !specifiers.contains(&version)),
            |target| {
                graph
                    .parsed_version(target)
                    .is_none_or(|version| !specifiers.contains(version))
            },
        )
    }

    pub fn installed_version<'a>(&self, graph: &'a Graph) -> Option<&'a str> {
        self.target.map_or_else(
            || graph.missing_versions.get(self.key()).map(String::as_str),
            |target| Some(graph.nodes[target].package.version.as_str()),
        )
    }
}

impl Graph {
    pub fn new(
        mut packages: Vec<Package>,
        marker: &MarkerEnvironment,
        extras_mode: ExtrasMode,
    ) -> Self {
        packages.sort_by(|left, right| left.key.cmp(&right.key));
        let index = packages
            .iter()
            .enumerate()
            .map(|(position, package)| (package.key.clone(), position))
            .collect::<HashMap<_, _>>();
        let mut warnings = Vec::new();
        let nodes = packages
            .into_iter()
            .map(|package| Self::build_node(package, marker, &index, &mut warnings))
            .collect::<Vec<_>>();
        let mut graph = Self {
            visible: vec![true; nodes.len()],
            nodes,
            global_extras: HashMap::new(),
            requested_extras: HashMap::new(),
            missing_versions: HashMap::new(),
            expanded: OnceLock::new(),
            reverse_edges: OnceLock::new(),
            cycles: OnceLock::new(),
            unique_dependencies: OnceLock::new(),
            warnings,
        };
        if extras_mode != ExtrasMode::None {
            graph.collect_requested_extras();
        }
        if extras_mode == ExtrasMode::Active {
            graph.activate_satisfied_extras();
        }
        graph
    }

    fn build_node(
        mut package: Package,
        marker: &MarkerEnvironment,
        index: &HashMap<String, usize>,
        warnings: &mut Vec<String>,
    ) -> Node {
        let mut mandatory = Vec::new();
        let mut optional = BTreeMap::<String, Vec<Dependency>>::new();
        let requires = std::mem::take(&mut package.requires);
        for raw in requires {
            let Ok(requirement) = Requirement::<VerbatimUrl>::from_str(&raw) else {
                warnings.push(format!(
                    "Invalid requirement found in {}: {raw}",
                    package.name
                ));
                continue;
            };
            let dependency = Dependency {
                target: index.get(requirement.name.as_ref()).copied(),
                requirement,
                activated_by: None,
                version_spec: OnceLock::new(),
            };
            if dependency.requirement.evaluate_markers(marker, &[]) {
                mandatory.push(dependency);
                continue;
            }
            // The requirement's own marker names the extras that can activate it; an extra
            // referenced only here still counts, since Provides-Extra is descriptive metadata.
            for extra_name in marker_extras(&dependency.requirement.marker) {
                if dependency
                    .requirement
                    .evaluate_markers(marker, std::slice::from_ref(&extra_name))
                {
                    let mut dependency = dependency.clone();
                    let extra = extra_name.to_string();
                    dependency.activated_by = Some(extra.clone());
                    optional.entry(extra).or_default().push(dependency);
                }
            }
        }
        mandatory.sort_by(|left, right| left.key().cmp(right.key()));
        mandatory.dedup_by(|left, right| left.requirement == right.requirement);
        for dependencies in optional.values_mut() {
            dependencies.sort_by(|left, right| left.key().cmp(right.key()));
            dependencies.dedup_by(|left, right| left.requirement == right.requirement);
        }
        let mandatory_end = mandatory.len();
        let mut dependencies = mandatory;
        let optional = optional
            .into_iter()
            .map(|(extra, values)| {
                let start = dependencies.len();
                dependencies.extend(values);
                (extra, start..dependencies.len())
            })
            .collect();
        Node {
            package,
            dependencies,
            mandatory: 0..mandatory_end,
            optional,
            parsed_version: OnceLock::new(),
        }
    }

    pub fn validate(&mut self) {
        self.collect_validation_warnings();
    }

    pub(super) fn children<'a>(
        &'a self,
        index: usize,
        incoming_extras: &BTreeSet<String>,
    ) -> Children<'a> {
        Children {
            graph: self,
            node: index,
            indices: Cow::Owned(self.selected_children(index, incoming_extras)),
            position: 0,
        }
    }

    pub(super) fn expanded_children(&self, index: usize) -> Children<'_> {
        Children {
            graph: self,
            node: index,
            indices: Cow::Borrowed(&self.expanded_children_cache()[index]),
            position: 0,
        }
    }

    pub fn parents(&self, child: usize) -> Vec<(usize, &Dependency)> {
        self.parents_for(child, None)
    }

    pub fn parents_for(
        &self,
        child: usize,
        required_extra: Option<&str>,
    ) -> Vec<(usize, &Dependency)> {
        let required = required_extra.map(canonicalize_name);
        let mut result = Vec::new();
        // Nodes sort by key at construction, so ascending parent indices are already key order.
        for (parent, slot) in &self.reverse_edges()[child] {
            if !self.visible[*parent] {
                continue;
            }
            let dependency = &self.nodes[*parent].dependencies[*slot];
            if required.as_ref().is_none_or(|extra| {
                dependency
                    .requirement
                    .extras
                    .iter()
                    .any(|candidate| candidate.as_ref() == extra)
            }) {
                result.push((*parent, dependency));
            }
        }
        result
    }

    fn reverse_edges(&self) -> &[Vec<(usize, usize)>] {
        self.reverse_edges.get_or_init(|| {
            let mut edges = vec![Vec::new(); self.nodes.len()];
            for parent in 0..self.nodes.len() {
                for slot in &self.expanded_children_cache()[parent] {
                    if let Some(target) = self.nodes[parent].dependencies[*slot].target {
                        edges[target].push((parent, *slot));
                    }
                }
            }
            edges
        })
    }

    pub fn extra_is_global(&self, index: usize, extra: &str) -> bool {
        let Some(extras) = self.global_extras.get(&index) else {
            return false;
        };
        extras.contains(&canonicalize_name(extra))
    }

    // Uninstalled requirements have no node, yet every renderer must still show them and the
    // packages that need them.
    pub fn missing_dependents(&self) -> BTreeMap<&str, Vec<(usize, &Dependency)>> {
        let mut missing = BTreeMap::<&str, Vec<(usize, &Dependency)>>::new();
        for parent in self.visible_indices() {
            for dependency in self.expanded_children(parent) {
                if dependency.target.is_none() {
                    missing
                        .entry(dependency.key())
                        .or_default()
                        .push((parent, dependency));
                }
            }
        }
        for parents in missing.values_mut() {
            parents.sort_by(|(left, _), (right, _)| {
                self.nodes[*left]
                    .package
                    .key
                    .cmp(&self.nodes[*right].package.key)
            });
        }
        missing
    }

    pub fn reverse_roots(&self, list_all: bool) -> Vec<ReverseRoot<'_>> {
        let missing = self.missing_dependents();
        // A package shown beneath a missing root is a branch, not a root of its own.
        let missing_parents = missing
            .values()
            .flat_map(|parents| parents.iter().map(|(parent, _)| *parent))
            .collect::<HashSet<_>>();
        let mut missing = missing.into_iter().peekable();
        let mut result = Vec::new();
        for index in self
            .roots(true, list_all)
            .into_iter()
            .filter(|index| list_all || !missing_parents.contains(index))
        {
            let key = self.nodes[index].package.key.as_str();
            while missing.peek().is_some_and(|(name, _)| *name < key) {
                let (name, parents) = missing.next().expect("peek confirmed a next entry");
                result.push(ReverseRoot::Missing { name, parents });
            }
            result.push(ReverseRoot::Installed(index));
        }
        result.extend(missing.map(|(name, parents)| ReverseRoot::Missing { name, parents }));
        result
    }

    fn parsed_version(&self, index: usize) -> Option<&Version> {
        self.nodes[index]
            .parsed_version
            .get_or_init(|| Version::from_str(&self.nodes[index].package.version).ok())
            .as_ref()
    }

    // Uniqueness is judged against the full environment, not the filtered view: a package
    // still needed by a hidden dependent is not removable.
    pub(crate) fn unique_dependencies(&self, index: usize) -> &BTreeSet<usize> {
        let (full_counts, cache) = self.unique_dependencies.get_or_init(|| {
            let mut counts = vec![0_usize; self.nodes.len()];
            for parent in 0..self.nodes.len() {
                for target in self.active_targets(parent) {
                    counts[target] += 1;
                }
            }
            (
                counts,
                (0..self.nodes.len()).map(|_| OnceLock::new()).collect(),
            )
        });
        cache[index].get_or_init(|| {
            let mut parent_counts = full_counts.clone();
            let mut removed = BTreeSet::from([index]);
            let mut stack = vec![index];
            while let Some(parent) = stack.pop() {
                for child in self.active_targets(parent) {
                    parent_counts[child] = parent_counts[child].saturating_sub(1);
                    if parent_counts[child] == 0 && removed.insert(child) {
                        stack.push(child);
                    }
                }
            }
            removed.remove(&index);
            removed
        })
    }

    fn active_targets(&self, index: usize) -> impl Iterator<Item = usize> + '_ {
        self.expanded_children_cache()[index]
            .iter()
            .filter_map(move |slot| self.nodes[index].dependencies[*slot].target)
    }

    pub fn missing_version(&self, name: &str) -> &str {
        self.missing_versions.get(name).map_or("?", String::as_str)
    }

    pub fn roots(&self, reverse: bool, list_all: bool) -> Vec<usize> {
        let visible = self.visible_indices().collect::<Vec<_>>();
        if list_all {
            return visible;
        }
        let branch = if reverse {
            self.visible_indices()
                .flat_map(|child| self.parents(child).into_iter().map(|(parent, _)| parent))
                .collect::<HashSet<_>>()
        } else {
            self.visible_indices()
                .flat_map(|parent| {
                    self.expanded_children(parent)
                        .filter_map(|dependency| dependency.target)
                })
                .collect::<HashSet<_>>()
        };
        let roots = visible
            .iter()
            .copied()
            .filter(|index| !branch.contains(index))
            .collect::<Vec<_>>();
        if roots.is_empty() { visible } else { roots }
    }

    pub fn visible_indices(&self) -> impl Iterator<Item = usize> + '_ {
        self.visible
            .iter()
            .enumerate()
            .filter_map(|(index, visible)| visible.then_some(index))
    }

    pub fn missing_dependencies(&self) -> usize {
        self.visible_indices()
            .flat_map(|index| self.expanded_children(index))
            .filter(|dependency| dependency.installed_version(self).is_none())
            .map(Dependency::key)
            .collect::<HashSet<_>>()
            .len()
    }

    pub fn conflicts(&self) -> (usize, usize) {
        let mut packages = HashSet::new();
        let mut edges = 0;
        for parent in self.visible_indices() {
            for dependency in self.expanded_children(parent) {
                if dependency.is_conflicting(self) {
                    packages.insert(parent);
                    edges += 1;
                }
            }
        }
        (packages.len(), edges)
    }

    pub fn cycle_count(&self) -> usize {
        self.cycles().iter().map(Vec::len).sum()
    }

    fn cycles(&self) -> &[Vec<usize>] {
        self.cycles.get_or_init(|| self.compute_cycles())
    }

    fn compute_cycles(&self) -> Vec<Vec<usize>> {
        let mut outgoing = vec![Vec::new(); self.nodes.len()];
        let mut incoming = vec![Vec::new(); self.nodes.len()];
        for parent in self.visible_indices() {
            for child in self
                .expanded_children(parent)
                .filter_map(|dependency| dependency.target)
                .filter(|child| self.visible[*child])
            {
                outgoing[parent].push(child);
                incoming[child].push(parent);
            }
        }

        let mut visited = vec![false; self.nodes.len()];
        let mut order = Vec::new();
        for start in self.visible_indices() {
            if visited[start] {
                continue;
            }
            visited[start] = true;
            let mut stack = vec![(start, 0)];
            while let Some((node, next_child)) = stack.last_mut() {
                if *next_child == outgoing[*node].len() {
                    order.push(*node);
                    stack.pop();
                    continue;
                }
                let child = outgoing[*node][*next_child];
                *next_child += 1;
                if !visited[child] {
                    visited[child] = true;
                    stack.push((child, 0));
                }
            }
        }

        visited.fill(false);
        let mut result = Vec::new();
        while let Some(start) = order.pop() {
            if visited[start] {
                continue;
            }
            visited[start] = true;
            let mut component = Vec::new();
            let mut stack = vec![start];
            while let Some(node) = stack.pop() {
                component.push(node);
                for parent in &incoming[node] {
                    if !visited[*parent] {
                        visited[*parent] = true;
                        stack.push(*parent);
                    }
                }
            }
            if component.len() > 1 || outgoing[start].contains(&start) {
                result.push(component);
            }
        }
        result
    }

    fn cycle_chain(&self, component: &[usize]) -> String {
        let members = component.iter().copied().collect::<HashSet<_>>();
        let start = component
            .iter()
            .copied()
            .min_by_key(|index| &self.nodes[*index].package.key)
            .expect("cycle components are never empty");
        let mut path = vec![start];
        let mut visited = HashSet::from([start]);
        self.extend_cycle(start, start, &members, &mut visited, &mut path);
        path.push(start);
        path.iter()
            .map(|index| self.nodes[*index].package.key.as_str())
            .collect::<Vec<_>>()
            .join(" => ")
    }

    // Recursion depth is a dependency cycle's length, which is tiny in practice; the backtracking
    // return keeps the walk cheap when a branch dead-ends before reaching start.
    fn extend_cycle(
        &self,
        current: usize,
        start: usize,
        members: &HashSet<usize>,
        visited: &mut HashSet<usize>,
        path: &mut Vec<usize>,
    ) -> bool {
        for child in self
            .expanded_children(current)
            .filter_map(|dependency| dependency.target)
            .filter(|child| members.contains(child))
        {
            if child == start {
                return true;
            }
            if visited.insert(child) {
                path.push(child);
                if self.extend_cycle(child, start, members, visited, path) {
                    return true;
                }
                path.pop();
            }
        }
        false
    }

    fn selected_children(&self, index: usize, incoming_extras: &BTreeSet<String>) -> Vec<usize> {
        let node = &self.nodes[index];
        let global = self.global_extras.get(&index);
        if incoming_extras.is_empty() && global.is_none() {
            return node.mandatory.clone().collect();
        }
        let mut result = node.mandatory.clone().collect::<Vec<_>>();
        for (extra, range) in &node.optional {
            if incoming_extras.contains(extra)
                || global.is_some_and(|extras| extras.contains(extra))
            {
                result.extend(
                    range
                        .clone()
                        .filter(|dependency| node.dependencies[*dependency].target.is_some()),
                );
            }
        }
        result.sort_by(|left, right| {
            let left = &node.dependencies[*left];
            let right = &node.dependencies[*right];
            left.key()
                .cmp(right.key())
                .then_with(|| left.activated_by.cmp(&right.activated_by))
        });
        result.dedup_by(|left, right| {
            let left = &node.dependencies[*left];
            let right = &node.dependencies[*right];
            left.requirement == right.requirement && left.activated_by == right.activated_by
        });
        result
    }

    fn expanded_children_cache(&self) -> &[Vec<usize>] {
        self.expanded.get_or_init(|| {
            (0..self.nodes.len())
                .map(|index| {
                    self.requested_extras.get(&index).map_or_else(
                        || self.selected_children(index, &BTreeSet::new()),
                        |extras| self.selected_children(index, extras),
                    )
                })
                .collect()
        })
    }

    fn collect_validation_warnings(&mut self) {
        for index in 0..self.nodes.len() {
            let package = &self.nodes[index].package;
            let mut problems = Vec::new();
            for dependency in self.expanded_children(index) {
                if dependency.is_conflicting(self) {
                    problems.push(format!(
                        "{} [required: {}, installed: {}]",
                        dependency.key(),
                        dependency
                            .version_spec()
                            .unwrap_or_else(|| "Any".to_string()),
                        dependency.installed_version(self).unwrap_or("?")
                    ));
                }
            }
            if !problems.is_empty() {
                self.warnings.push(format!(
                    "{}=={}\n  - {}",
                    package.name,
                    package.version,
                    problems.join("\n  - ")
                ));
            }
        }
        let cycles = self.cycles();
        if !cycles.is_empty() {
            let chains = cycles
                .iter()
                .map(|component| self.cycle_chain(component))
                .collect::<Vec<_>>();
            self.warnings.push(format!(
                "Cyclic dependencies found:\n  {}",
                chains.join("\n  ")
            ));
        }
    }
}

impl<'a> Iterator for Children<'a> {
    type Item = &'a Dependency;

    fn next(&mut self) -> Option<Self::Item> {
        while let Some(index) = self.indices.get(self.position) {
            self.position += 1;
            let dependency = &self.graph.nodes[self.node].dependencies[*index];
            if dependency
                .target
                .is_none_or(|target| self.graph.visible[target])
            {
                return Some(dependency);
            }
        }
        None
    }

    fn size_hint(&self) -> (usize, Option<usize>) {
        (0, Some(self.indices.len() - self.position))
    }
}

fn marker_extras(marker: &MarkerTree) -> BTreeSet<ExtraName> {
    marker
        .to_dnf()
        .into_iter()
        .flatten()
        .filter_map(|expression| match expression {
            MarkerExpression::Extra {
                name: MarkerValueExtra::Extra(name),
                ..
            } => Some(name),
            _ => None,
        })
        .collect()
}
