use std::collections::{BTreeMap, BTreeSet, HashMap, HashSet, VecDeque};

use glob::Pattern;

use crate::metadata::canonicalize_name;
use crate::options::Options;

use super::{Dependency, FilterError, Graph};

pub struct FilterSpec {
    include: Vec<String>,
    exclude: Vec<String>,
    reverse: bool,
    exclude_dependencies: bool,
}

impl FilterSpec {
    // Parse the CLI package selectors once: the include/exclude patterns plus the name[extra] map
    // that global-extra activation consumes, so the same string is not re-parsed per phase.
    pub fn from_options(options: &Options) -> (Self, HashMap<String, BTreeSet<String>>) {
        let (include, extras) = parse_packages(options.packages.as_deref());
        let exclude = options
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
        let spec = Self {
            include,
            exclude,
            reverse: options.reverse,
            exclude_dependencies: options.exclude_dependencies,
        };
        (spec, extras)
    }
}

impl Graph {
    pub fn apply_filters(&mut self, spec: &FilterSpec) -> Result<(), FilterError> {
        // The expanded, reverse-edge and unique caches depend on extras, not visibility; only
        // the cycle components change when filters hide nodes.
        self.cycles.take();
        let canonical_excludes = spec
            .exclude
            .iter()
            .map(|pattern| canonicalize_name(pattern))
            .collect::<HashSet<_>>();
        if spec
            .include
            .iter()
            .map(|pattern| canonicalize_name(pattern))
            .any(|pattern| canonical_excludes.contains(&pattern))
        {
            return Err(FilterError::Overlap);
        }
        // Reverse mode renders uninstalled requirements as roots, so a pattern may legitimately
        // name one; its dependents carry the subtree.
        let missing_names = if spec.reverse {
            self.missing_dependents()
        } else {
            BTreeMap::new()
        };
        let mut include_matches = HashSet::new();
        let unmatched = spec
            .include
            .iter()
            .filter_map(|pattern| {
                let mut matched = self.matching(pattern);
                if let Some(parents) = matching_missing(&missing_names, pattern) {
                    matched.extend(parents);
                }
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
        let exclude_matches = self.matching_many(&spec.exclude);
        if !spec.include.is_empty() {
            let mut included = vec![false; self.nodes.len()];
            self.mark_into(&include_matches, spec.reverse, &mut included);
            self.visible = included;
        }
        if spec.exclude_dependencies {
            let mut excluded = vec![false; self.nodes.len()];
            self.mark_excluded_dependencies(&exclude_matches, spec.reverse, &mut excluded);
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

    pub(super) fn matching(&self, pattern: &str) -> Vec<usize> {
        let pattern = canonicalize_name(pattern);
        let Ok(pattern) = Pattern::new(&pattern) else {
            return Vec::new();
        };
        self.nodes
            .iter()
            .enumerate()
            .filter_map(|(index, node)| pattern.matches(&node.package.key).then_some(index))
            .collect()
    }

    fn matching_many(&self, patterns: &[String]) -> HashSet<usize> {
        patterns
            .iter()
            .flat_map(|pattern| self.matching(pattern))
            .collect()
    }

    // A dependency leaves the tree only when every package needing it is itself excluded.
    fn mark_excluded_dependencies(
        &self,
        seeds: &HashSet<usize>,
        reverse: bool,
        marked: &mut [bool],
    ) {
        let mut forward = vec![Vec::new(); self.nodes.len()];
        let mut backward = vec![Vec::new(); self.nodes.len()];
        for (parent, edges) in forward.iter_mut().enumerate() {
            for target in self.active_targets(parent) {
                edges.push(target);
                backward[target].push(parent);
            }
        }
        if reverse {
            std::mem::swap(&mut forward, &mut backward);
        }
        for seed in seeds {
            marked[*seed] = true;
        }
        let mut queue = seeds.iter().copied().collect::<VecDeque<_>>();
        while let Some(index) = queue.pop_front() {
            for candidate in &forward[index] {
                if !marked[*candidate] && backward[*candidate].iter().all(|holder| marked[*holder])
                {
                    marked[*candidate] = true;
                    queue.push_back(*candidate);
                }
            }
        }
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
}

fn parse_packages(value: Option<&str>) -> (Vec<String>, HashMap<String, BTreeSet<String>>) {
    let Some(value) = value else {
        return (Vec::new(), HashMap::new());
    };
    // An unbalanced '[' would swallow the terminating sentinel and silently drop every pattern.
    let value = if value.matches('[').count() == value.matches(']').count() {
        value
    } else {
        return (vec![value.trim().to_string()], HashMap::new());
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

fn matching_missing(
    missing: &BTreeMap<&str, Vec<(usize, &Dependency)>>,
    pattern: &str,
) -> Option<Vec<usize>> {
    let pattern = Pattern::new(&canonicalize_name(pattern)).ok()?;
    let matched = missing
        .iter()
        .filter(|(name, _)| pattern.matches(&canonicalize_name(name)))
        .flat_map(|(_, parents)| parents.iter().map(|(parent, _)| *parent))
        .collect::<Vec<_>>();
    (!matched.is_empty()).then_some(matched)
}
