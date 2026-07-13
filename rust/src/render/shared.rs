use std::collections::BTreeSet;

use crate::graph::{Dependency, Graph};

pub(super) fn unique_dependencies(graph: &Graph, index: usize) -> BTreeSet<usize> {
    let mut parent_counts = graph.parent_counts().to_vec();
    let mut removed = BTreeSet::from([index]);
    let mut stack = vec![index];
    while let Some(parent) = stack.pop() {
        for child in graph
            .expanded_children(parent)
            .filter_map(|dependency| dependency.target)
        {
            parent_counts[child] = parent_counts[child].saturating_sub(1);
            if parent_counts[child] == 0 && removed.insert(child) {
                stack.push(child);
            }
        }
    }
    removed.remove(&index);
    removed
}

pub(super) fn edge_label(dependency: &Dependency) -> String {
    let version = dependency
        .version_spec()
        .unwrap_or_else(|| "any".to_string());
    dependency
        .activated_by
        .as_ref()
        .map_or_else(|| version.clone(), |extra| format!("[{extra}] {version}"))
}

pub(super) fn format_size(bytes: u64) -> String {
    if bytes < 1024 {
        return format!("{bytes} B");
    }
    let bytes = u128::from(bytes);
    let mut divisor = 1024_u128;
    for unit in ["KB", "MB"] {
        if bytes < divisor * 1024 {
            let tenths = (bytes * 10 + divisor / 2) / divisor;
            return format!("{}.{:01} {unit}", tenths / 10, tenths % 10);
        }
        divisor *= 1024;
    }
    let tenths = (bytes * 10 + divisor / 2) / divisor;
    format!("{}.{:01} GB", tenths / 10, tenths % 10)
}
