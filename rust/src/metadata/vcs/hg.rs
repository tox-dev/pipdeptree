use std::path::Path;

use crate::process::ProcessRunner;

use super::shared::{
    CommandError, ExitStatusPolicy, VcsError, VcsRequirement, VcsResult, build_requirement,
    command, marker_root, normalize_local_remote,
};

pub(super) struct Hg;

impl super::Vcs for Hg {
    fn root(&self, _processes: &dyn ProcessRunner, location: &Path) -> Option<std::path::PathBuf> {
        marker_root(location, ".hg", false)
    }

    fn requirement(
        &self,
        processes: &dyn ProcessRunner,
        location: &Path,
        package: &str,
        root: &Path,
    ) -> VcsResult {
        let remote = match required_command(processes, &["showconfig", "paths.default"], root) {
            Ok(remote) => normalize_local_remote(remote),
            Err(error) => return VcsResult::error(Some("hg"), error),
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
