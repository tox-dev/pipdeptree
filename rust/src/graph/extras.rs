use rustc_hash::{FxHashMap as HashMap, FxHashSet as HashSet};
use std::collections::{BTreeSet, VecDeque};
use std::sync::{Arc, PoisonError};

use super::{Dependency, Graph};

impl Graph {
    pub fn apply_global_extras(&mut self, extras: &HashMap<String, BTreeSet<String>>) {
        if extras.is_empty() {
            return;
        }
        let mut pending = VecDeque::new();
        for (pattern, values) in extras {
            for index in self.matching(pattern) {
                self.global_extras
                    .entry(index)
                    .or_default()
                    .extend(values.iter().cloned());
                let node = &self.nodes[index];
                pending.extend(
                    values
                        .iter()
                        .filter_map(|extra| node.optional.get(extra))
                        .flat_map(Clone::clone)
                        .map(|slot| (index, slot)),
                );
            }
        }
        self.propagate_requested_extras(pending);
        self.expanded.take();
        self.selected
            .get_mut()
            .unwrap_or_else(PoisonError::into_inner)
            .clear();
        for dependency in self
            .nodes
            .iter_mut()
            .flat_map(|node| &mut node.dependencies)
        {
            dependency.children.take();
        }
        self.reverse_edges.take();
        self.cycles.take();
        self.unique_dependencies.take();
    }

    pub(super) fn collect_requested_extras(&mut self) {
        let mut pending = VecDeque::new();
        for (index, node) in self.nodes.iter().enumerate() {
            pending.extend(node.mandatory.clone().map(|slot| (index, slot)));
        }
        self.propagate_requested_extras(pending);
    }

    // The queue holds (node, slot) and reads the requested extras on pop: a requirement fills one
    // slot per extra activating it, so queueing the extras would hold that many copies of them.
    fn propagate_requested_extras(&mut self, mut pending: VecDeque<(usize, usize)>) {
        while let Some((parent, slot)) = pending.pop_front() {
            let dependency = &self.nodes[parent].dependencies[slot];
            let Some(index) = dependency.target else {
                continue;
            };
            let extras = dependency.requested_extras();
            if extras.is_empty() {
                continue;
            }
            let entry = self.requested_extras.entry(index).or_default();
            let new = extras.difference(entry).cloned().collect::<BTreeSet<_>>();
            entry.extend(new.iter().cloned());
            let node = &self.nodes[index];
            pending.extend(
                new.iter()
                    .filter_map(|extra| node.optional.get(extra))
                    .flat_map(Clone::clone)
                    .map(|slot| (index, slot)),
            );
        }
    }

    pub(super) fn activate_satisfied_extras(&mut self) {
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
        // Grouping the activating extras under their shared requirement checks the extras it
        // requests once; a check per activating extra would record each of them once for every
        // extra that activates the requirement.
        let mut activated = HashMap::<_, (&Dependency, Vec<_>)>::default();
        for pair in &satisfied {
            let node = &self.nodes[pair.0];
            for dependency in &node.dependencies[node.optional[&pair.1].clone()] {
                activated
                    .entry(Arc::as_ptr(&dependency.requirement))
                    .or_insert((dependency, Vec::new()))
                    .1
                    .push(pair.clone());
            }
        }
        let mut dependents = HashMap::<(usize, String), Vec<_>>::default();
        let mut unsatisfied = VecDeque::new();
        for (requirement, (dependency, _)) in &activated {
            let Some(target) = dependency.target else {
                unsatisfied.push_back(*requirement);
                continue;
            };
            for extra in dependency.requested_extras() {
                let required = (target, extra);
                if satisfied.contains(&required) {
                    dependents.entry(required).or_default().push(*requirement);
                } else {
                    unsatisfied.push_back(*requirement);
                }
            }
        }
        while let Some(requirement) = unsatisfied.pop_front() {
            for pair in activated
                .remove(&requirement)
                .into_iter()
                .flat_map(|(_, pairs)| pairs)
            {
                if satisfied.remove(&pair) {
                    unsatisfied.extend(dependents.remove(&pair).into_iter().flatten());
                }
            }
        }
        for (index, extra) in satisfied {
            self.global_extras.entry(index).or_default().insert(extra);
        }
    }
}
