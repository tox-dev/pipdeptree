use std::ffi::OsString;
use std::io::{self, Read, Write as _};
use std::path::PathBuf;
use std::process::{Child, Command, ExitStatus, Stdio};
use std::thread::{self, JoinHandle};
use std::time::{Duration, Instant};

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct ProcessRequest {
    pub program: OsString,
    pub args: Vec<OsString>,
    pub current_dir: Option<PathBuf>,
    pub stdin: Vec<u8>,
    pub timeout: Option<Duration>,
    pub output_limit: u64,
    pub removed_environment: Vec<OsString>,
    pub added_environment: Vec<(OsString, OsString)>,
}

impl ProcessRequest {
    pub fn new(
        program: impl Into<OsString>,
        args: impl IntoIterator<Item = impl Into<OsString>>,
    ) -> Self {
        Self {
            program: program.into(),
            args: args.into_iter().map(Into::into).collect(),
            current_dir: None,
            stdin: Vec::new(),
            timeout: None,
            output_limit: u64::MAX,
            removed_environment: Vec::new(),
            added_environment: Vec::new(),
        }
    }

    #[must_use]
    pub fn in_directory(mut self, path: impl Into<PathBuf>) -> Self {
        self.current_dir = Some(path.into());
        self
    }

    #[must_use]
    pub fn with_stdin(mut self, stdin: impl Into<Vec<u8>>) -> Self {
        self.stdin = stdin.into();
        self
    }

    #[must_use]
    pub const fn with_timeout(mut self, timeout: Duration) -> Self {
        self.timeout = Some(timeout);
        self
    }

    #[must_use]
    pub const fn with_output_limit(mut self, bytes: u64) -> Self {
        self.output_limit = bytes;
        self
    }

    #[must_use]
    pub fn without_environment(
        mut self,
        names: impl IntoIterator<Item = impl Into<OsString>>,
    ) -> Self {
        self.removed_environment = names.into_iter().map(Into::into).collect();
        self
    }

    #[must_use]
    pub fn with_environment(
        mut self,
        variables: impl IntoIterator<Item = (impl Into<OsString>, impl Into<OsString>)>,
    ) -> Self {
        self.added_environment = variables
            .into_iter()
            .map(|(name, value)| (name.into(), value.into()))
            .collect();
        self
    }
}

#[derive(Debug, Eq, PartialEq)]
pub struct ProcessOutput {
    pub success: bool,
    pub stdout: Vec<u8>,
    pub stderr: Vec<u8>,
}

#[derive(Debug, Eq, PartialEq, thiserror::Error)]
pub enum ProcessError {
    #[error("command not found")]
    NotFound,
    #[error("{0}")]
    Failed(String),
    #[error("command timed out")]
    TimedOut,
}

pub trait ProcessRunner {
    /// # Errors
    ///
    /// Returns `NotFound` for a missing executable, `TimedOut` after the requested deadline, and `Failed` for other
    /// operating-system errors.
    fn run(&self, request: &ProcessRequest) -> Result<ProcessOutput, ProcessError>;
}

#[derive(Clone, Copy, Debug, Default)]
pub struct SystemProcessRunner;

