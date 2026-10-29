use std::cell::Cell;
use std::path::{Path, PathBuf};
use std::time::Duration;

use crate::metadata::direct_url::redact_url;
use crate::process::{ProcessError, ProcessRequest, ProcessRunner};

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub(super) enum VcsError {
    None,
    NoRemote,
    InvalidRemote,
    CommandNotFound,
    TimedOut,
}

#[derive(Debug, Eq, PartialEq)]
pub(super) struct VcsResult {
    pub(super) requirement: Option<String>,
    pub(super) name: Option<&'static str>,
    pub(super) error: VcsError,
}

#[derive(Clone, Copy)]
pub(super) struct VcsRequirement<'a> {
    pub(super) vcs: &'static str,
    pub(super) remote: &'a str,
    pub(super) commit: &'a str,
    pub(super) package: &'a str,
    pub(super) location: &'a Path,
    pub(super) root: &'a Path,
    pub(super) always_prefix: bool,
    pub(super) include_subdirectory: bool,
}

#[derive(Clone, Copy, Debug)]
pub(super) enum CommandError {
    NotFound,
    Failed,
    TimedOut,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub(super) enum ExitStatusPolicy {
    Ignore,
    RequireSuccess,
}

impl VcsResult {
    pub(super) const fn error(name: Option<&'static str>, error: VcsError) -> Self {
        Self {
            requirement: None,
            name,
            error,
        }
    }
}

impl From<CommandError> for VcsError {
    fn from(error: CommandError) -> Self {
        match error {
            CommandError::NotFound => Self::CommandNotFound,
            CommandError::Failed => Self::NoRemote,
            CommandError::TimedOut => Self::TimedOut,
        }
    }
}

// Every editable record can point at the same stalled repository, so a run spends at most this long
// on commands that time out; once it is gone, later commands time out without starting.
const STALL_BUDGET: Duration = Duration::from_secs(10);

thread_local! {
    static STALL_REMAINING: Cell<Duration> = const { Cell::new(STALL_BUDGET) };
}

pub(super) fn reset_stall_budget() {
    STALL_REMAINING.set(STALL_BUDGET);
}

pub(super) fn command(
    processes: &dyn ProcessRunner,
    program: &str,
    args: &[&str],
    cwd: &Path,
    status: ExitStatusPolicy,
) -> Result<String, CommandError> {
    let timeout = STALL_REMAINING.get().min(Duration::from_secs(5));
    if timeout.is_zero() {
        return Err(CommandError::TimedOut);
    }
    let mut request = ProcessRequest::new(program, args.iter().copied())
        .in_directory(cwd)
        .with_timeout(timeout)
        .with_output_limit(1 << 20);
    if program == "git" {
        request = request.without_environment(["GIT_DIR", "GIT_WORK_TREE"]);
    }
    if program == "hg" {
        // The repository root comes from package metadata, and its hgrc can define hooks, shell
        // aliases and extensions that hg would run for any command; hg.rs reads the file as data.
        request = request.with_environment([("HGRCSKIPREPO", "1")]);
    }
    let output = processes.run(&request).map_err(|error| match error {
        ProcessError::NotFound => CommandError::NotFound,
        ProcessError::Failed(_) => CommandError::Failed,
        ProcessError::TimedOut => {
            STALL_REMAINING.set(STALL_REMAINING.get().saturating_sub(timeout));
            CommandError::TimedOut
        }
    })?;
    if status == ExitStatusPolicy::RequireSuccess && !output.success {
        return Err(CommandError::Failed);
    }
    String::from_utf8(output.stdout)
        .map(|value| value.trim().to_string())
        .map_err(|_| CommandError::Failed)
}

pub(super) fn build_requirement(input: VcsRequirement<'_>) -> VcsResult {
    let remote = redact_url(input.remote, input.vcs == "git");
    let remote = if input.always_prefix
        || !remote
            .to_ascii_lowercase()
            .starts_with(&format!("{}:", input.vcs))
    {
        format!("{}+{remote}", input.vcs)
    } else {
        remote
    };
    let mut requirement = format!(
        "{remote}@{}#egg={}",
        quote_commit(input.commit),
        input.package.replace('-', "_")
    );
    if input.include_subdirectory
        && let Some(subdirectory) = project_subdirectory(input.location, input.root)
    {
        requirement.push_str("&subdirectory=");
        requirement.push_str(&subdirectory);
    }
    VcsResult {
        requirement: Some(requirement),
        name: Some(input.vcs),
        error: VcsError::None,
    }
}

pub(super) fn marker_root(location: &Path, marker: &str, directory_only: bool) -> Option<PathBuf> {
    let mut current = location.canonicalize().ok()?;
    loop {
        let candidate = current.join(marker);
        if if directory_only {
            candidate.is_dir()
        } else {
            candidate.exists()
        } {
            return Some(current);
        }
        if !current.pop() {
            return None;
        }
    }
}

pub(super) fn local_path(value: &str) -> bool {
    Path::new(value).is_absolute()
        || (value.as_bytes().get(1) == Some(&b':')
            && value
                .as_bytes()
                .first()
                .is_some_and(u8::is_ascii_alphabetic))
}

pub(super) fn path_url(path: &Path) -> Option<String> {
    url::Url::from_file_path(path).ok().map(Into::into)
}

// hg and bzr both report on-disk remotes as bare paths; turn those into file URLs while leaving
// already-remote URLs untouched. The inspected repository chooses the path, so it stays unresolved.
pub(super) fn normalize_local_remote(remote: String) -> String {
    if local_path(&remote) {
        path_url(Path::new(&remote)).unwrap_or(remote)
    } else {
        remote
    }
}

fn project_subdirectory(location: &Path, root: &Path) -> Option<String> {
    let mut current = location.canonicalize().ok()?;
    let root = root.canonicalize().ok()?;
    while !installable(&current) {
        if !current.pop() {
            return None;
        }
    }
    if current == root {
        return None;
    }
    current
        .strip_prefix(root)
        .ok()
        .map(|path| path.to_string_lossy().into_owned())
}

fn installable(path: &Path) -> bool {
    path.is_dir()
        && ["pyproject.toml", "setup.py"]
            .iter()
            .any(|name| path.join(name).is_file())
}

fn quote_commit(value: &str) -> String {
    value
        .bytes()
        .flat_map(|byte| {
            if byte.is_ascii_alphanumeric() || matches!(byte, b'-' | b'.' | b'_' | b'~' | b'/') {
                vec![char::from(byte)]
            } else {
                format!("%{byte:02X}").chars().collect()
            }
        })
        .collect()
}
