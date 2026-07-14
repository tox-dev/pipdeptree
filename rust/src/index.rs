use std::collections::HashMap;
use std::env;
use std::fs;
use std::path::{Path, PathBuf};
use std::str::FromStr;

use pep508_rs::{Requirement, VerbatimUrl, VersionOrUrl};
use pyo3::prelude::{PyAnyMethods, PyModule};
use pyo3::types::{PyDict, PyDictMethods, PyList, PyListMethods, PyStringMethods, PyTuple};
use pyo3::{PyResult, Python};
use serde::{Deserialize, Serialize};
use tempfile::tempdir;

use crate::Error;
use crate::metadata::Package;

const RESOLVER_IMPORT_ERROR: &str = "The from-index subcommand requires nab-index and nab-python";
const PYPI_NAME: &str = "pypi";
const PYPI_URL: &str = "https://pypi.org/simple";
const GIT_SCHEMES: [&str; 5] = ["git+https", "git+ssh", "git+http", "git+file", "git+git"];

#[derive(Debug, Default)]
struct Inputs {
    requirements: Vec<String>,
    constraints: Vec<String>,
    local_sources: Vec<LocalSource>,
    vcs_sources: Vec<VcsSource>,
    indexes: Option<Vec<Index>>,
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
    build_policy: Option<&'static str>,
    #[serde(skip_serializing_if = "Option::is_none")]
    vcs: Option<VcsPolicy>,
    #[serde(skip_serializing_if = "Vec::is_empty")]
    local_sources: Vec<LocalSource>,
    #[serde(skip_serializing_if = "Vec::is_empty")]
    vcs_sources: Vec<VcsSource>,
    #[serde(skip_serializing_if = "Vec::is_empty")]
    indexes: Vec<Index>,
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
) -> Result<Vec<Package>, Error> {
    let indexes = resolve_indexes(index_url, extra_index_urls);
    let result =
        if requirements.is_empty() && requirement_files.is_empty() && pyproject_files.len() == 1 {
            let path = require_file(&pyproject_files[0])?;
            resolve_pyproject(py, path, indexes.as_deref())?
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
                parse_requirement(requirement, Path::new("."), false, &mut inputs)?;
            }
            let directory = tempdir()?;
            let path = directory.path().join("pyproject.toml");
            fs::write(&path, render_pyproject(&inputs))?;
            resolve_pyproject(py, &path, None)?
        };
    adapt_result(&result)
}

fn resolve_indexes(index_url: Option<&str>, extra_index_urls: &[String]) -> Option<Vec<Index>> {
    // Empty values fall through so `PIP_INDEX_URL=` keeps the PyPI default, like pip's or-chain.
    let primary = index_url
        .map(ToOwned::to_owned)
        .filter(|value| !value.is_empty())
        .or_else(|| {
            env::var("PIP_INDEX_URL")
                .ok()
                .filter(|value| !value.is_empty())
        })
        .or_else(|| {
            env::var("UV_INDEX_URL")
                .ok()
                .filter(|value| !value.is_empty())
        });
    let extras = if extra_index_urls.is_empty() {
        env::var("PIP_EXTRA_INDEX_URL")
            .or_else(|_| env::var("UV_EXTRA_INDEX_URL"))
            .map_or_else(
                |_| Vec::new(),
                |value| value.split_whitespace().map(ToOwned::to_owned).collect(),
            )
    } else {
        extra_index_urls.to_vec()
    };
    if primary.is_none() && extras.is_empty() {
        return None;
    }
    let mut indexes = vec![primary.map_or_else(
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
        url,
    }));
    Some(indexes)
}

