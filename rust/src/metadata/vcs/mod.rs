use std::path::{Path, PathBuf};

use crate::process::ProcessRunner;

mod bzr;
mod git;
mod hg;
mod shared;
mod svn;

use shared::{VcsError, VcsResult};

// One backend per supported VCS. Adding a system means adding its module and one entry here; the
// dispatch, cache reset, and innermost-root selection all iterate this slice.
trait Vcs {
    fn root(&self, processes: &dyn ProcessRunner, location: &Path) -> Option<PathBuf>;
    fn requirement(
        &self,
        processes: &dyn ProcessRunner,
        location: &Path,
        package: &str,
        root: &Path,
    ) -> VcsResult;
    // Per-run caches keyed by repository root; only backends that resolve shared state override it.
    fn reset_cache(&self) {}
}

const BACKENDS: &[&dyn Vcs] = &[&git::Git, &hg::Hg, &svn::Svn, &bzr::Bzr];

pub fn reset_caches() {
    for backend in BACKENDS {
        backend.reset_cache();
    }
}

pub(super) fn editable_requirement(
    processes: &dyn ProcessRunner,
    location: &Path,
    package: &str,
    version: &str,
) -> String {
    let roots = BACKENDS
        .iter()
        .filter_map(|backend| Some((backend.root(processes, location)?, *backend)))
        .collect::<Vec<_>>();
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
        backend.requirement(processes, location, package, &root),
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

fn innermost(roots: Vec<(PathBuf, &dyn Vcs)>) -> Option<(PathBuf, &dyn Vcs)> {
    roots
        .into_iter()
        .max_by_key(|(root, _)| root.as_os_str().len())
}
