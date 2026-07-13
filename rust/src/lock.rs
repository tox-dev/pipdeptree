use std::collections::HashMap;
use std::fs;
use std::path::Path;

use serde::Deserialize;

use crate::Error;
use crate::metadata::{Package, canonicalize_name};

#[derive(Debug, Deserialize)]
struct Lock {
    packages: Option<toml::Value>,
}

#[derive(Debug, Deserialize)]
struct LockPackage {
    name: Option<String>,
    #[serde(default)]
    version: String,
    #[serde(default)]
    dependencies: Vec<LockDependency>,
}

#[derive(Debug, Deserialize)]
struct LockDependency {
    name: String,
}

pub fn load(path: &Path) -> Result<Vec<Package>, Error> {
    if !path.is_file() {
        return Err(Error::message(format!(
            "lock file does not exist: {}",
            path.display()
        )));
    }
    let content = fs::read_to_string(path)?;
    let lock: Lock = toml::from_str(&content)
        .map_err(|error| Error::message(format!("malformed TOML: {error}")))?;
    let packages = lock
        .packages
        .filter(toml::Value::is_array)
        .ok_or_else(|| Error::message("missing 'packages' array"))?;
    let packages = match packages.try_into::<Vec<LockPackage>>() {
        Ok(packages) => packages,
        Err(error) => return Err(Error::message(format!("malformed TOML: {error}"))),
    };
    let versions = packages
        .iter()
        .filter_map(|package| {
            package
                .name
                .as_ref()
                .map(|name| (canonicalize_name(name), package.version.clone()))
        })
        .collect::<HashMap<_, _>>();
    packages
        .into_iter()
        .map(|package| {
            let name = package
                .name
                .ok_or_else(|| Error::message("package is missing 'name'"))?;
            let requires = package
                .dependencies
                .into_iter()
                .map(|dependency| {
                    versions
                        .get(&canonicalize_name(&dependency.name))
                        .map_or_else(
                            || dependency.name.clone(),
                            |version| {
                                if version.is_empty() {
                                    dependency.name.clone()
                                } else {
                                    format!("{}=={version}", dependency.name)
                                }
                            },
                        )
                })
                .collect();
            Ok(Package::synthetic(name, package.version, requires))
        })
        .collect()
}
