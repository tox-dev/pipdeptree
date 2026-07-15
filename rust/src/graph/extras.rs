use std::collections::{BTreeSet, HashMap, HashSet, VecDeque};

use super::Graph;

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
        self.reverse_edges.take();
        self.cycles.take();
        self.unique_dependencies.take();
    }

    pub(super) fn collect_requested_extras(&mut self) {
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
}
