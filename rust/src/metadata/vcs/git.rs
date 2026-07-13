use std::path::{Path, PathBuf};

use crate::process::ProcessRunner;

use super::shared::{
    CommandError, ExitStatusPolicy, VcsError, VcsRequirement, VcsResult, build_requirement,
    command, local_path, path_url,
};

pub(super) fn root(processes: &dyn ProcessRunner, location: &Path) -> Option<PathBuf> {
    command(
        processes,
        "git",
        &["rev-parse", "--show-toplevel"],
        location,
        ExitStatusPolicy::RequireSuccess,
    )
    .ok()
    .filter(|value| !value.is_empty())
    .map(PathBuf::from)
}

pub(super) fn requirement(
    processes: &dyn ProcessRunner,
    location: &Path,
    package: &str,
    root: &Path,
) -> VcsResult {
    let remote = match remote(processes, root) {
        Ok(Some(remote)) => remote,
        Ok(None) | Err(CommandError::Failed) => {
            return VcsResult::error(Some("git"), VcsError::NoRemote);
        }
        Err(CommandError::NotFound) => {
            return VcsResult::error(Some("git"), VcsError::CommandNotFound);
        }
    };
    let commit = match command(
        processes,
        "git",
        &["rev-parse", "HEAD"],
        root,
        ExitStatusPolicy::RequireSuccess,
    ) {
        Ok(commit) if !commit.is_empty() => commit,
        Ok(_) | Err(CommandError::Failed) => {
            return VcsResult::error(Some("git"), VcsError::NoRemote);
        }
        Err(CommandError::NotFound) => {
            return VcsResult::error(Some("git"), VcsError::CommandNotFound);
        }
    };
    let Some(remote) = normalize_remote(&remote, root) else {
        return VcsResult::error(Some("git"), VcsError::InvalidRemote);
    };
    build_requirement(VcsRequirement {
        vcs: "git",
        remote: &remote,
        commit: &commit,
        package,
        location,
        root,
        always_prefix: true,
        include_subdirectory: true,
    })
}

fn remote(processes: &dyn ProcessRunner, root: &Path) -> Result<Option<String>, CommandError> {
    let output = command(
        processes,
        "git",
        &["config", "--get-regexp", r"remote\..*\.url"],
        root,
        ExitStatusPolicy::Ignore,
    )?;
    let lines = output.lines().collect::<Vec<_>>();
    let selected = lines
        .iter()
        .find(|line| line.starts_with("remote.origin.url "))
        .or_else(|| lines.first());
    Ok(selected
        .and_then(|line| line.split_once(' '))
        .map(|(_, value)| value.trim().to_string())
        .filter(|value| !value.is_empty()))
}

fn normalize_remote(value: &str, root: &Path) -> Option<String> {
    if value.contains("://") {
        return Some(value.to_string());
    }
    let path = if local_path(value) {
        PathBuf::from(value)
    } else {
        root.join(value)
    };
    if path.exists() {
        return path.canonicalize().ok().as_deref().and_then(path_url);
    }
    scp_remote(value)
}

fn scp_remote(value: &str) -> Option<String> {
    let (host, path) = value.split_once(':')?;
    if host.contains(['/', ':'])
        || path.is_empty()
        || !path.as_bytes()[0].is_ascii_alphanumeric()
        || path.contains(':')
    {
        return None;
    }
    let valid_host = host.split_once('@').map_or_else(
        || !host.is_empty(),
        |(user, hostname)| {
            !user.is_empty()
                && user
                    .chars()
                    .all(|character| character.is_ascii_alphanumeric() || character == '_')
                && !hostname.is_empty()
        },
    );
    valid_host.then(|| format!("ssh://{host}/{path}"))
}
