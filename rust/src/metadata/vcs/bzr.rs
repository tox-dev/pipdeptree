use std::path::Path;

use crate::process::ProcessRunner;

use super::shared::{
    CommandError, ExitStatusPolicy, VcsError, VcsRequirement, VcsResult, build_requirement,
    canonical_or_original, command, local_path, marker_root, path_url,
};

pub(super) fn root(location: &Path) -> Option<std::path::PathBuf> {
    marker_root(location, ".bzr", true)
}

pub(super) fn requirement(
    processes: &dyn ProcessRunner,
    location: &Path,
    package: &str,
    root: &Path,
) -> VcsResult {
    let remote = match command(
        processes,
        "bzr",
        &["info"],
        root,
        ExitStatusPolicy::RequireSuccess,
    ) {
        Ok(output) => parse_remote(&output),
        Err(CommandError::Failed) => None,
        Err(CommandError::NotFound) => {
            return VcsResult::error(Some("bzr"), VcsError::CommandNotFound);
        }
    };
    let Some(remote) = remote else {
        return VcsResult::error(Some("bzr"), VcsError::NoRemote);
    };
    let remote = if local_path(&remote) {
        path_url(&canonical_or_original(&remote)).unwrap_or(remote)
    } else {
        remote
    };
    let revision = match command(
        processes,
        "bzr",
        &["revno"],
        root,
        ExitStatusPolicy::RequireSuccess,
    ) {
        Ok(output) => match output.lines().next_back().map(str::trim) {
            Some(value) if !value.is_empty() => Some(value.to_owned()),
            _ => None,
        },
        Err(CommandError::Failed) => None,
        Err(CommandError::NotFound) => {
            return VcsResult::error(Some("bzr"), VcsError::CommandNotFound);
        }
    };
    let Some(revision) = revision else {
        return VcsResult::error(Some("bzr"), VcsError::NoRemote);
    };
    build_requirement(VcsRequirement {
        vcs: "bzr",
        remote: &remote,
        commit: &revision,
        package,
        location,
        root,
        always_prefix: false,
        include_subdirectory: false,
    })
}

fn parse_remote(output: &str) -> Option<String> {
    output.lines().find_map(|line| {
        let line = line.trim();
        ["checkout of branch: ", "parent branch: "]
            .iter()
            .find_map(|prefix| line.strip_prefix(prefix))
            .map(str::trim)
            .filter(|value| !value.is_empty())
            .map(ToOwned::to_owned)
    })
}