impl ProcessRunner for SystemProcessRunner {
    fn run(&self, request: &ProcessRequest) -> Result<ProcessOutput, ProcessError> {
        #[cfg(unix)]
        let mut command = Command::new(resolve_program(request)?);
        // Windows searches PATH in the parent, before the child changes directory.
        #[cfg(not(unix))]
        let mut command = Command::new(&request.program);
        command
            .args(&request.args)
            .stdin(if request.stdin.is_empty() {
                Stdio::null()
            } else {
                Stdio::piped()
            })
            .stdout(Stdio::piped())
            .stderr(Stdio::piped());
        for name in &request.removed_environment {
            command.env_remove(name);
        }
        for (name, value) in &request.added_environment {
            command.env(name, value);
        }
        if let Some(path) = &request.current_dir {
            command.current_dir(path);
        }
        let mut child = command.spawn()?;
        let deadline = request.timeout.map(|timeout| Instant::now() + timeout);
        if !request.stdin.is_empty() {
            let mut stdin = child.stdin.take().expect("piped process stdin exists");
            let input = request.stdin.clone();
            // The exit status is authoritative: dot stops reading stdin once the graph parses, so
            // a write error to a finished child is not a failure.
            thread::spawn(move || stdin.write_all(&input));
        }
        let stdout = child.stdout.take().expect("piped process stdout exists");
        let limit = request.output_limit;
        let stdout = thread::spawn(move || read_output(stdout, limit));
        let stderr = child.stderr.take().expect("piped process stderr exists");
        let stderr = thread::spawn(move || read_output(stderr, limit));
        let status = wait(&mut child, deadline)?;
        Ok(ProcessOutput {
            success: status.success(),
            stdout: collect(stdout, deadline)?,
            stderr: collect(stderr, deadline)?,
        })
    }
}

// Returning at the limit closes the pipe, so a child that keeps writing gets a broken pipe and exits
// instead of filling memory or running until its timeout.
fn read_output(pipe: impl Read, limit: u64) -> io::Result<Vec<u8>> {
    let mut output = Vec::new();
    pipe.take(limit.saturating_add(1))
        .read_to_end(&mut output)?;
    if output.len() as u64 > limit {
        return Err(io::Error::other(format!("output exceeds {limit} bytes")));
    }
    Ok(output)
}

// A Unix child searches PATH after it changes into current_dir, so an empty or relative PATH entry
// would find a program inside that directory. Search from pipdeptree's own directory instead.
#[cfg(unix)]
fn resolve_program(request: &ProcessRequest) -> Result<PathBuf, ProcessError> {
    use std::env;
    use std::os::unix::ffi::OsStrExt as _;
    use std::os::unix::fs::PermissionsExt as _;
    use std::path;

    let search = env::var_os("PATH")
        .filter(|_| request.current_dir.is_some() && !request.program.as_bytes().contains(&b'/'));
    let Some(search) = search else {
        return Ok(PathBuf::from(&request.program));
    };
    env::split_paths(&search)
        .filter_map(|entry| path::absolute(entry.join(&request.program)).ok())
        .find(|candidate| {
            candidate.metadata().is_ok_and(|metadata| {
                metadata.is_file() && metadata.permissions().mode() & 0o111 != 0
            })
        })
        .ok_or(ProcessError::NotFound)
}

fn wait(child: &mut Child, deadline: Option<Instant>) -> Result<ExitStatus, ProcessError> {
    let Some(deadline) = deadline else {
        return Ok(child.wait()?);
    };
    loop {
        match child.try_wait()? {
            Some(status) => return Ok(status),
            None if Instant::now() >= deadline => {
                child.kill()?;
                child.wait()?;
                return Err(ProcessError::TimedOut);
            }
            None => thread::sleep(Duration::from_millis(10)),
        }
    }
}

// A process the child started inherits its pipes and can hold them open after the child exits, so
// stop waiting for the readers at the deadline and let them finish in the background.
fn collect(
    reader: JoinHandle<io::Result<Vec<u8>>>,
    deadline: Option<Instant>,
) -> Result<Vec<u8>, ProcessError> {
    if let Some(deadline) = deadline {
        while !reader.is_finished() {
            if Instant::now() >= deadline {
                return Err(ProcessError::TimedOut);
            }
            thread::sleep(Duration::from_millis(10));
        }
    }
    Ok(reader
        .join()
        .expect("process output reader does not panic")?)
}

impl From<io::Error> for ProcessError {
    fn from(error: io::Error) -> Self {
        if error.kind() == io::ErrorKind::NotFound {
            Self::NotFound
        } else {
            Self::Failed(error.to_string())
        }
    }
}
