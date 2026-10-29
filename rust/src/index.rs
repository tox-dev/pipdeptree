use std::collections::{HashMap, HashSet};
use std::env;
use std::fs;
use std::path::{Path, PathBuf};
use std::str::FromStr;

use pep508_rs::{Pep508Error, Requirement, VerbatimUrl, VersionOrUrl, expand_env_vars};
use percent_encoding::percent_decode_str;
use pyo3::exceptions::PyValueError;
use pyo3::prelude::{PyAnyMethods, PyModule};
use pyo3::types::{
    IntoPyDict, PyDict, PyDictMethods, PyList, PyListMethods, PyStringMethods, PyTuple,
};
use pyo3::{PyResult, Python};
use serde::{Deserialize, Serialize};
use tempfile::tempdir;
use url::Url;

use crate::Error;
use crate::metadata::{
    Discovered, DiscoveryWarning, Package, ResolvedDeclaration, ResolvedEdge, printable_lines,
};

const RESOLVER_IMPORT_ERROR: &str =
    "The from-index subcommand requires nab, nab-index and nab-project";
const PYPI_NAME: &str = "pypi";
const PYPI_URL: &str = "https://pypi.org/simple";
const GIT_SCHEMES: [&str; 5] = ["git+https", "git+ssh", "git+http", "git+file", "git+git"];
const SOURCE_CONSTRAINT_ERROR: &str = "source requirements cannot be constraints";

#[derive(Debug, Default)]
struct Inputs {
    requirements: Vec<String>,
    constraints: Vec<String>,
    local_sources: Vec<LocalSource>,
    vcs_sources: Vec<VcsSource>,
    indexes: Option<Vec<Index>>,
    parsed_files: HashSet<(PathBuf, bool)>,
    warnings: Vec<DiscoveryWarning>,
}

#[derive(Clone, Debug, Serialize)]
struct Index {
    name: String,
    url: String,
}

#[derive(Clone, Debug, Serialize)]
struct LocalSource {
    name: String,
    path: String,
    editable: bool,
}

#[derive(Clone, Debug, Serialize)]
struct VcsSource {
    name: String,
    url: String,
}

#[derive(Clone, Copy)]
struct Location<'a> {
    file: &'a Path,
    line: usize,
}

impl<'a> Location<'a> {
    fn directory(self) -> &'a Path {
        self.file
            .parent()
            .expect("canonical source file has a parent")
    }
}

struct ResolverModules<'py> {
    multi_index: pyo3::Bound<'py, PyModule>,
    transport: pyo3::Bound<'py, PyModule>,
    config: pyo3::Bound<'py, PyModule>,
    resolve: pyo3::Bound<'py, PyModule>,
}

#[derive(Debug, Deserialize)]
struct PyProject {
    project: Option<ProjectInput>,
}

#[derive(Debug, Deserialize)]
struct ProjectInput {
    name: Option<String>,
    #[serde(default)]
    dependencies: Vec<String>,
}

#[derive(Debug, Serialize)]
struct GeneratedPyProject {
    project: GeneratedProject,
    #[serde(skip_serializing_if = "Option::is_none")]
    tool: Option<Tool>,
}

#[derive(Debug, Serialize)]
struct GeneratedProject {
    name: &'static str,
    version: &'static str,
    dependencies: Vec<String>,
}

