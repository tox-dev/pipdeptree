use std::collections::HashMap;
use std::fs;
use std::path::Path;
use std::str::FromStr;

use pep508_rs::{MarkerEnvironment, MarkerTree};
use serde::Deserialize;

use crate::Error;
use crate::metadata::{Package, canonicalize_name};

#[derive(Debug, Deserialize)]
struct Lock {
    #[serde(rename = "lock-version")]
    lock_version: Option<String>,
    packages: Option<toml::Value>,
}

#[derive(Debug, Deserialize)]
struct LockPackage {
    name: Option<String>,
    #[serde(default)]
    version: String,
    marker: Option<String>,
    #[serde(default)]
    dependencies: Vec<LockDependency>,
}

#[derive(Debug, Deserialize)]
struct LockDependency {
    name: String,
}

pub fn load(path: &Path, marker: &MarkerEnvironment) -> Result<Vec<Package>, Error> {
    if !path.is_file() {
        return Err(Error::message(format!(
            "lock file does not exist: {}",
            path.display()
        )));
    }
    let content = fs::read_to_string(path)?;
    let lock: Lock = toml::from_str(&content)
        .map_err(|error| Error::message(format!("malformed TOML: {error}")))?;
    // PEP 751 tools must refuse a lock whose major version they do not implement.
    if let Some(version) = &lock.lock_version {
        if version.split('.').next() != Some("1") {
            return Err(Error::message(format!(
                "unsupported lock-version: {version}"
            )));
        }
    }
    let packages = lock
        .packages
        .filter(toml::Value::is_array)
        .ok_or_else(|| Error::message("missing 'packages' array"))?;
    let packages = match packages.try_into::<Vec<LockPackage>>() {
        Ok(packages) => packages,
        Err(error) => return Err(Error::message(format!("malformed TOML: {error}"))),
    };
    // A lock may hold several entries per package, disambiguated by their environment marker.
    let packages = packages
        .into_iter()
        .filter(|package| applies(package.marker.as_deref(), marker))
        .collect::<Vec<_>>();
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

fn applies(marker: Option<&str>, environment: &MarkerEnvironment) -> bool {
    // An unparseable marker cannot be shown to exclude the package, so the entry stays.
    marker.is_none_or(|marker| {
        MarkerTree::from_str(marker).map_or(true, |tree| tree.evaluate(environment, &[]))
    })
}
