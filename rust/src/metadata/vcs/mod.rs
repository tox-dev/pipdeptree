use std::path::{Path, PathBuf};

use crate::process::ProcessRunner;

mod bzr;
mod git;
mod hg;
mod shared;
mod svn;

use shared::{VcsError, VcsResult};

type Backend = fn(&dyn ProcessRunner, &Path, &str, &Path) -> VcsResult;

pub use git::clear_root_cache;

pub(super) fn editable_requirement(
    processes: &dyn ProcessRunner,
    location: &Path,
    package: &str,
    version: &str,
) -> String {
    let mut roots: Vec<(PathBuf, Backend)> = Vec::new();
    if let Some(root) = git::root(processes, location) {
        roots.push((root, git::requirement));
    }
    if let Some(root) = hg::root(location) {
        roots.push((root, hg::requirement));
    }
    if let Some(root) = svn::root(location) {
        roots.push((root, svn::requirement));
    }
    if let Some(root) = bzr::root(location) {
        roots.push((root, bzr::requirement));
    }
    let Some((root, backend)) = innermost(roots) else {
        return format!(
            "# Editable install with no version control ({package}=={version})\n-e {}",
            location.display()
        );
    };
    format_result(
        location,
        package,
        version,
        backend(processes, location, package, &root),
    )
}

fn format_result(location: &Path, package: &str, version: &str, result: VcsResult) -> String {
    if let Some(requirement) = result.requirement {
        return format!("-e {requirement}");
    }
    let comment = match result.error {
        VcsError::NoRemote => Some(format!(
            "# Editable {} install with no remote ({package}=={version})",
            result.name.unwrap_or("VCS")
        )),
        VcsError::InvalidRemote => Some(format!(
            "# Editable {} install ({package}=={version}) with either a deleted local remote or invalid URI:",
            result.name.unwrap_or("VCS")
        )),
        VcsError::None | VcsError::CommandNotFound => None,
    };
    comment.map_or_else(
        || format!("-e {}", location.display()),
        |comment| format!("{comment}\n-e {}", location.display()),
    )
}

fn innermost(roots: Vec<(PathBuf, Backend)>) -> Option<(PathBuf, Backend)> {
    roots
        .into_iter()
        .max_by_key(|(root, _)| root.as_os_str().len())
}