#[derive(Debug, Serialize)]
struct Tool {
    nab: Nab,
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "kebab-case")]
struct Nab {
    #[serde(skip_serializing_if = "Vec::is_empty")]
    constraints: Vec<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    vcs: Option<VcsPolicy>,
    #[serde(skip_serializing_if = "Vec::is_empty")]
    local_sources: Vec<LocalSource>,
    #[serde(skip_serializing_if = "Vec::is_empty")]
    vcs_sources: Vec<VcsSource>,
    #[serde(skip_serializing_if = "Vec::is_empty")]
    package_rules: Vec<PackageRule>,
    #[serde(skip_serializing_if = "Vec::is_empty")]
    indexes: Vec<Index>,
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "kebab-case")]
struct PackageRule {
    r#match: [String; 1],
    build_policy: &'static str,
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "kebab-case")]
struct VcsPolicy {
    policy: &'static str,
    allowed_schemes: [&'static str; 5],
}

pub fn resolve(
    py: Python<'_>,
    requirements: &[String],
    requirement_files: &[PathBuf],
    pyproject_files: &[PathBuf],
    index_url: Option<&str>,
    extra_index_urls: &[String],
    warnings: &mut Vec<DiscoveryWarning>,
) -> Result<Discovered, Error> {
    // Nab logs what it skips while reading the index, such as a release whose metadata does not
    // parse, quoting that metadata. Without a handler, Python's last-resort handler writes the
    // record to stderr unescaped and regardless of --warn.
    let queue = PyModule::import(py, "queue")?
        .getattr("SimpleQueue")?
        .call0()?;
    let handler = PyModule::import(py, "logging.handlers")?
        .getattr("QueueHandler")?
        .call1((&queue,))?;
    handler.call_method1("setLevel", ("WARNING",))?;
    let logging = PyModule::import(py, "logging")?;
    // The top-level loggers Nab's modules log under, as listed in nab.output._NAB_LOGGERS.
    let loggers = [
        "nab",
        "nab_markersets",
        "nab_provider",
        "nab_project",
        "nab_index",
        "nab_resolver",
    ]
    .into_iter()
    .map(|name| logging.call_method1("getLogger", (name,)))
    .collect::<PyResult<Vec<_>>>()?;
    for logger in &loggers {
        logger.call_method1("addHandler", (&handler,))?;
    }
    let resolved = resolve_requirements(
        py,
        requirements,
        requirement_files,
        pyproject_files,
        index_url,
        extra_index_urls,
        warnings,
    );
    for logger in &loggers {
        logger.call_method1("removeHandler", (&handler,))?;
    }
    let mut messages = Vec::new();
    while !queue.call_method0("empty")?.extract::<bool>()? {
        let record = queue.call_method0("get_nowait")?;
        messages.push(printable_lines(
            &record.call_method0("getMessage")?.extract::<String>()?,
        ));
    }
    if !messages.is_empty() {
        warnings.push(DiscoveryWarning {
            message: format!(
                "Warning: the resolver reported:\n{}\n{}\n",
                messages.join("\n"),
                "-".repeat(72)
            ),
            failure: false,
        });
    }
    resolved
}

fn resolve_requirements(
    py: Python<'_>,
    requirements: &[String],
    requirement_files: &[PathBuf],
    pyproject_files: &[PathBuf],
    index_url: Option<&str>,
    extra_index_urls: &[String],
    warnings: &mut Vec<DiscoveryWarning>,
) -> Result<Discovered, Error> {
    let indexes = resolve_indexes(index_url, extra_index_urls);
    let result =
        if requirements.is_empty() && requirement_files.is_empty() && pyproject_files.len() == 1 {
            let path = require_file(&pyproject_files[0])?;
            resolve_pyproject(py, path, indexes.as_deref(), true)?
        } else {
            let mut inputs = Inputs {
                indexes,
                ..Inputs::default()
            };
            for path in pyproject_files {
                inputs.requirements.extend(
                    read_pyproject(require_file(path)?)?
                        .project
                        .map_or_else(Vec::new, |project| project.dependencies),
                );
            }
            for path in requirement_files {
                parse_requirements_file(require_file(path)?, false, &mut inputs, &mut Vec::new())?;
            }
            for requirement in requirements {
                parse_requirement(requirement, None, false, &mut inputs)?;
            }
            warnings.append(&mut inputs.warnings);
            let directory = tempdir()?;
            let path = directory.path().join("pyproject.toml");
            fs::write(&path, render_pyproject(&inputs))?;
            // The generated project belongs to no workspace. Its ancestors are the temporary
            // directory, where any local user may declare one whose members would replace the
            // index's packages.
            resolve_pyproject(py, &path, None, false)?
        };
    adapt_result(&result)
}

fn resolve_indexes(index_url: Option<&str>, extra_index_urls: &[String]) -> Option<Vec<Index>> {
    // An empty variable counts as unset, so `PIP_INDEX_URL=` keeps the PyPI default like pip's
    // or-chain, and `PIP_EXTRA_INDEX_URL=` leaves `UV_EXTRA_INDEX_URL` in effect.
    let variable = |name| env::var(name).ok().filter(|value| !value.is_empty());
    let primary = index_url
        .map(ToOwned::to_owned)
        .filter(|value| !value.is_empty())
        .or_else(|| variable("PIP_INDEX_URL"))
        .or_else(|| variable("UV_INDEX_URL"));
    let extras = if extra_index_urls.is_empty() {
        variable("PIP_EXTRA_INDEX_URL")
            .or_else(|| variable("UV_EXTRA_INDEX_URL"))
            .map_or_else(Vec::new, |value| {
                value.split_whitespace().map(ToOwned::to_owned).collect()
            })
    } else {
        extra_index_urls.to_vec()
    };
    if primary.is_none() && extras.is_empty() {
        return None;
    }
    let mut indexes = vec![primary.map(without_credentials).map_or_else(
        || Index {
            name: PYPI_NAME.to_string(),
            url: PYPI_URL.to_string(),
        },
        |url| Index {
            name: if url == PYPI_URL {
                PYPI_NAME.to_string()
            } else {
                "primary".to_string()
            },
            url,
        },
    )];
    indexes.extend(extras.into_iter().enumerate().map(|(position, url)| Index {
        name: format!("extra-{}", position + 1),
        url: without_credentials(url),
    }));
    Some(indexes)
}

// Nab sends no credentials from an index URL, but quotes the URL in its error messages, so the
// user name and password would reach stderr without ever authenticating a request.
fn without_credentials(url: String) -> String {
    match Url::parse(&url) {
        Ok(mut parsed) if !parsed.username().is_empty() || parsed.password().is_some() => {
            parsed
                .set_username("")
                .and_then(|()| parsed.set_password(None))
                .expect("a URL with credentials has a host");
            parsed.into()
        }
        _ => url,
    }
}

fn parse_requirements_file(
    path: &Path,
    constraint: bool,
    inputs: &mut Inputs,
    stack: &mut Vec<PathBuf>,
) -> Result<(), Error> {
    // Each include recurses on the caller's thread, so a long chain of distinct files would
    // overflow its stack; hand-written layouts nest a few levels.
    const MAX_DEPTH: usize = 100;
    let path = dunce::canonicalize(path)?;
    if stack.contains(&path) {
        return Err(Error::message(format!(
            "recursive requirements include: {}",
            path.display()
        )));
    }
    // A repeated include adds the same entries, and a file reached along many include paths
    // would otherwise be parsed once per path.
    if !inputs.parsed_files.insert((path.clone(), constraint)) {
        return Ok(());
    }
    if stack.len() == MAX_DEPTH {
        return Err(Error::message(format!(
            "requirements include nested deeper than {MAX_DEPTH} levels: {}",
            path.display()
        )));
    }
    stack.push(path.clone());
    let content = fs::read_to_string(&path)?;
    let mut logical = String::new();
    let mut location = Location {
        file: &path,
        line: 0,
    };
    for (index, raw_line) in content.lines().enumerate() {
        if logical.is_empty() {
            location.line = index + 1;
        }
        let line = raw_line.trim();
        if line.ends_with('\\') {
            logical.push_str(line.trim_end_matches('\\').trim_end());
            logical.push(' ');
            continue;
        }
        logical.push_str(line);
        let line = strip_comment(&logical).trim();
        (!line.is_empty())
            .then(|| parse_requirements_line(line, location, constraint, inputs, stack))
            .transpose()?;
        logical.clear();
    }
    if !logical.trim().is_empty() {
        parse_requirements_line(
            strip_comment(&logical).trim(),
            location,
            constraint,
            inputs,
            stack,
        )?;
    }
    stack.pop();
    Ok(())
}

fn parse_requirements_line(
    line: &str,
    location: Location<'_>,
    constraint: bool,
    inputs: &mut Inputs,
    stack: &mut Vec<PathBuf>,
) -> Result<(), Error> {
    let base = location.directory();
    // pip treats -r inside a constraints file as another constraints file.
    if let Some(value) = option_value(line, "-r", "--requirement") {
        return parse_requirements_file(&base.join(value), constraint, inputs, stack);
    }
    if let Some(value) = option_value(line, "-c", "--constraint") {
        return parse_requirements_file(&base.join(value), true, inputs, stack);
    }
    if let Some(value) = option_value(line, "-e", "--editable") {
        if constraint {
            return Err(Error::message(SOURCE_CONSTRAINT_ERROR));
        }
        // pip accepts editable VCS URLs; the resolver has no editable mode for them, so they
        // map to plain VCS sources like the Python engine did.
        if value.trim_start().starts_with("git+") {
            return translate_source(value, base, inputs);
        }
        return add_local_source(value, base, true, inputs);
    }
    if line.starts_with('-') {
        // pip applies an index option here to the whole install, while the resolve reads its
        // indexes from the command line and environment, so skipping one changes the index used.
        let (option, flag) = match line.split([' ', '\t', '=']).next() {
            Some(option @ ("--index-url" | "--extra-index-url")) => (option, option),
            Some(option) if option.starts_with("-i") => ("-i", "--index-url"),
            _ => return Ok(()),
        };
        inputs.warnings.push(DiscoveryWarning {
            message: format!(
                "Warning: {}:{}: from-index ignores {option} in requirements files; pass {flag} on \
                 the command line\n",
                location.file.display(),
                location.line
            ),
            failure: true,
        });
        return Ok(());
    }
    let requirement = line.split(" --hash=").next().unwrap_or(line).trim();
    parse_requirement(requirement, Some(location), constraint, inputs)
}

fn parse_requirement(
    raw: &str,
    location: Option<Location<'_>>,
    constraint: bool,
    inputs: &mut Inputs,
) -> Result<(), Error> {
    // The parser's error repeats the whole input. An include can name a file that holds a
    // credential rather than requirements, so a line read from a file is reported by location.
    let invalid = |error: Pep508Error<VerbatimUrl>| {
        Error::message(location.map_or_else(
            || error.to_string(),
            |location| {
                format!(
                    "{}:{}: invalid requirement",
                    location.file.display(),
                    location.line
                )
            },
        ))
    };
    let requirement = match Requirement::<VerbatimUrl>::from_str(raw) {
        Ok(requirement) => requirement,
        Err(error) if looks_like_source(raw) && raw.contains(" @ ") => return Err(invalid(error)),
        Err(_) if looks_like_source(raw) => {
            if constraint {
                return Err(Error::message(SOURCE_CONSTRAINT_ERROR));
            }
            let base = location.map_or_else(|| Path::new("."), Location::directory);
            return translate_source(raw, base, inputs);
        }
        Err(error) => return Err(invalid(error)),
    };
    if constraint {
        if matches!(requirement.version_or_url, Some(VersionOrUrl::Url(_))) {
            return Err(Error::message(SOURCE_CONSTRAINT_ERROR));
        }
        if !requirement.extras.is_empty() {
            return Err(Error::message(format!(
                "the index resolver cannot constrain extras: {raw}"
            )));
        }
        inputs.constraints.push(requirement.to_string());
        return Ok(());
    }
    if let Some(VersionOrUrl::Url(url)) = &requirement.version_or_url {
        return translate_url(requirement.name.to_string(), url, inputs);
    }
    inputs.requirements.push(requirement.to_string());
    Ok(())
}

fn translate_source(raw: &str, base: &Path, inputs: &mut Inputs) -> Result<(), Error> {
    let raw = raw.trim();
    if raw.starts_with("git+") {
        if let Some(name) = egg_fragment_name(raw) {
            validate_vcs_pin(raw)?;
            inputs.vcs_sources.push(VcsSource {
                name: name.to_string(),
                url: raw.to_string(),
            });
            return Ok(());
        }
        return Err(Error::message(format!(
            "VCS requirement needs an explicit name (use 'name @ git+...' or '#egg=name'): {raw}"
        )));
    }
    add_local_source(raw, base, false, inputs)
}

fn egg_fragment_name(url: &str) -> Option<&str> {
    let (_, fragment) = url.split_once('#')?;
    fragment
        .split('&')
        .find_map(|parameter| parameter.strip_prefix("egg="))
        .filter(|name| !name.is_empty())
}

fn translate_url(name: String, url: &VerbatimUrl, inputs: &mut Inputs) -> Result<(), Error> {
    let value = url
        .given()
        .expect("requirements parsed from user input retain their URL")
        .to_owned();
    if value.starts_with("git+") {
        validate_vcs_pin(&value)?;
        inputs.vcs_sources.push(VcsSource { name, url: value });
        return Ok(());
    }
    if url.scheme() == "file" {
        return add_local_source_path(&file_url_path(&expand_env_vars(&value))?, false, inputs);
    }
    Err(Error::message(format!(
        "URL requirements are not supported by the index resolver: {name} @ {value}"
    )))
}

fn add_local_source(
    raw: &str,
    base: &Path,
    editable: bool,
    inputs: &mut Inputs,
) -> Result<(), Error> {
    let path = if raw.starts_with("file:") {
        file_url_path(raw)?
    } else {
        let path = PathBuf::from(raw);
        if path.is_absolute() {
            path
        } else {
            base.join(path)
        }
    };
    add_local_source_path(&path, editable, inputs)
}

// pip's url_to_path keeps the path of a file: URL that has no authority as written, so
// file:pkg and file:./pkg stay relative and resolve against the working directory.
fn file_url_path(url: &str) -> Result<PathBuf, Error> {
    let invalid = || Error::message(format!("invalid local file URL: {url}"));
    match url.get("file:".len()..) {
        Some(path) if !path.starts_with("//") => {
            let path = path.find(['?', '#']).map_or(path, |end| &path[..end]);
            let path = percent_decode_str(path)
                .decode_utf8()
                .map_err(|_| invalid())?;
            Ok(PathBuf::from(strip_drive_slash(&path)))
        }
        _ => Url::parse(url)
            .ok()
            .and_then(|url| url.to_file_path().ok())
            .ok_or_else(invalid),
    }
}

// pip drops the slash urlsplit leaves before a drive letter, so file:/C:/pkg reads C:/pkg.
#[cfg(windows)]
fn strip_drive_slash(path: &str) -> &str {
    match path.as_bytes() {
        [b'/', drive, b':', rest @ ..]
            if drive.is_ascii_alphabetic() && matches!(rest, [] | [b'/', ..]) =>
        {
            &path[1..]
        }
        _ => path,
    }
}

#[cfg(not(windows))]
const fn strip_drive_slash(path: &str) -> &str {
    path
}

fn add_local_source_path(path: &Path, editable: bool, inputs: &mut Inputs) -> Result<(), Error> {
    // std's canonicalize gives a \\?\ path on Windows, where "." does not resolve, so the build
    // frontend rejects backend-path = ["."]; dunce returns the plain form when one exists.
    let path = dunce::canonicalize(path).map_err(|error| {
        Error::message(format!("editable/local source {}: {error}", path.display()))
    })?;
    let pyproject = path.join("pyproject.toml");
    if !pyproject.is_file() {
        return Err(Error::message(format!(
            "editable/local source must be a directory with a pyproject.toml: {}",
            path.display()
        )));
    }
    let project = read_pyproject(&pyproject)?;
    let name = project
        .project
        .and_then(|project| project.name)
        .ok_or_else(|| {
            Error::message(format!(
                "cannot determine package name for editable/local source {}: \
                 its pyproject.toml has no [project].name",
                path.display()
            ))
        })?;
    inputs.local_sources.push(LocalSource {
        name,
        path: path.to_string_lossy().into_owned(),
        editable,
    });
    Ok(())
}

fn validate_vcs_pin(url: &str) -> Result<(), Error> {
    let reference = url
        .split('#')
        .next()
        .and_then(|value| value.rsplit_once('@'))
        .map(|(_, reference)| reference);
    if reference.is_none_or(|reference| {
        reference.len() != 40
            || !reference
                .chars()
                .all(|character| character.is_ascii_hexdigit())
    }) {
        return Err(Error::message(format!(
            "VCS requirement must be pinned to a full commit sha: {url}"
        )));
    }
    Ok(())
}

fn read_pyproject(path: &Path) -> Result<PyProject, Error> {
    Ok(toml::from_str(&fs::read_to_string(path)?)?)
}

fn render_pyproject(inputs: &Inputs) -> String {
    let mut dependencies = inputs.requirements.clone();
    dependencies.extend(
        inputs
            .local_sources
            .iter()
            .map(|source| source.name.clone()),
    );
    dependencies.extend(inputs.vcs_sources.iter().map(|source| source.name.clone()));
    let has_sources = !inputs.local_sources.is_empty() || !inputs.vcs_sources.is_empty();
    let indexes = inputs.indexes.clone().unwrap_or_default();
    let has_nab = !inputs.constraints.is_empty() || has_sources || !indexes.is_empty();
    let project = GeneratedPyProject {
        project: GeneratedProject {
            name: "pipdeptree-from-index",
            version: "0",
            dependencies,
        },
        tool: has_nab.then(|| Tool {
            nab: Nab {
                constraints: inputs.constraints.clone(),
                vcs: (!inputs.vcs_sources.is_empty()).then_some(VcsPolicy {
                    policy: "allow",
                    allowed_schemes: GIT_SCHEMES,
                }),
                local_sources: inputs.local_sources.clone(),
                vcs_sources: inputs.vcs_sources.clone(),
                // The resolver's default policy already builds a listed local source. A listed
                // clone needs build-remote, which, set for the whole resolve, would also run the
                // backend of every sdist fetched from the index, so only the named clones get it.
                package_rules: inputs
                    .vcs_sources
                    .iter()
                    .map(|source| PackageRule {
                        r#match: [source.name.clone()],
                        build_policy: "build-remote",
                    })
                    .collect(),
                indexes,
            },
        }),
    };
    toml::to_string(&project).expect("generated pyproject data is TOML serializable")
}

fn resolve_pyproject<'py>(
    py: Python<'py>,
    path: &Path,
    indexes: Option<&[Index]>,
    discover_workspace: bool,
) -> Result<pyo3::Bound<'py, pyo3::PyAny>, Error> {
    ResolverModules::import(py)?
        .resolve(py, path, indexes, discover_workspace)
        .map_err(Error::from)
}

