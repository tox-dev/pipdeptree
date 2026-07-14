use std::borrow::Cow;
use std::collections::{BTreeMap, BTreeSet, HashMap, HashSet, VecDeque};
use std::ops::Range;
use std::str::FromStr;
use std::sync::OnceLock;

use glob::Pattern;
use pep508_rs::pep440_rs::Version;
use pep508_rs::{ExtraName, MarkerEnvironment, Requirement, VerbatimUrl, VersionOrUrl};
use pyo3::exceptions::{PyAttributeError, PyImportError};
use pyo3::prelude::{PyAnyMethods, PyModule};
use pyo3::{PyResult, Python};

use crate::metadata::{Package, canonicalize_name};
use crate::options::{ExtrasMode, Options};

#[derive(Clone, Debug)]
pub struct Dependency {
    pub requirement: Requirement<VerbatimUrl>,
    pub target: Option<usize>,
    pub activated_by: Option<String>,
}

#[derive(Debug)]
pub struct Node {
    pub package: Package,
    dependencies: Vec<Dependency>,
    mandatory: Range<usize>,
    optional: BTreeMap<String, Range<usize>>,
}

#[derive(Debug)]
pub struct Graph {
    pub nodes: Vec<Node>,
    pub visible: Vec<bool>,
    pub global_extras: HashMap<usize, BTreeSet<String>>,
    requested_extras: HashMap<usize, BTreeSet<String>>,
    incoming: Vec<Vec<usize>>,
    missing_versions: HashMap<String, String>,
    expanded: OnceLock<Vec<Vec<usize>>>,
    parent_counts: OnceLock<Vec<usize>>,
    pub warnings: Vec<String>,
}

