use std::path::{Path, PathBuf};

use crate::process::ProcessRunner;

mod bzr;
mod git;
mod hg;
mod shared;
mod svn;

use super::requirement_url;
use shared::{VcsError, VcsResult, path_url, reset_stall_budget};

// One backend per supported VCS. Adding a system means adding its module and one entry here; the
// dispatch, cache reset, and innermost-root selection all iterate this slice.
trait Vcs {
    fn root(
        &self,
        processes: &dyn ProcessRunner,
        location: &Path,
    ) -> Result<Option<PathBuf>, VcsError>;
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
    reset_stall_budget();
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
    // A timed-out root lookup leaves the other backends free to find the checkout.
    let mut root_error = None;
    let roots = BACKENDS
        .iter()
        .filter_map(|backend| match backend.root(processes, location) {
            Ok(root) => Some((root?, *backend)),
            Err(error) => {
                root_error = Some(error);
                None
            }
        })
        .collect::<Vec<_>>();
    let Some((root, backend)) = innermost(roots) else {
        if let Some(error) = root_error {
            return format_result(location, package, version, VcsResult::error(None, error));
        }
        return format!(
            "# Editable install with no version control ({package}=={version})\n-e {}",
            requirement_location(location)
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
        return format!("-e {}", requirement_url(&requirement));
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
        VcsError::TimedOut => Some(format!(
            "# Editable {} install whose lookup timed out ({package}=={version})",
            result.name.unwrap_or("VCS")
        )),
        VcsError::None | VcsError::CommandNotFound => None,
    };
    let location = requirement_location(location);
    comment.map_or_else(
        || format!("-e {location}"),
        |comment| format!("{comment}\n-e {location}"),
    )
}

// pip decodes a file URL back to the path, so a location that needs encoding becomes one. pip splits
// an option line with POSIX shlex, which drops every backslash and with it each Windows path
// separator (pypa/pip#10121), so a location holding one becomes a URL too. A legacy link may name a
// relative target, which the link lookup resolved against the working directory.
fn requirement_location(location: &Path) -> String {
    let display = location.display().to_string();
    let encoded = requirement_url(&display);
    if encoded == display && !display.contains('\\') {
        return display;
    }
    std::path::absolute(location)
        .ok()
        .and_then(|path| path_url(&path))
        .unwrap_or(encoded)
}

fn innermost(roots: Vec<(PathBuf, &dyn Vcs)>) -> Option<(PathBuf, &dyn Vcs)> {
    roots
        .into_iter()
        .max_by_key(|(root, _)| root.as_os_str().len())
}
