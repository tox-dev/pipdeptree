use std::collections::BTreeSet;

use crate::graph::{Dependency, Graph};

pub(super) fn edge_label(dependency: &Dependency) -> String {
    let version = dependency
        .version_spec()
        .unwrap_or_else(|| "any".to_string());
    dependency
        .activating_extras()
        .map_or_else(|| version.clone(), |extra| format!("[{extra}] {version}"))
}

// The text and JSON trees both label an unconstrained requirement "Any" (distinct from the
// lowercase "any" the graph formats use on edges).
pub(super) fn required_version(dependency: &Dependency) -> String {
    dependency
        .version_spec()
        .unwrap_or_else(|| "Any".to_string())
}

// A globally selected parent extra makes that parent reachable outside the reverse chain.
pub(super) fn reverse_required_extras(
    graph: &Graph,
    parent: usize,
    dependency: &Dependency,
) -> Option<BTreeSet<String>> {
    let extras: BTreeSet<String> = dependency.declaration.as_ref().map_or_else(
        || dependency.activated_by.iter().cloned().collect(),
        |declaration| {
            declaration
                .required_for_parent_extras
                .iter()
                .cloned()
                .collect()
        },
    );
    (!extras.is_empty()
        && !extras
            .iter()
            .any(|extra| graph.extra_is_global(parent, extra)))
    .then_some(extras)
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