fn parse_requirements_file(
    path: &Path,
    constraint: bool,
    inputs: &mut Inputs,
    stack: &mut Vec<PathBuf>,
) -> Result<(), Error> {
    let path = path.canonicalize()?;
    if stack.contains(&path) {
        return Err(Error::message(format!(
            "recursive requirements include: {}",
            path.display()
        )));
    }
    stack.push(path.clone());
    let content = fs::read_to_string(&path)?;
    let mut logical = String::new();
    for raw_line in content.lines() {
        let line = raw_line.trim();
        if line.ends_with('\\') {
            logical.push_str(line.trim_end_matches('\\').trim_end());
            logical.push(' ');
            continue;
        }
        logical.push_str(line);
        let line = strip_comment(&logical).trim();
        (!line.is_empty())
            .then(|| parse_requirements_line(line, &path, constraint, inputs, stack))
            .transpose()?;
        logical.clear();
    }
    if !logical.trim().is_empty() {
        parse_requirements_line(
            strip_comment(&logical).trim(),
            &path,
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
    source: &Path,
    constraint: bool,
    inputs: &mut Inputs,
    stack: &mut Vec<PathBuf>,
) -> Result<(), Error> {
    let base = source.parent().expect("canonical source file has a parent");
    // pip treats -r inside a constraints file as another constraints file.
    if let Some(value) = option_value(line, "-r", "--requirement") {
        return parse_requirements_file(&base.join(value), constraint, inputs, stack);
    }
    if let Some(value) = option_value(line, "-c", "--constraint") {
        return parse_requirements_file(&base.join(value), true, inputs, stack);
    }
    if let Some(value) = option_value(line, "-e", "--editable") {
        // pip accepts editable VCS URLs; the resolver has no editable mode for them, so they
        // map to plain VCS sources like the Python engine did.
        if value.trim_start().starts_with("git+") {
            return translate_source(value, base, inputs);
        }
        return add_local_source(value, base, true, inputs);
    }
    if line.starts_with('-') {
        return Ok(());
    }
    let requirement = line.split(" --hash=").next().unwrap_or(line).trim();
    parse_requirement(requirement, base, constraint, inputs)
}

fn parse_requirement(
    raw: &str,
    base: &Path,
    constraint: bool,
    inputs: &mut Inputs,
) -> Result<(), Error> {
    let requirement = match Requirement::<VerbatimUrl>::from_str(raw) {
        Ok(requirement) => requirement,
        Err(error) if looks_like_source(raw) && raw.contains(" @ ") => {
            return Err(Error::message(error.to_string()));
        }
        Err(_) if looks_like_source(raw) => {
            if constraint {
                return Err(Error::message("source requirements cannot be constraints"));
            }
            return translate_source(raw, base, inputs);
        }
        Err(error) => return Err(Error::message(error.to_string())),
    };
    if constraint {
        if matches!(requirement.version_or_url, Some(VersionOrUrl::Url(_))) {
            return Err(Error::message("source requirements cannot be constraints"));
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
        let path = url
            .to_file_path()
            .map_err(|()| Error::message(format!("invalid local file URL: {value}")))?;
        return add_local_source_path(&path, false, inputs);
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
    let path = PathBuf::from(raw);
    let path = if path.is_absolute() {
        path
    } else {
        base.join(path)
    };
    add_local_source_path(&path, editable, inputs)
}

fn add_local_source_path(path: &Path, editable: bool, inputs: &mut Inputs) -> Result<(), Error> {
    let path = path.canonicalize()?;
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
                build_policy: has_sources.then_some("build-remote"),
                vcs: (!inputs.vcs_sources.is_empty()).then_some(VcsPolicy {
                    policy: "allow",
                    allowed_schemes: GIT_SCHEMES,
                }),
                local_sources: inputs.local_sources.clone(),
                vcs_sources: inputs.vcs_sources.clone(),
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
) -> Result<pyo3::Bound<'py, pyo3::PyAny>, Error> {
    ResolverModules::import(py)?
        .resolve(py, path, indexes)
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
            config: import("nab_python.config")?,
            resolve: import("nab_python.resolve")?,
        })
    }

    fn resolve(
        &self,
        py: Python<'py>,
        path: &Path,
        indexes: Option<&[Index]>,
    ) -> PyResult<pyo3::Bound<'py, pyo3::PyAny>> {
        let pathlib = PyModule::import(py, "pathlib")?;
        let py_path = pathlib
            .getattr("Path")?
            .call1((path.to_string_lossy().as_ref(),))?;
        let mut config = self
            .config
            .getattr("read_pyproject_config")?
            .call1((&py_path,))?;
        if let Some(indexes) = indexes {
            let index_config = self.multi_index.getattr("IndexConfig")?;
            let configs = PyList::empty(py);
            for index in indexes {
                configs.append(index_config.call1((&index.name, &index.url))?)?;
            }
            let tuple = PyTuple::new(py, configs.iter())?;
            let kwargs = PyDict::new(py);
            kwargs.set_item("indexes", tuple)?;
            config = PyModule::import(py, "dataclasses")?
                .getattr("replace")?
                .call((&config,), Some(&kwargs))?;
        }
        let kwargs = PyDict::new(py);
        kwargs.set_item("config", config)?;
        let transport = self.transport.getattr("Urllib3AsyncTransport")?.call0()?;
        self.resolve
            .getattr("resolve_pyproject")?
            .call((&py_path, transport), Some(&kwargs))
    }
}

fn adapt_result(result: &pyo3::Bound<'_, pyo3::PyAny>) -> Result<Vec<Package>, Error> {
    let pins = result.getattr("pins")?;
    let mut versions = HashMap::new();
    for item in pins.call_method0("items")?.try_iter()? {
        let item = item?;
        let name: String = item.get_item(0)?.extract()?;
        let version = item.get_item(1)?.str()?.to_string_lossy().into_owned();
        versions.insert(name, version);
    }
    let dependencies = result
        .getattr("lock_input")?
        .getattr("dependencies")?
        .extract::<HashMap<String, Vec<String>>>()?;
    Ok(versions
        .iter()
        .map(|(name, version)| {
            let requires = dependencies
                .get(name)
                .into_iter()
                .flatten()
                .map(|child| {
                    versions
                        .get(child)
                        .map_or_else(|| child.clone(), |version| format!("{child}=={version}"))
                })
                .collect();
            Package::synthetic(name.clone(), version.clone(), requires)
        })
        .collect())
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
    let requirement = requirement.trim();
    requirement.contains("://")
        || ["./", "../", "/", "file:", "git+"]
            .iter()
            .any(|prefix| requirement.starts_with(prefix))
        || Path::new(requirement).join("pyproject.toml").is_file()
}
