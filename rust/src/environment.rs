use std::env;
use std::ffi::CString;
use std::path::{Path, PathBuf};
use std::time::Duration;

use pep508_rs::{MarkerEnvironment, MarkerEnvironmentBuilder};
use pyo3::exceptions::PyValueError;
use pyo3::prelude::{PyAnyMethods, PyModule};
use pyo3::types::{PyDict, PyDictMethods};
use pyo3::{PyResult, Python};
use serde::Deserialize;

use crate::Error;
use crate::options::Options;
use crate::process::{ProcessRequest, ProcessRunner};

const INTERPRETER_INFO: &str = r#"{
    "paths": sys.path,
    "executable": sys.executable,
    "prefix": sys.prefix,
    "base_prefix": sys.base_prefix,
    "user_site": site.getusersitepackages(),
    "marker": {
        "implementation_name": sys.implementation.name,
        "implementation_version": (
            f"{sys.implementation.version.major}.{sys.implementation.version.minor}."
            f"{sys.implementation.version.micro}"
            f"{'' if sys.implementation.version.releaselevel == 'final' else sys.implementation.version.releaselevel[0] + str(sys.implementation.version.serial)}"
        ),
        "os_name": os.name,
        "platform_machine": platform.machine(),
        "platform_python_implementation": platform.python_implementation(),
        "platform_release": platform.release(),
        "platform_system": platform.system(),
        "platform_version": platform.version(),
        "python_full_version": platform.python_version(),
        "python_version": ".".join(platform.python_version_tuple()[:2]),
        "sys_platform": sys.platform,
    },
}
"#;

#[derive(Clone, Debug, Deserialize)]
pub struct MarkerValues {
    implementation_name: String,
    implementation_version: String,
    os_name: String,
    platform_machine: String,
    platform_python_implementation: String,
    platform_release: String,
    platform_system: String,
    platform_version: String,
    python_full_version: String,
    python_version: String,
    sys_platform: String,
}

#[derive(Debug, Deserialize)]
struct InterpreterInfo {
    paths: Vec<PathBuf>,
    executable: PathBuf,
    prefix: PathBuf,
    base_prefix: PathBuf,
    user_site: PathBuf,
    marker: MarkerValues,
}

#[derive(Debug)]
pub struct Runtime {
    pub paths: Vec<PathBuf>,
    pub marker: MarkerEnvironment,
    pub resolved_message: Option<String>,
}

impl Runtime {
    pub fn resolve(
        processes: &dyn ProcessRunner,
        py: Python<'_>,
        options: &Options,
        log_resolved: bool,
    ) -> Result<Self, Error> {
        let current = InterpreterInfo::current(py)?;
        if options.command.is_some() {
            return Self::from_info(current, None, options, None, false);
        }
        if !options.path.is_empty() {
            return Self::from_info(current, Some(options.path.clone()), options, None, false);
        }

        let (detected, auto_detected) = match options.python.as_deref() {
            Some("auto") => (
                Some(
                    detect_interpreter(processes, &current.marker.implementation_name)
                        .ok_or_else(|| Error::message("Unable to detect virtual environment."))?,
                ),
                true,
            ),
            Some(value) => (Some(PathBuf::from(value)), false),
            None => (
                detect_interpreter(processes, &current.marker.implementation_name),
                true,
            ),
        };
        // An explicit --python PATH is the user's own choice; only auto-detection logs it.
        let resolved_message = detected
            .as_ref()
            .filter(|_| log_resolved && auto_detected)
            .map(|path| format!("(resolved python: {})\n", path.display()));
        let (info, queried) = if let Some(interpreter) = detected {
            if same_file(&interpreter, &current.executable) {
                (current, false)
            } else {
                (InterpreterInfo::query(processes, &interpreter)?, true)
            }
        } else {
            (current, false)
        };
        Self::from_info(info, None, options, resolved_message, queried)
    }

