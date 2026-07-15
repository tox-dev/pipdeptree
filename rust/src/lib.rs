use std::fmt::Write as _;

use anstyle::AnsiColor;
use pyo3::exceptions::PyValueError;
use pyo3::prelude::{PyModule, PyModuleMethods};
use pyo3::types::{PyAnyMethods as _, PyBytes, PyList};
use pyo3::{Bound, Py, PyResult, Python, pyfunction, pymodule, wrap_pyfunction};

use crate::environment::Runtime;
use crate::graph::{FilterError, FilterSpec, Graph};
use crate::metadata::Discovered;
use crate::options::{Command, Format, Options, WarningMode};

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
    pub mermaid: Option<Vec<u8>>,
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
            false,
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
fn render_py(py: Python<'_>, args: &Bound<'_, PyList>) -> PyResult<(String, String, i32)> {
    let args: Vec<String> = args.extract()?;
    let output = execute(
        &SystemProcessRunner,
        py,
        &args,
        false,
        false,
        Interface::Python,
        false,
    );
    // warn=fail sets a nonzero code while still rendering; the API contract raises only when
    // nothing could be rendered (invalid options, discovery failures).
    if output.code != 0 && output.stdout.is_empty() {
        return Err(PyValueError::new_err(output.stderr.trim().to_string()));
    }
    let rendered = String::from_utf8(output.stdout).map_err(|_| {
        PyValueError::new_err(
            "binary graphviz output cannot be returned as a string; use the dot format",
        )
    })?;
    Ok((rendered, output.stderr, output.code))
}

#[pyfunction(name = "render_with_mermaid", signature = (args))]
fn render_with_mermaid_py(
    py: Python<'_>,
    args: &Bound<'_, PyList>,
) -> PyResult<(String, String, String, i32)> {
    let args: Vec<String> = args.extract()?;
    let output = execute(
        &SystemProcessRunner,
        py,
        &args,
        false,
        false,
        Interface::Python,
        true,
    );
    if output.code != 0 && output.stdout.is_empty() {
        return Err(PyValueError::new_err(output.stderr.trim().to_string()));
    }
    Ok((
        String::from_utf8(output.stdout).expect("text output is UTF-8"),
        output
            .mermaid
            .map(|mermaid| String::from_utf8(mermaid).expect("mermaid output is UTF-8"))
            .unwrap_or_default(),
        output.stderr,
        output.code,
    ))
}

// Binary Graphviz targets that the string-returning render() API cannot hand back; kept here so the
// output-format vocabulary lives on the Rust side of the boundary rather than in the Python shim.
const BINARY_GRAPHVIZ: &[&str] = &["png", "svg", "pdf", "jpeg", "jpg", "gif", "bmp", "ps"];
const RENDER_FORMATS: &[&str] = &["text", "json", "json-tree", "mermaid", "dot"];

// Translate a render() output_format into the CLI arguments the engine expects, or raise the same
// ValueError the Python shim used to raise. Summary and tree formats have distinct vocabularies.
#[pyfunction(name = "format_flags", signature = (output_format, summary))]
fn format_flags_py(output_format: &str, summary: bool) -> PyResult<Vec<String>> {
    if summary {
        if !matches!(output_format, "json" | "rich" | "text") {
            return Err(PyValueError::new_err(format!(
                "summary output_format must be one of json, rich, text; got '{output_format}'"
            )));
        }
        return Ok(vec![
            "--summary".to_string(),
            "--output".to_string(),
            output_format.to_string(),
        ]);
    }
    let flags: &[&str] = match output_format {
        "text" => &[],
        "json" => &["--json"],
        "json-tree" => &["--json-tree"],
        "mermaid" => &["--mermaid"],
        "dot" => &["--graph-output", "dot"],
        _ if BINARY_GRAPHVIZ.contains(&output_format) => {
            return Err(PyValueError::new_err(
                "binary Graphviz formats cannot be returned as a string; use output_format='dot' \
                 for the Graphviz source, or run the pipdeptree CLI for binary output",
            ));
        }
        _ => {
            return Err(PyValueError::new_err(format!(
                "unknown output_format '{output_format}'; expected one of {}",
                RENDER_FORMATS.join(", ")
            )));
        }
    };
    Ok(flags.iter().map(ToString::to_string).collect())
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
    with_mermaid: bool,
) -> Execution {
    let mut options = match Options::parse_args(args, color) {
        Ok(options) => options,
        Err(error) => return parse_failure(&error, color),
    };
    if options.version() {
        return success(format!("{}\n", env!("PIPDEPTREE_VERSION")).into_bytes());
    }
    if let Err(error) = options.validate(color) {
        return failure(2, format!("pipdeptree: error: {error}\n"));
    }
    let ctx = RenderContext {
        color,
        interface,
        warning_mode: if options.output_format.emits_text_warnings() {
            options.warn
        } else {
            WarningMode::Silence
        },
        graphviz_format: options
            .output_format
            .graphviz_target()
            .map(ToOwned::to_owned),
    };
    let Prepared {
        graph,
        stderr,
        warned,
    } = match prepare_graph(processes, py, &options, log_resolved, &ctx) {
        Ok(prepared) => prepared,
        Err(execution) => return execution,
    };
    let output = match render::render(processes, &graph, &options, color) {
        Ok(output) => output,
        Err(error) => return failure(1, format!("{stderr}{error}\n")),
    };
    let mermaid = with_mermaid.then(|| {
        options.output_format = Format::Mermaid;
        render::render(processes, &graph, &options, color).expect("mermaid rendering cannot fail")
    });
    let code = i32::from(ctx.warning_mode == WarningMode::Fail && warned);
    Execution {
        code,
        stdout: output,
        stderr,
        graphviz_format: ctx.graphviz_format,
        mermaid,
    }
}

