use std::fs;
use std::path::Path;

use crate::metadata::read_bounded;
use crate::process::ProcessRunner;

use super::shared::{
    ExitStatusPolicy, VcsError, VcsRequirement, VcsResult, build_requirement, command, marker_root,
    normalize_local_remote,
};

pub(super) struct Hg;

impl super::Vcs for Hg {
    fn root(
        &self,
        _processes: &dyn ProcessRunner,
        location: &Path,
    ) -> Result<Option<std::path::PathBuf>, VcsError> {
        Ok(marker_root(location, ".hg", false))
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

// hg runs with HGRCSKIPREPO (see `command`), so this reads the remote as data. It follows neither a
// linked .hg or hgrc nor `%include`, and the last assignment wins as in hg.
fn default_path(root: &Path) -> Option<String> {
    let store = root.join(".hg");
    let hgrc = store.join("hgrc");
    (fs::symlink_metadata(&store).ok()?.is_dir() && fs::symlink_metadata(&hgrc).ok()?.is_file())
        .then_some(())?;
    let content = read_bounded(&hgrc).ok()?;
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
        Ok(_) => Err(VcsError::NoRemote),
        Err(error) => Err(error.into()),
    }
}