impl<'py> ResolverModules<'py> {
    fn import(py: Python<'py>) -> Result<Self, Error> {
        let import = |name| {
            PyModule::import(py, name).map_err(|error| {
                if error.is_instance_of::<pyo3::exceptions::PyModuleNotFoundError>(py) {
                    Error::message(RESOLVER_IMPORT_ERROR)
                } else {
                    Error::message(error.to_string())
                }
            })
        };
        Ok(Self {
            multi_index: import("nab_index.multi_index")?,
            transport: import("nab_index.urllib3_async_transport")?,
            config: import("nab.config.model")?,
            resolve: import("nab_project.resolve")?,
        })
    }

    fn resolve(
        &self,
        py: Python<'py>,
        path: &Path,
        indexes: Option<&[Index]>,
        discover_workspace: bool,
    ) -> PyResult<pyo3::Bound<'py, pyo3::PyAny>> {
        let pathlib = PyModule::import(py, "pathlib")?;
        let py_path = pathlib
            .getattr("Path")?
            .call1((path.to_string_lossy().as_ref(),))?;
        let kwargs = [("discover_workspace", discover_workspace)].into_py_dict(py)?;
        let mut config = self
            .config
            .getattr("read_pyproject_config")?
            .call((&py_path,), Some(&kwargs))?;
        if let Some(indexes) = indexes {
            let index_config = self.multi_index.getattr("IndexConfig")?;
            let configs = PyList::empty(py);
            for index in indexes {
                configs.append(index_config.call1((&index.name, &index.url))?)?;
            }
            let tuple = PyTuple::new(py, configs.iter())?;
            let kwargs = PyDict::new(py);
            kwargs.set_item("indexes", tuple)?;
            config = config.call_method("replace", (), Some(&kwargs))?;
        }
        let kwargs = PyDict::new(py);
        let targets = self.config.getattr("plan_targets")?.call1((&config,))?;
        kwargs.set_item("targets", targets)?;
        kwargs.set_item("inputs", config.call_method0("resolve_inputs")?)?;
        kwargs.set_item("include_dependency_requirements", true)?;
        let cache_dir = if let Some(path) = env::var_os("NAB_CACHE_DIR") {
            if path.is_empty() {
                return Err(PyValueError::new_err(
                    "NAB_CACHE_DIR must be a non-empty path",
                ));
            }
            pathlib
                .getattr("Path")?
                .call1((path.to_string_lossy().as_ref(),))?
        } else if let Some(path) = env::var_os("XDG_CACHE_HOME")
            .map(PathBuf::from)
            .filter(|path| path.is_absolute())
        {
            pathlib
                .getattr("Path")?
                .call1((path.to_string_lossy().as_ref(),))?
                .call_method1("joinpath", ("nab",))?
        } else {
            pathlib
                .getattr("Path")?
                .call_method0("home")?
                .call_method1("joinpath", (".cache", "nab"))?
        };
        kwargs.set_item("cache_dir", cache_dir)?;
        let transport = self.transport.getattr("Urllib3AsyncTransport")?.call0()?;
        self.resolve
            .getattr("resolve_for_targets")?
            .call((&py_path, transport), Some(&kwargs))
    }
}