    fn from_info(
        mut info: InterpreterInfo,
        paths: Option<Vec<PathBuf>>,
        options: &Options,
        resolved_message: Option<String>,
        queried: bool,
    ) -> Result<Self, Error> {
        let mut paths = paths.unwrap_or_else(|| std::mem::take(&mut info.paths));
        // The old engine filtered a queried interpreter's sys.path by sys.prefix unconditionally;
        // only the running interpreter needs to be a venv for --local-only to act.
        if options.local_only() && (queried || info.prefix != info.base_prefix) {
            paths.retain(|path| path.starts_with(&info.prefix));
        }
        if options.user_only() {
            paths.retain(|path| path.starts_with(&info.user_site));
        }
        let marker = info.marker.as_environment()?;
        Ok(Self {
            paths,
            marker,
            resolved_message,
        })
    }
}

impl MarkerValues {
    fn as_environment(&self) -> Result<MarkerEnvironment, Error> {
        MarkerEnvironment::try_from(MarkerEnvironmentBuilder {
            implementation_name: &self.implementation_name,
            implementation_version: &self.implementation_version,
            os_name: &self.os_name,
            platform_machine: &self.platform_machine,
            platform_python_implementation: &self.platform_python_implementation,
            platform_release: &self.platform_release,
            platform_system: &self.platform_system,
            platform_version: &self.platform_version,
            python_full_version: &self.python_full_version,
            python_version: &self.python_version,
            sys_platform: &self.sys_platform,
        })
        .map_err(|error| Error::message(error.to_string()))
    }
}

impl InterpreterInfo {
    fn current(py: Python<'_>) -> PyResult<Self> {
        let globals = PyDict::new(py);
        for module in ["os", "platform", "site", "sys"] {
            globals.set_item(module, PyModule::import(py, module)?)?;
        }
        let expression =
            CString::new(INTERPRETER_INFO).expect("interpreter query has no null bytes");
        let value = py.eval(&expression, Some(&globals), None)?;
        let encoded: String = PyModule::import(py, "json")?
            .call_method1("dumps", (value,))?
            .extract()?;
        serde_json::from_str(&encoded).map_err(|error| PyValueError::new_err(error.to_string()))
    }

    fn query(processes: &dyn ProcessRunner, interpreter: &Path) -> Result<Self, Error> {
        let output = processes
            .run(&ProcessRequest::new(
                interpreter,
                ["-c".to_string(), interpreter_query()],
            ))
            .map_err(|error| {
                Error::message(format!("Failed to query custom interpreter: {error}"))
            })?;
        if !output.success {
            return Err(Error::message("Failed to query custom interpreter"));
        }
        Ok(serde_json::from_slice(&output.stdout)?)
    }
}

fn interpreter_query() -> String {
    format!("import json, os, platform, site, sys\nprint(json.dumps({INTERPRETER_INFO}))")
}

fn same_file(left: &Path, right: &Path) -> bool {
    comparable_path(left) == comparable_path(right)
}

fn comparable_path(path: &Path) -> PathBuf {
    // Not canonicalize(): a venv's bin/python symlinks to the base interpreter yet exposes a
    // different sys.path, so resolving symlinks would skip querying the venv.
    std::path::absolute(path).unwrap_or_else(|_| path.to_path_buf())
}

fn detect_interpreter(processes: &dyn ProcessRunner, implementation: &str) -> Option<PathBuf> {
    let executable = format!(
        "{}{}",
        if implementation == "pypy" {
            "pypy"
        } else {
            "python"
        },
        env::consts::EXE_SUFFIX
    );
    for (variable, directory) in environment_locations() {
        if let Some(root) = env::var_os(variable) {
            let path = PathBuf::from(root).join(directory).join(&executable);
            if path.exists() {
                return Some(path);
            }
        }
    }
    processes
        .run(
            &ProcessRequest::new("poetry", ["env", "info", "--executable"])
                .with_timeout(Duration::from_secs(5)),
        )
        .ok()
        .filter(|output| output.success)
        .and_then(|output| String::from_utf8(output.stdout).ok())
        .map(|path| PathBuf::from(path.trim()))
        .filter(|path| path.exists())
}

#[cfg(unix)]
const fn environment_locations() -> [(&'static str, &'static str); 2] {
    [("VIRTUAL_ENV", "bin"), ("CONDA_PREFIX", "bin")]
}

#[cfg(windows)]
const fn environment_locations() -> [(&'static str, &'static str); 2] {
    [("VIRTUAL_ENV", "Scripts"), ("CONDA_PREFIX", "")]
}
