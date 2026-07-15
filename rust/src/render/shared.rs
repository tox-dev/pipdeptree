use crate::graph::{Dependency, Graph};

pub(super) fn edge_label(dependency: &Dependency) -> String {
    let version = dependency
        .version_spec()
        .unwrap_or_else(|| "any".to_string());
    dependency
        .activated_by
        .as_ref()
        .map_or_else(|| version.clone(), |extra| format!("[{extra}] {version}"))
}

// The text and JSON trees both label an unconstrained requirement "Any" (distinct from the
// lowercase "any" the graph formats use on edges).
pub(super) fn required_version(dependency: &Dependency) -> String {
    dependency
        .version_spec()
        .unwrap_or_else(|| "Any".to_string())
}

// A reverse edge keeps recursing under the extra that pulled it in, unless that extra was requested
// globally (via --packages name[extra]) and so is not part of this specific chain.
pub(super) fn reverse_required_extra<'a>(
    graph: &Graph,
    parent: usize,
    dependency: &'a Dependency,
) -> Option<&'a str> {
    dependency
        .activated_by
        .as_deref()
        .filter(|extra| !graph.extra_is_global(parent, extra))
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
