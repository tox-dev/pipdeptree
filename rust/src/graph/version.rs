use std::collections::BTreeSet;
use std::path::PathBuf;

use pyo3::exceptions::{PyAttributeError, PyImportError};
use pyo3::prelude::{PyAnyMethods, PyModule};
use pyo3::types::PyList;
use pyo3::{Bound, PyResult, Python};

use super::Graph;

impl Graph {
    pub fn resolve_missing_versions(&mut self, py: Python<'_>, paths: &[PathBuf]) -> PyResult<()> {
        // The lookup is scoped to the inspected environment; consulting the host interpreter
        // would report packages installed alongside pipdeptree as installed there.
        let search = PyList::new(py, paths.iter().map(|path| path.to_string_lossy()))?;
        // Only dependencies that can render matter; resolving inactive extras would import
        // arbitrary modules (and run their side effects) for packages never shown.
        let names = (0..self.nodes.len())
            .filter(|index| self.visible[*index])
            .flat_map(|index| self.expanded_children(index))
            .filter(|dependency| dependency.target.is_none())
            .map(|dependency| dependency.key().to_string())
            .collect::<BTreeSet<_>>();
        for name in names {
            if let Some(version) = module_version(py, &name, &search)? {
                self.missing_versions.insert(name, version);
            }
        }
        Ok(())
    }
}

// A module found on the inspected paths may carry __version__ even without dist metadata; it is
// loaded through PathFinder so the host's own copy of the module never answers.
fn module_version(
    py: Python<'_>,
    name: &str,
    search: &Bound<'_, PyList>,
) -> PyResult<Option<String>> {
    let finder = PyModule::import(py, "importlib.machinery")?.getattr("PathFinder")?;
    let spec = finder.call_method1("find_spec", (name, search))?;
    if spec.is_none() {
        return Ok(None);
    }
    let module =
        PyModule::import(py, "importlib.util")?.call_method1("module_from_spec", (&spec,))?;
    match spec
        .getattr("loader")?
        .call_method1("exec_module", (&module,))
    {
        Ok(_) => {}
        Err(error) if error.is_instance_of::<PyImportError>(py) => return Ok(None),
        Err(error) => return Err(error),
    }
    let value = match module.getattr("__version__") {
        Ok(value) => value,
        Err(error) if error.is_instance_of::<PyAttributeError>(py) => return Ok(None),
        Err(error) => return Err(error),
    };
    if let Ok(version) = value.extract() {
        return Ok(Some(version));
    }
    match value.getattr("__version__") {
        Ok(value) => value.extract().map(Some),
        Err(error) if error.is_instance_of::<PyAttributeError>(py) => Ok(None),
        Err(error) => Err(error),
    }
}