#[derive(Clone)]
pub struct Children<'a> {
    graph: &'a Graph,
    node: usize,
    indices: Cow<'a, [usize]>,
    position: usize,
}

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
        match &self.requirement.version_or_url {
            Some(VersionOrUrl::VersionSpecifier(specifiers)) if !specifiers.is_empty() => {
                Some(specifiers.to_string().replace(", ", ","))
            }
            _ => None,
        }
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
        Version::from_str(installed).map_or(true, |version| !specifiers.contains(&version))
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
            .map(|mut package| {
                let mut mandatory = Vec::new();
                let mut optional = BTreeMap::<String, Vec<Dependency>>::new();
                let requires = std::mem::take(&mut package.requires);
                let provides_extras = std::mem::take(&mut package.provides_extras);
                for raw in requires {
                    let Ok(requirement) = Requirement::<VerbatimUrl>::from_str(&raw) else {
                        warnings.push(format!("Invalid requirement found: {raw}"));
                        continue;
                    };
                    let dependency = Dependency {
                        target: index.get(requirement.name.as_ref()).copied(),
                        requirement,
                        activated_by: None,
                    };
                    if dependency.requirement.evaluate_markers(marker, &[]) {
                        mandatory.push(dependency);
                        continue;
                    }
                    for extra in &provides_extras {
                        let Ok(extra_name) = ExtraName::from_str(extra) else {
                            continue;
                        };
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
                }
            })
            .collect::<Vec<_>>();
        let mut incoming = vec![Vec::new(); nodes.len()];
        for (parent, node) in nodes.iter().enumerate() {
            for target in node
                .dependencies
                .iter()
                .filter_map(|dependency| dependency.target)
            {
                incoming[target].push(parent);
            }
        }
        for parents in &mut incoming {
            parents.sort_unstable();
            parents.dedup();
        }
        let mut graph = Self {
            visible: vec![true; nodes.len()],
            nodes,
            global_extras: HashMap::new(),
            requested_extras: HashMap::new(),
            incoming,
            missing_versions: HashMap::new(),
            expanded: OnceLock::new(),
            parent_counts: OnceLock::new(),
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

    pub fn resolve_missing_versions(&mut self, py: Python<'_>) -> PyResult<()> {
        let metadata = PyModule::import(py, "importlib.metadata")?;
        let package_not_found = metadata.getattr("PackageNotFoundError")?;
        // Only dependencies that can render matter; resolving inactive extras would import
        // arbitrary modules (and run their side effects) for packages never shown.
        let names = (0..self.nodes.len())
            .flat_map(|index| self.expanded_children(index))
            .filter(|dependency| dependency.target.is_none())
            .map(|dependency| dependency.key().to_string())
            .collect::<BTreeSet<_>>();
        for name in names {
            let version = match metadata.getattr("version")?.call1((&name,)) {
                Ok(value) => Some(value.extract()?),
                Err(error) if error.is_instance(py, &package_not_found) => {
                    module_version(py, &name)?
                }
                Err(error) => return Err(error),
            };
            if let Some(version) = version {
                self.missing_versions.insert(name, version);
            }
        }
        Ok(())
    }

    pub fn apply_global_extras(&mut self, options: &Options) {
        let (_, extras) = parse_packages(options.packages.as_deref());
        if extras.is_empty() {
            return;
        }
        let mut pending = VecDeque::new();
        for (pattern, values) in extras {
            for index in self.matching(&pattern) {
                self.global_extras
                    .entry(index)
                    .or_default()
                    .extend(values.iter().cloned());
                let node = &self.nodes[index];
                for dependency in values
                    .iter()
                    .filter_map(|extra| node.optional.get(extra))
                    .flat_map(|range| &node.dependencies[range.clone()])
                {
                    if let Some(target) = dependency.target {
                        let nested = dependency.requested_extras();
                        if !nested.is_empty() {
                            pending.push_back((target, nested));
                        }
                    }
                }
            }
        }
        self.propagate_requested_extras(pending);
        self.expanded.take();
        self.parent_counts.take();
    }

    pub fn validate(&mut self) {
        self.collect_validation_warnings();
    }

    pub fn apply_filters(&mut self, options: &Options) -> Result<(), FilterError> {
        let (include, _) = parse_packages(options.packages.as_deref());
        self.expanded.take();
        self.parent_counts.take();
        let exclude_patterns = options
            .exclude
            .as_deref()
            .map(|value| {
                value
                    .split(',')
                    .map(str::trim)
                    .filter(|value| !value.is_empty())
                    .map(ToOwned::to_owned)
                    .collect::<Vec<_>>()
            })
            .unwrap_or_default();
        let canonical_excludes = exclude_patterns
            .iter()
            .map(|pattern| canonicalize_pattern(pattern))
            .collect::<HashSet<_>>();
        if include
            .iter()
            .map(|pattern| canonicalize_pattern(pattern))
            .any(|pattern| canonical_excludes.contains(&pattern))
        {
            return Err(FilterError::Overlap);
        }
        let mut include_matches = HashSet::new();
        let unmatched = include
            .iter()
            .filter_map(|pattern| {
                let matched = self.matching(pattern);
                if matched.is_empty() {
                    Some(pattern.clone())
                } else {
                    include_matches.extend(matched);
                    None
                }
            })
            .collect::<Vec<_>>();
        if !unmatched.is_empty() {
            return Err(FilterError::Unmatched(unmatched));
        }
        let exclude_matches = self.matching_many(&exclude_patterns);
        if !include.is_empty() {
            let mut included = vec![false; self.nodes.len()];
            self.mark_into(&include_matches, options.reverse, &mut included);
            self.visible = included;
        }
        if options.exclude_dependencies {
            let mut excluded = vec![false; self.nodes.len()];
            self.mark_into(&exclude_matches, options.reverse, &mut excluded);
            for (visible, excluded) in self.visible.iter_mut().zip(excluded) {
                *visible &= !excluded;
            }
        } else {
            for index in exclude_matches {
                self.visible[index] = false;
            }
        }
        Ok(())
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

    pub(super) fn parent_counts(&self) -> &[usize] {
        self.parent_counts.get_or_init(|| {
            let mut counts = vec![0; self.nodes.len()];
            for parent in self.visible_indices() {
                for child in self
                    .expanded_children(parent)
                    .filter_map(|dependency| dependency.target)
                {
                    counts[child] += 1;
                }
            }
            counts
        })
    }

    pub fn parents(&self, child: usize) -> Vec<(usize, &Dependency)> {
        self.parents_for(child, None)
    }

    pub fn parents_for(
        &self,
        child: usize,
        required_extra: Option<&str>,
    ) -> Vec<(usize, &Dependency)> {
        let mut result = Vec::new();
        for &parent in &self.incoming[child] {
            if !self.visible[parent] {
                continue;
            }
            for dependency in self.expanded_children(parent) {
                if dependency.target == Some(child)
                    && required_extra.is_none_or(|extra| {
                        dependency
                            .requested_extras()
                            .contains(&canonicalize_name(extra))
                    })
                {
                    result.push((parent, dependency));
                }
            }
        }
        result.sort_by(|(left, _), (right, _)| {
            self.nodes[*left]
                .package
                .key
                .cmp(&self.nodes[*right].package.key)
        });
        result
    }

    pub fn extra_is_global(&self, index: usize, extra: &str) -> bool {
        let Some(extras) = self.global_extras.get(&index) else {
            return false;
        };
        extras.contains(&canonicalize_name(extra))
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
        let mut count = 0;
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
                count += component.len();
            }
        }
        count
    }

    fn matching(&self, pattern: &str) -> Vec<usize> {
        let pattern = canonicalize_pattern(pattern);
        let Ok(pattern) = Pattern::new(&pattern) else {
            return Vec::new();
        };
        self.nodes
            .iter()
            .enumerate()
            .filter_map(|(index, node)| pattern.matches(&node.package.key).then_some(index))
            .collect()
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

    fn matching_many(&self, patterns: &[String]) -> HashSet<usize> {
        patterns
            .iter()
            .flat_map(|pattern| self.matching(pattern))
            .collect()
    }

    fn mark_into(&self, seeds: &HashSet<usize>, reverse: bool, marked: &mut [bool]) {
        let mut queue = seeds.iter().copied().collect::<VecDeque<_>>();
        while let Some(index) = queue.pop_front() {
            if marked[index] {
                continue;
            }
            marked[index] = true;
            if reverse {
                queue.extend(self.parents(index).into_iter().map(|(parent, _)| parent));
            } else {
                queue.extend(
                    self.expanded_children(index)
                        .filter_map(|dependency| dependency.target),
                );
            }
        }
    }

    fn collect_requested_extras(&mut self) {
        let mut pending = VecDeque::new();
        for index in 0..self.nodes.len() {
            let node = &self.nodes[index];
            for dependency in &node.dependencies[node.mandatory.clone()] {
                if let Some(target) = dependency.target {
                    let extras = dependency.requested_extras();
                    if !extras.is_empty() {
                        pending.push_back((target, extras));
                    }
                }
            }
        }
        self.propagate_requested_extras(pending);
    }

    fn propagate_requested_extras(&mut self, mut pending: VecDeque<(usize, BTreeSet<String>)>) {
        while let Some((index, extras)) = pending.pop_front() {
            let entry = self.requested_extras.entry(index).or_default();
            let new = extras.difference(entry).cloned().collect::<BTreeSet<_>>();
            if new.is_empty() {
                continue;
            }
            entry.extend(new.iter().cloned());
            for extra in new {
                let node = &self.nodes[index];
                for dependency in node
                    .optional
                    .get(&extra)
                    .into_iter()
                    .flat_map(|range| &node.dependencies[range.clone()])
                {
                    if let Some(target) = dependency.target {
                        let nested = dependency.requested_extras();
                        if !nested.is_empty() {
                            pending.push_back((target, nested));
                        }
                    }
                }
            }
        }
    }

    fn activate_satisfied_extras(&mut self) {
        let mut satisfied = self
            .nodes
            .iter()
            .enumerate()
            .flat_map(|(index, node)| {
                node.optional
                    .keys()
                    .cloned()
                    .map(move |extra| (index, extra))
            })
            .collect::<HashSet<_>>();
        let mut dependents = HashMap::<(usize, String), Vec<(usize, String)>>::new();
        let mut unsatisfied = VecDeque::new();
        for pair in &satisfied {
            let node = &self.nodes[pair.0];
            for dependency in &node.dependencies[node.optional[&pair.1].clone()] {
                let Some(target) = dependency.target else {
                    unsatisfied.push_back(pair.clone());
                    continue;
                };
                for extra in dependency.requested_extras() {
                    let required = (target, extra);
                    if satisfied.contains(&required) {
                        dependents.entry(required).or_default().push(pair.clone());
                    } else {
                        unsatisfied.push_back(pair.clone());
                    }
                }
            }
        }
        while let Some(pair) = unsatisfied.pop_front() {
            if satisfied.remove(&pair) {
                unsatisfied.extend(dependents.remove(&pair).into_iter().flatten());
            }
        }
        for (index, extra) in satisfied {
            self.global_extras.entry(index).or_default().insert(extra);
        }
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
        if self.cycle_count() != 0 {
            self.warnings.push("Cyclic dependencies found".to_string());
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

impl Children<'_> {
    pub(super) fn len(&self) -> usize {
        self.clone().count()
    }
}

fn parse_packages(value: Option<&str>) -> (Vec<String>, HashMap<String, BTreeSet<String>>) {
    let Some(value) = value else {
        return (Vec::new(), HashMap::new());
    };
    let mut names = Vec::new();
    let mut extras = HashMap::<String, BTreeSet<String>>::new();
    let mut depth: usize = 0;
    let mut start = 0;
    for (index, character) in value
        .char_indices()
        .chain(std::iter::once((value.len(), ',')))
    {
        match character {
            '[' => depth += 1,
            ']' => depth = depth.saturating_sub(1),
            ',' if depth == 0 => {
                let entry = value[start..index].trim();
                start = index + 1;
                if entry.is_empty() {
                    continue;
                }
                if let Some((name, raw_extras)) = entry
                    .strip_suffix(']')
                    .and_then(|entry| entry.split_once('['))
                {
                    names.push(name.to_string());
                    let requested = raw_extras
                        .split(',')
                        .map(str::trim)
                        .filter(|extra| !extra.is_empty())
                        .map(canonicalize_name)
                        .collect::<BTreeSet<_>>();
                    if !requested.is_empty() {
                        extras
                            .entry(name.to_string())
                            .or_default()
                            .extend(requested);
                    }
                } else {
                    names.push(entry.to_string());
                }
            }
            _ => {}
        }
    }
    (names, extras)
}

fn module_version(py: Python<'_>, name: &str) -> PyResult<Option<String>> {
    let module = match PyModule::import(py, name) {
        Ok(module) => module,
        Err(error) if error.is_instance_of::<PyImportError>(py) => return Ok(None),
        Err(error) => return Err(error),
    };
    let value = match module.getattr("__version__") {
        Ok(value) => value,
        Err(error) if error.is_instance_of::<PyAttributeError>(py) => return Ok(None),
        Err(error) => return Err(error),
    };
    if let Ok(version) = value.extract() {
        return Ok(Some(version));
    }
    let Ok(module) = value.cast::<PyModule>() else {
        return Ok(None);
    };
    match module.getattr("__version__") {
        Ok(value) => value.extract().map(Some),
        Err(error) if error.is_instance_of::<PyAttributeError>(py) => Ok(None),
        Err(error) => Err(error),
    }
}

fn canonicalize_pattern(pattern: &str) -> String {
    let mut result = String::new();
    for (index, part) in pattern.split('*').enumerate() {
        if index != 0 {
            result.push('*');
        }
        result.push_str(&canonicalize_name(part));
    }
    result
}
