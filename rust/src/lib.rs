use std::fmt::Write as _;

use anstyle::AnsiColor;
use pyo3::exceptions::PyValueError;
use pyo3::prelude::{PyModule, PyModuleMethods};
use pyo3::types::{PyAnyMethods as _, PyBytes, PyList};
use pyo3::{Bound, Py, PyResult, Python, pyfunction, pymodule, wrap_pyfunction};

use crate::environment::Runtime;
use crate::graph::{FilterError, Graph};
use crate::metadata::Package;
use crate::options::{Command, Options, WarningMode};

mod environment;
mod error;
mod graph;
mod index;
mod lock;
mod metadata;
mod options;
mod process;
mod render;

pub use error::Error;
pub use process::{
    ProcessError, ProcessOutput, ProcessRequest, ProcessRunner, SystemProcessRunner,
};

#[derive(Debug, Eq, PartialEq)]
pub struct Execution {
    pub code: i32,
    pub stdout: Vec<u8>,
    pub stderr: String,
    pub graphviz_format: Option<String>,
}

pub struct Application<'a> {
    processes: &'a dyn ProcessRunner,
}

impl<'a> Application<'a> {
    #[must_use]
    pub const fn new(processes: &'a dyn ProcessRunner) -> Self {
        Self { processes }
    }

    #[must_use]
    pub fn run(
        &self,
        py: Python<'_>,
        args: &[String],
        color: bool,
        log_resolved: bool,
    ) -> Execution {
        execute(
            self.processes,
            py,
            args,
            color,
            log_resolved,
            Interface::Cli,
        )
    }
}

#[pyfunction]
const fn engine() -> &'static str {
    "rust"
}

#[pyfunction]
const fn version() -> &'static str {
    env!("PIPDEPTREE_VERSION")
}

#[pyfunction(name = "execute", signature = (args, *, color = false, log_resolved = true))]
fn execute_py(
    py: Python<'_>,
    args: &Bound<'_, PyList>,
    color: bool,
    log_resolved: bool,
) -> PyResult<(i32, Py<PyBytes>, String, Option<String>)> {
    let args: Vec<String> = args.extract()?;
    let output = run(py, &args, color, log_resolved);
    Ok((
        output.code,
        PyBytes::new(py, &output.stdout).unbind(),
        output.stderr,
        output.graphviz_format,
    ))
}

#[pyfunction(name = "render", signature = (args))]
fn render_py(py: Python<'_>, args: &Bound<'_, PyList>) -> PyResult<String> {
    let args: Vec<String> = args.extract()?;
    let output = execute(
        &SystemProcessRunner,
        py,
        &args,
        false,
        false,
        Interface::Python,
    );
    if output.code != 0 {
        return Err(PyValueError::new_err(output.stderr.trim().to_string()));
    }
    Ok(String::from_utf8(output.stdout).expect("Rust renderers emit UTF-8"))
}

#[must_use]
pub fn run(py: Python<'_>, args: &[String], color: bool, log_resolved: bool) -> Execution {
    Application::new(&SystemProcessRunner).run(py, args, color, log_resolved)
}