// Cross-cutting presentation state shared by graph preparation and every failure path, so filter
// outcomes render consistently without threading four separate values through the pipeline.
struct RenderContext {
    color: bool,
    interface: Interface,
    warning_mode: WarningMode,
    graphviz_format: Option<String>,
}

struct Prepared {
    graph: Graph,
    stderr: String,
    warned: bool,
}

fn prepare_graph(
    processes: &dyn ProcessRunner,
    py: Python<'_>,
    options: &Options,
    log_resolved: bool,
    ctx: &RenderContext,
) -> Result<Prepared, Execution> {
    metadata::reset_vcs_caches();
    let runtime = Runtime::resolve(processes, py, options, log_resolved)
        .map_err(|error| failure(1, format!("{error}\n")))?;
    let mut stderr = runtime.resolved_message.clone().unwrap_or_default();
    let mut warned = false;
    let packages = match packages(py, options, &runtime) {
        Ok(discovered) => {
            if ctx.warning_mode != WarningMode::Silence {
                for warning in discovered.warnings {
                    stderr.push_str(&style_warning(&warning.message, ctx.color));
                    warned |= warning.failure;
                }
            }
            discovered.packages
        }
        Err(error) => return Err(failure(1, format!("{stderr}{error}\n"))),
    };
    let mut graph = Graph::new(packages, &runtime.marker, options.extras);
    let (filter_spec, requested_extras) = FilterSpec::from_options(options);
    graph.apply_global_extras(&requested_extras);
    let filtered = |graph: &mut Graph, stderr: String, warned: bool| {
        graph
            .apply_filters(&filter_spec)
            .map_err(|error| filter_failure(&error, ctx, stderr, warned))
    };
    // Warnings cover the whole environment, so filters wait for them; with warnings silenced,
    // filtering first keeps version resolution (and its module-import fallback) away from
    // packages that never render.
    if ctx.warning_mode == WarningMode::Silence {
        filtered(&mut graph, stderr.clone(), warned)?;
    }
    graph
        .resolve_missing_versions(py, &runtime.paths)
        .map_err(|error| failure(1, format!("{stderr}{error}\n")))?;
    if ctx.warning_mode != WarningMode::Silence {
        graph.validate();
        for warning in &graph.warnings {
            let warning = format!(
                "Warning: dependency problems found:\n* {warning}\n{}\n",
                "-".repeat(72)
            );
            stderr.push_str(&style_warning(&warning, ctx.color));
            stderr.push('\n');
            warned = true;
        }
        filtered(&mut graph, stderr.clone(), warned)?;
    }
    Ok(Prepared {
        graph,
        stderr,
        warned,
    })
}

fn filter_failure(
    error: &FilterError,
    ctx: &RenderContext,
    mut stderr: String,
    warned: bool,
) -> Execution {
    let message = error.to_string();
    match error {
        FilterError::Unmatched(_) if ctx.interface == Interface::Python => Execution {
            code: 0,
            stdout: Vec::new(),
            stderr: String::new(),
            graphviz_format: ctx.graphviz_format.clone(),
            mermaid: None,
        },
        FilterError::Unmatched(_) => {
            let warned = if ctx.warning_mode == WarningMode::Silence {
                warned
            } else {
                writeln!(stderr, "{message}").expect("writing to a string cannot fail");
                true
            };
            Execution {
                code: i32::from(ctx.warning_mode == WarningMode::Fail && warned),
                stdout: Vec::new(),
                stderr,
                graphviz_format: ctx.graphviz_format.clone(),
                mermaid: None,
            }
        }
        FilterError::Overlap => failure(1, format!("{stderr}{message}\n")),
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
        success(message.into_bytes())
    }
}

const fn success(stdout: Vec<u8>) -> Execution {
    Execution {
        code: 0,
        stdout,
        stderr: String::new(),
        graphviz_format: None,
        mermaid: None,
    }
}

const fn failure(code: i32, stderr: String) -> Execution {
    Execution {
        code,
        stdout: Vec::new(),
        stderr,
        graphviz_format: None,
        mermaid: None,
    }
}

fn packages(py: Python<'_>, options: &Options, runtime: &Runtime) -> Result<Discovered, Error> {
    match &options.command {
        None => metadata::discover_selected(&runtime.paths, &options.metadata, options.summary()),
        Some(Command::FromLock { lock }) => lock::load(lock, &runtime.marker),
        Some(Command::FromIndex {
            requirements,
            requirement_files,
            pyproject_files,
            index_url,
            extra_index_url,
        }) => index::resolve(
            py,
            requirements,
            requirement_files,
            pyproject_files,
            index_url.as_deref(),
            extra_index_url,
        ),
    }
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
    extension.add_function(wrap_pyfunction!(render_with_mermaid_py, extension)?)?;
    extension.add_function(wrap_pyfunction!(format_flags_py, extension)?)?;
    Ok(())
}
