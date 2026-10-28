use std::fs;
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
        let commit = match required_command(processes, &["parents", "--template={node}"], root) {
            Ok(commit) => commit,
            Err(error) => return VcsResult::error(Some("hg"), error),
        };
        let Some(remote) = default_path(root).map(normalize_local_remote) else {
            return VcsResult::error(Some("hg"), VcsError::NoRemote);
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

// hg runs with HGRCSKIPREPO (see `command`), so the remote is read here as data; a linked hgrc and
// `%include` are not followed, and the last assignment wins as in hg.
fn default_path(root: &Path) -> Option<String> {
    let hgrc = root.join(".hg/hgrc");
    if !fs::symlink_metadata(&hgrc).is_ok_and(|metadata| metadata.is_file()) {
        return None;
    }
    let content = fs::read_to_string(hgrc).ok()?;
    let mut in_paths = false;
    let mut remote = None;
    for line in content.lines() {
        if let Some((section, _)) = line.strip_prefix('[').and_then(|rest| rest.split_once(']')) {
            in_paths = section == "paths";
        } else if in_paths
            && let Some((name, value)) = line.split_once('=')
            && name.trim_end() == "default"
        {
            remote = Some(value.trim().to_string());
        }
    }
    remote.filter(|remote| !remote.is_empty())
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