fn execute(
    processes: &dyn ProcessRunner,
    py: Python<'_>,
    args: &[String],
    color: bool,
    log_resolved: bool,
    interface: Interface,
) -> Execution {
    let mut options = match Options::parse_args(args, color) {
        Ok(options) => options,
        Err(error) => return parse_failure(&error, color),
    };
    if options.version() {
        return Execution {
            code: 0,
            stdout: format!("{}\n", env!("PIPDEPTREE_VERSION")).into_bytes(),
            stderr: String::new(),
            graphviz_format: None,
        };
    }
    if let Err(error) = options.validate() {
        return failure(2, format!("pipdeptree: error: {error}\n"));
    }
    let graphviz_format = options
        .output_format
        .strip_prefix("graphviz-")
        .map(ToOwned::to_owned);
    let warning_mode = if text_output(&options) {
        options.warn
    } else {
        WarningMode::Silence
    };

    let runtime = match Runtime::resolve(processes, py, &options, log_resolved) {
        Ok(runtime) => runtime,
        Err(error) => return failure(1, format!("{error}\n")),
    };
    let mut stderr = runtime.resolved_message.clone().unwrap_or_default();
    let mut warned = false;
    let packages = match packages(py, &options, &runtime) {
        Ok((packages, discovery_warnings)) => {
            if warning_mode != WarningMode::Silence {
                for warning in discovery_warnings {
                    stderr.push_str(&style_warning(&warning.message, color));
                    warned |= warning.failure;
                }
            }
            packages
        }
        Err(error) => return failure(1, format!("{stderr}{error}\n")),
    };
    let mut graph = Graph::new(packages, &runtime.marker, options.extras);
    if let Err(error) = graph.resolve_missing_versions(py) {
        return failure(1, format!("{stderr}{error}\n"));
    }
    if warning_mode != WarningMode::Silence {
        graph.validate();
        for warning in &graph.warnings {
            let warning = format!(
                "Warning: dependency problems found:\n* {warning}\n{}\n",
                "-".repeat(72)
            );
            stderr.push_str(&style_warning(&warning, color));
            stderr.push('\n');
            warned = true;
        }
    }
    if let Err(error) = graph.apply_filters(&options) {
        let message = error.to_string();
        return match error {
            FilterError::Unmatched(_) if interface == Interface::Python => Execution {
                code: 0,
                stdout: Vec::new(),
                stderr: String::new(),
                graphviz_format,
            },
            FilterError::Unmatched(_) => {
                if warning_mode != WarningMode::Silence {
                    writeln!(stderr, "{message}").expect("writing to a string cannot fail");
                    warned = true;
                }
                Execution {
                    code: i32::from(warning_mode == WarningMode::Fail && warned),
                    stdout: Vec::new(),
                    stderr,
                    graphviz_format,
                }
            }
            FilterError::Overlap => failure(1, format!("{stderr}{message}\n")),
        };
    }
    let output = match render::render(processes, &graph, &options, color) {
        Ok(output) => output,
        Err(error) => return failure(1, format!("{stderr}{error}\n")),
    };
    let code = i32::from(warning_mode == WarningMode::Fail && warned);
    Execution {
        code,
        stdout: output,
        stderr,
        graphviz_format,
    }
}

#[derive(Clone, Copy, Eq, PartialEq)]
enum Interface {
    Cli,
    Python,
}

fn parse_failure(error: &clap::Error, color: bool) -> Execution {
    let message = if color {
        error.render().ansi().to_string()
    } else {
        error.to_string()
    };
    if error.use_stderr() {
        failure(2, message)
    } else {
        Execution {
            code: 0,
            stdout: message.into_bytes(),
            stderr: String::new(),
            graphviz_format: None,
        }
    }
}

const fn failure(code: i32, stderr: String) -> Execution {
    Execution {
        code,
        stdout: Vec::new(),
        stderr,
        graphviz_format: None,
    }
}

fn packages(
    py: Python<'_>,
    options: &Options,
    runtime: &Runtime,
) -> Result<(Vec<Package>, Vec<metadata::DiscoveryWarning>), Error> {
    match &options.command {
        None => metadata::discover_selected(&runtime.paths, &options.metadata, options.summary()),
        Some(Command::FromLock { lock }) => Ok((lock::load(lock)?, Vec::new())),
        Some(Command::FromIndex {
            requirements,
            requirement_files,
            pyproject_files,
            index_url,
            extra_index_url,
        }) => Ok((
            index::resolve(
                py,
                requirements,
                requirement_files,
                pyproject_files,
                index_url.as_deref(),
                extra_index_url,
            )?,
            Vec::new(),
        )),
    }
}

fn text_output(options: &Options) -> bool {
    matches!(options.output_format.as_str(), "freeze" | "rich" | "text")
}

fn style_warning(message: &str, color: bool) -> String {
    if !color {
        return message.to_string();
    }
    let style = AnsiColor::Yellow.on_default().bold();
    message.replacen("Warning:", &format!("{style}Warning:{style:#}"), 1)
}

#[pymodule(gil_used = false)]
#[pyo3(name = "_rust")]
/// # Errors
///
/// Returns the first Python exception raised while `PyO3` registers the extension functions.
pub fn install_python_module(extension: &Bound<'_, PyModule>) -> PyResult<()> {
    extension.add_function(wrap_pyfunction!(engine, extension)?)?;
    extension.add_function(wrap_pyfunction!(version, extension)?)?;
    extension.add_function(wrap_pyfunction!(execute_py, extension)?)?;
    extension.add_function(wrap_pyfunction!(render_py, extension)?)?;
    Ok(())
}
