use std::ffi::OsString;
use std::io::{self, Read as _, Write as _};
use std::path::PathBuf;
use std::process::{Child, Command, ExitStatus, Stdio};
use std::thread;
use std::time::{Duration, Instant};

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct ProcessRequest {
    pub program: OsString,
    pub args: Vec<OsString>,
    pub current_dir: Option<PathBuf>,
    pub stdin: Vec<u8>,
    pub timeout: Option<Duration>,
    pub removed_environment: Vec<OsString>,
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
            removed_environment: Vec::new(),
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
    pub fn without_environment(
        mut self,
        names: impl IntoIterator<Item = impl Into<OsString>>,
    ) -> Self {
        self.removed_environment = names.into_iter().map(Into::into).collect();
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
        if let Some(path) = &request.current_dir {
            command.current_dir(path);
        }
        let mut child = command.spawn()?;
        thread::scope(|scope| {
            let writer = (!request.stdin.is_empty()).then(|| {
                let mut stdin = child.stdin.take().expect("piped process stdin exists");
                scope.spawn(move || stdin.write_all(&request.stdin))
            });
            let mut stdout = child.stdout.take().expect("piped process stdout exists");
            let stdout = scope.spawn(move || {
                let mut output = Vec::new();
                stdout.read_to_end(&mut output)?;
                Ok::<_, io::Error>(output)
            });
            let mut stderr = child.stderr.take().expect("piped process stderr exists");
            let stderr = scope.spawn(move || {
                let mut output = Vec::new();
                stderr.read_to_end(&mut output)?;
                Ok::<_, io::Error>(output)
            });
            let status = wait(&mut child, request.timeout)?;
            let stdout = stdout
                .join()
                .expect("process stdout reader does not panic")?;
            let stderr = stderr
                .join()
                .expect("process stderr reader does not panic")?;
            if status.success() {
                if let Some(writer) = writer {
                    writer
                        .join()
                        .expect("process stdin writer does not panic")?;
                }
            }
            Ok(ProcessOutput {
                success: status.success(),
                stdout,
                stderr,
            })
        })
    }
}

fn wait(child: &mut Child, timeout: Option<Duration>) -> Result<ExitStatus, ProcessError> {
    let Some(timeout) = timeout else {
        return Ok(child.wait()?);
    };
    let deadline = Instant::now() + timeout;
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

impl From<io::Error> for ProcessError {
    fn from(error: io::Error) -> Self {
        if error.kind() == io::ErrorKind::NotFound {
            Self::NotFound
        } else {
            Self::Failed(error.to_string())
        }
    }
}