fn adapt_result(result: &pyo3::Bound<'_, pyo3::PyAny>) -> Result<Discovered, Error> {
    // A target that cannot be resolved is reported rather than raised, so ask for the failure.
    // What is left is one result per planned target, and the generated project plans just the one.
    result.call_method0("raise_for_failure")?;
    let target = result.getattr("target_results")?.get_item(0)?;
    let pins = target.getattr("pins")?;
    let mut versions = HashMap::new();
    for item in pins.call_method0("items")?.try_iter()? {
        let item = item?;
        let name: String = item.get_item(0)?.extract()?;
        let version = item.get_item(1)?.str()?.to_string_lossy().into_owned();
        versions.insert(name, version);
    }
    let dependencies = target
        .getattr("lock")?
        .getattr("dependencies")?
        .extract::<HashMap<String, Vec<String>>>()?;
    let requirements = target.call_method0("dependency_requirements")?;
    let mut resolved_edges = HashMap::new();
    for (parent, children) in dependencies {
        let by_child = requirements.get_item(&parent)?;
        let mut edges = Vec::new();
        for child in children {
            let records = by_child.get_item(&child)?;
            let mut found = false;
            for record in records.try_iter()? {
                let record = record?;
                found = true;
                edges.push(ResolvedEdge {
                    child: child.clone(),
                    declaration: Some(ResolvedDeclaration {
                        requirement_text: record.getattr("requirement_text")?.extract()?,
                        dependency_specifier: record.getattr("dependency_specifier")?.extract()?,
                        requirement_condition: record
                            .getattr("requirement_condition")?
                            .extract()?,
                        dependency_extras: record.getattr("dependency_extras")?.extract()?,
                        required_for_parent_extras: record
                            .getattr("required_for_parent_extras")?
                            .extract()?,
                        required_without_parent_extras: record
                            .getattr("required_without_parent_extras")?
                            .extract()?,
                    }),
                });
            }
            if !found {
                edges.push(ResolvedEdge {
                    child,
                    declaration: None,
                });
            }
        }
        resolved_edges.insert(parent, edges);
    }
    let packages = versions
        .iter()
        .map(|(name, version)| Package::synthetic(name, version, &[]))
        .collect::<Result<_, _>>()?;
    Ok(Discovered {
        packages,
        warnings: Vec::new(),
        resolved_edges: Some(resolved_edges),
    })
}

