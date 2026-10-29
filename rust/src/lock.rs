use std::collections::HashMap;
use std::fs;
use std::path::Path;
use std::str::FromStr;

use pep508_rs::{MarkerEnvironment, MarkerTree};
use serde::Deserialize;

use crate::Error;
use crate::metadata::{
    Discovered, MAX_IDENTITY_LENGTH, Package, canonicalize_name, oversized_identity, printable,
};

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

pub fn load(path: &Path, marker: &MarkerEnvironment) -> Result<Discovered, Error> {
    if !path.is_file() {
        return Err(Error::message(format!(
            "lock file does not exist: {}",
            path.display()
        )));
    }
    let content = fs::read_to_string(path)?;
    let lock: Lock = toml::from_str(&content).map_err(|error| parse_error(&content, &error))?;
    // PEP 751 tools must refuse a lock whose major version they do not implement.
    if let Some(version) = &lock.lock_version
        && version.split('.').next() != Some("1")
    {
        return Err(Error::message(format!(
            "unsupported lock-version: {}",
            printable(version)
        )));
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
            if let Some(field) = oversized_identity(&name, &package.version) {
                return Err(Error::message(format!(
                    "package '{field}' is longer than {MAX_IDENTITY_LENGTH} bytes"
                )));
            }
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
                .collect::<Vec<_>>();
            Ok(Package::synthetic(&name, &package.version, &requires))
        })
        .collect::<Result<Vec<_>, _>>()
        .map(Discovered::new)
}

// The Display form of a toml error quotes the source line, and the lock path can be a symlink to
// any readable file, so the error reports only the position and the parser's message.
fn parse_error(content: &str, error: &toml::de::Error) -> Error {
    let before = &content[..error.span().map_or(0, |span| span.start)];
    let line_start = before.rfind('\n').map_or(0, |index| index + 1);
    Error::message(format!(
        "malformed TOML at line {}, column {}: {}",
        before.matches('\n').count() + 1,
        before[line_start..].chars().count() + 1,
        error.message()
    ))
}

fn applies(marker: Option<&str>, environment: &MarkerEnvironment) -> bool {
    // An unparsable marker cannot be shown to exclude the package, so the entry stays.
    marker.is_none_or(|marker| {
        MarkerTree::from_str(marker).map_or(true, |tree| tree.evaluate(environment, &[]))
    })
}
