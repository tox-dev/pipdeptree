use std::path::Path;

use crate::process::ProcessRunner;

use super::shared::{
    CommandError, ExitStatusPolicy, VcsError, VcsRequirement, VcsResult, build_requirement,
    canonical_or_original, command, local_path, marker_root, path_url,
};

pub(super) fn root(location: &Path) -> Option<std::path::PathBuf> {
    marker_root(location, ".hg", false)
}

pub(super) fn requirement(
    processes: &dyn ProcessRunner,
    location: &Path,
    package: &str,
    root: &Path,
) -> VcsResult {
    let remote = match required_command(processes, &["showconfig", "paths.default"], root) {
        Ok(remote) => remote,
        Err(error) => return VcsResult::error(Some("hg"), error),
    };
    let remote = if local_path(&remote) {
        path_url(&canonical_or_original(&remote)).unwrap_or(remote)
    } else {
        remote
    };
    let commit = match required_command(processes, &["parents", "--template={node}"], root) {
        Ok(commit) => commit,
        Err(error) => return VcsResult::error(Some("hg"), error),
    };
    build_requirement(VcsRequirement {
        vcs: "hg",
        remote: &remote,
        commit: &commit,
        package,
        location,
        root,
        always_prefix: false,
        include_subdirectory: true,
    })
}

fn required_command(
    processes: &dyn ProcessRunner,
    args: &[&str],
    root: &Path,
) -> Result<String, VcsError> {
    match command(
        processes,
        "hg",
        args,
        root,
        ExitStatusPolicy::RequireSuccess,
    ) {
        Ok(value) if !value.is_empty() => Ok(value),
        Ok(_) | Err(CommandError::Failed) => Err(VcsError::NoRemote),
        Err(CommandError::NotFound) => Err(VcsError::CommandNotFound),
    }
}