fn require_file(path: &Path) -> Result<&Path, Error> {
    if path.is_file() {
        Ok(path)
    } else {
        Err(Error::message(format!(
            "source file does not exist: {}",
            path.display()
        )))
    }
}

fn option_value<'a>(line: &'a str, short: &str, long: &str) -> Option<&'a str> {
    // pip's optparse also accepts an attached short value ("-rnested.txt").
    line.strip_prefix(&format!("{short} "))
        .or_else(|| line.strip_prefix(&format!("{long} ")))
        .or_else(|| line.strip_prefix(&format!("{long}=")))
        .or_else(|| {
            line.strip_prefix(short)
                .filter(|value| !value.is_empty() && !value.starts_with('-'))
        })
        .map(str::trim)
}

fn strip_comment(line: &str) -> &str {
    // pip strips a '#' preceded by any whitespace, not just a space.
    if line.starts_with('#') {
        return "";
    }
    line.char_indices()
        .find(|(position, character)| {
            *character == '#'
                && line[..*position]
                    .chars()
                    .next_back()
                    .is_some_and(char::is_whitespace)
        })
        .map_or(line, |(position, _)| &line[..position])
}

fn looks_like_source(requirement: &str) -> bool {
    // A local source is spelled ./, ../, .\, ..\, an absolute path, a file: URL or a VCS URL,
    // matching what pip accepts; no filesystem probe is needed to recognize one.
    let requirement = requirement.trim();
    requirement.contains("://")
        || Path::new(requirement).is_absolute()
        || ["./", "../", ".\\", "..\\", "/", "file:", "git+"]
            .iter()
            .any(|prefix| requirement.starts_with(prefix))
}
