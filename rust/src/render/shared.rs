use crate::graph::Dependency;

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
