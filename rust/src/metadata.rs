use std::collections::{BTreeMap, BTreeSet, HashSet};
use std::fmt::Write as _;
use std::fs;
use std::io;
use std::path::{Path, PathBuf};
use std::str::FromStr;
use std::sync::OnceLock;

use pep508_rs::pep440_rs::Version;

use crate::Error;
use crate::process::ProcessRunner;

mod direct_url;
mod editable;
mod vcs;

use direct_url::{DirectInfo, DirectUrl};
use editable::{EggLinks, file_url_to_path};

#[derive(Debug)]
pub struct Package {
    pub name: String,
    pub key: String,
    pub version: String,
    pub requires: Vec<String>,
    pub provides_extras: Vec<String>,
    metadata: Headers,
    metadata_dir: Option<PathBuf>,
    legacy_editable: Option<PathBuf>,
    size: OnceLock<u64>,
    frozen: OnceLock<String>,
}

#[derive(Debug)]
pub struct DiscoveryWarning {
    pub message: String,
    pub failure: bool,
}

#[derive(Debug)]
struct Header {
    name: String,
    values: Vec<String>,
}

#[derive(Debug, Default)]
struct Headers(Vec<Header>);

impl Package {
    pub fn synthetic(name: String, version: String, requires: Vec<String>) -> Self {
        Self {
            key: canonicalize_name(&name),
            name,
            version,
            requires,
            provides_extras: Vec::new(),
            metadata: Headers::default(),
            metadata_dir: None,
            legacy_editable: None,
            size: OnceLock::from(0),
            frozen: OnceLock::new(),
        }
    }

    pub fn metadata(&self, field: &str) -> Vec<String> {
        if field.eq_ignore_ascii_case("license") {
            let value = self.license().trim_matches(['(', ')']).to_string();
            return vec![if value.to_ascii_lowercase().contains("license") {
                value
            } else {
                format!("{value} License")
            }];
        }
        self.metadata
            .get_all(field)
            .map_or_else(|| vec!["N/A".to_string()], ToOwned::to_owned)
    }

    pub fn license(&self) -> String {
        if let Some(value) = self
            .metadata
            .first("license-expression")
            .filter(|value| !value.is_empty())
        {
            return format!("({value})");
        }
        let licenses = self
            .metadata
            .get_all("classifier")
            .into_iter()
            .flatten()
            .filter(|value| value.starts_with("License"))
            .map(|value| value.rsplit(":: ").next().unwrap_or(value))
            .collect::<Vec<_>>();
        if licenses.is_empty() {
            "(N/A)".to_string()
        } else {
            format!("({})", licenses.join(", "))
        }
    }

    pub fn requires_python(&self) -> Option<&str> {
        match self.metadata.get_all("requires-python") {
            Some([value]) => Some(value),
            _ => None,
        }
    }

    pub fn size(&self) -> u64 {
        *self.size.get_or_init(|| self.compute_size())
    }

    pub fn frozen(&self, processes: &dyn ProcessRunner) -> String {
        self.frozen
            .get_or_init(|| self.compute_frozen(processes))
            .clone()
    }

    fn compute_frozen(&self, processes: &dyn ProcessRunner) -> String {
        let Some(metadata_dir) = &self.metadata_dir else {
            return self.regular_specifier();
        };
        if let Ok(content) = fs::read_to_string(metadata_dir.join("direct_url.json")) {
            if let Ok(direct) = DirectUrl::parse(&content) {
                if direct.editable() {
                    if let Some(location) = file_url_to_path(&direct.url) {
                        return vcs::editable_requirement(
                            processes,
                            &location,
                            &self.name,
                            &self.version,
                        );
                    }
                } else {
                    return self.direct_specifier(&direct);
                }
            }
        }
        if let Some(location) = &self.legacy_editable {
            return vcs::editable_requirement(processes, location, &self.name, &self.version);
        }
        self.regular_specifier()
    }

    fn direct_specifier(&self, direct: &DirectUrl) -> String {
        let mut result = format!("{} @ ", self.name);
        match &direct.info {
            DirectInfo::Vcs(info) => {
                result.push_str(&info.vcs);
                result.push('+');
                result.push_str(&direct.redacted_url());
                if let Some(commit) = info.reference() {
                    result.push('@');
                    result.push_str(commit);
                }
            }
            DirectInfo::Archive(info) => {
                result.push_str(&direct.redacted_url());
                if let Some(hash) = info.hash_fragment() {
                    result.push('#');
                    result.push_str(&hash);
                }
            }
            DirectInfo::Directory { .. } => result.push_str(&direct.redacted_url()),
        }
        if let Some(subdirectory) = &direct.subdirectory {
            result.push(if result.contains('#') { '&' } else { '#' });
            result.push_str("subdirectory=");
            result.push_str(subdirectory);
        }
        result
    }

    fn regular_specifier(&self) -> String {
        if Version::from_str(&self.version).is_ok() {
            format!("{}=={}", self.name, self.version)
        } else {
            format!("{}==={}", self.name, self.version)
        }
    }

    fn from_metadata(
        metadata_dir: PathBuf,
        metadata_file: &Path,
        retained_fields: Option<&HashSet<String>>,
    ) -> Result<Option<Self>, Error> {
        let mut metadata = Headers::parse_selected(&read_headers(metadata_file)?, retained_fields);
        let Some(name) = metadata.first("name").map(ToOwned::to_owned) else {
            return Ok(None);
        };
        let version = metadata.first("version").unwrap_or("").to_string();
        let requires = metadata
            .get_all("requires-dist")
            .map_or_else(Vec::new, <[String]>::to_vec);
        let provides_extras = metadata
            .get_all("provides-extra")
            .map_or_else(Vec::new, <[String]>::to_vec);
        if let Some(retained_fields) = retained_fields {
            metadata.retain(retained_fields);
        }
        Ok(Some(Self {
            key: canonicalize_name(&name),
            name,
            version,
            requires,
            provides_extras,
            metadata,
            metadata_dir: Some(metadata_dir),
            legacy_editable: None,
            size: OnceLock::new(),
            frozen: OnceLock::new(),
        }))
    }

    fn compute_size(&self) -> u64 {
        let metadata_dir = self
            .metadata_dir
            .as_ref()
            .expect("resolved package sizes are initialized at construction");
        let record = metadata_dir.join("RECORD");
        let root = metadata_dir
            .parent()
            .expect("discovered metadata has a search-path parent");
        let Ok(file) = fs::File::open(record) else {
            return 0;
        };
        csv::ReaderBuilder::new()
            .has_headers(false)
            .from_reader(file)
            .records()
            .filter_map(Result::ok)
            .filter_map(|row| row.get(0).map(|path| root.join(path)))
            .filter_map(|path| fs::metadata(path).ok())
            .map(|metadata| metadata.len())
            .sum()
    }
}

impl Headers {
    fn parse_selected(content: &str, retained_fields: Option<&HashSet<String>>) -> Self {
        let mut headers: Vec<Header> = Vec::new();
        let mut current: Option<(usize, usize)> = None;
        // read_headers already stops at the body separator, so every line here is a header.
        for line in content.lines() {
            if line.starts_with([' ', '\t']) {
                if let Some((header, index)) = current {
                    let value = &mut headers[header].values[index];
                    value.push(' ');
                    value.push_str(line.trim());
                }
                continue;
            }
            let Some((key, value)) = line.split_once(':') else {
                current = None;
                continue;
            };
            let key = key.to_ascii_lowercase();
            if retained_fields.is_some_and(|fields| {
                !matches!(
                    key.as_str(),
                    "name" | "provides-extra" | "requires-dist" | "version"
                ) && !fields.contains(&key)
            }) {
                current = None;
                continue;
            }
            let position = headers
                .iter()
                .position(|header| header.name == key)
                .unwrap_or_else(|| {
                    headers.push(Header {
                        name: key,
                        values: Vec::new(),
                    });
                    headers.len() - 1
                });
            headers[position].values.push(value.trim().to_string());
            current = Some((position, headers[position].values.len() - 1));
        }
        Self(headers)
    }

    fn first(&self, field: &str) -> Option<&str> {
        self.get_all(field)
            .and_then(|values| values.first())
            .map(String::as_str)
    }

    fn get_all(&self, field: &str) -> Option<&[String]> {
        self.0
            .iter()
            .find(|header| header.name.eq_ignore_ascii_case(field))
            .map(|header| header.values.as_slice())
    }

    fn retain(&mut self, fields: &HashSet<String>) {
        self.0.retain(|header| fields.contains(&header.name));
    }
}

pub fn discover_selected(
    paths: &[PathBuf],
    metadata_fields: &[String],
    summary: bool,
) -> Result<(Vec<Package>, Vec<DiscoveryWarning>), Error> {
    let mut retained_fields = metadata_fields
        .iter()
        .filter(|field| !field.eq_ignore_ascii_case("license"))
        .map(|field| field.to_ascii_lowercase())
        .collect::<HashSet<_>>();
    if summary
        || metadata_fields
            .iter()
            .any(|field| field.eq_ignore_ascii_case("license"))
    {
        retained_fields.extend(["classifier".to_string(), "license-expression".to_string()]);
    }
    if summary {
        retained_fields.insert("requires-python".to_string());
    }
    discover_with_fields(paths, Some(&retained_fields))
}

fn discover_with_fields(
    paths: &[PathBuf],
    retained_fields: Option<&HashSet<String>>,
) -> Result<(Vec<Package>, Vec<DiscoveryWarning>), Error> {
    let search_paths = paths
        .iter()
        .map(|path| {
            if path.as_os_str().is_empty() {
                std::env::current_dir()
            } else {
                Ok(path.clone())
            }
        })
        .collect::<Result<Vec<_>, _>>()?;
    let mut packages = Vec::new();
    let mut legacy_editables = EggLinks::new(search_paths.len());
    let mut invalid_paths = BTreeSet::new();
    let mut duplicates = BTreeMap::<PathBuf, Vec<(String, String, String, PathBuf)>>::new();
    let mut seen = BTreeMap::<String, (String, PathBuf)>::new();
    let mut archive_paths = BTreeSet::new();
    for (search, path) in search_paths.iter().enumerate() {
        let Ok(entries) = fs::read_dir(path) else {
            // Nonexistent sys.path entries are routine; a file (zipped egg, zipapp) held
            // packages the old importlib-based discovery listed, so losing it deserves a warning.
            if path.is_file() {
                archive_paths.insert(path.clone());
            }
            continue;
        };
        for (entry, kind) in entries.filter_map(Result::ok).filter_map(|entry| {
            let kind = entry.file_type().ok()?;
            Some((entry, kind))
        }) {
            let metadata_dir = entry.path();
            let name = entry.file_name();
            let name = name.to_string_lossy();
            if kind.is_file() && name.ends_with(".egg-link") {
                legacy_editables.insert(search, &metadata_dir);
                continue;
            }
            let (metadata_file, package_metadata_dir) =
                if kind.is_dir() && name.ends_with(".dist-info") {
                    (metadata_dir.join("METADATA"), metadata_dir)
                } else if kind.is_dir() && name.ends_with(".egg-info") {
                    (metadata_dir.join("PKG-INFO"), metadata_dir)
                } else if kind.is_file() && name.ends_with(".egg-info") {
                    (metadata_dir, path.clone())
                } else {
                    continue;
                };
            let Ok(Some(package)) =
                Package::from_metadata(package_metadata_dir, &metadata_file, retained_fields)
            else {
                invalid_paths.insert(path.clone());
                continue;
            };
            if let Some((version, first_path)) = seen.get(&package.key) {
                duplicates.entry(path.clone()).or_default().push((
                    package.name,
                    package.version,
                    version.clone(),
                    first_path.clone(),
                ));
            } else {
                seen.insert(package.key.clone(), (package.version.clone(), path.clone()));
                packages.push(package);
            }
        }
    }
    for package in &mut packages {
        package.legacy_editable = legacy_editables.find(&package.name).cloned();
    }
    Ok((
        packages,
        path_warnings(&archive_paths, &invalid_paths, duplicates),
    ))
}

fn path_warnings(
    archive_paths: &BTreeSet<PathBuf>,
    invalid_paths: &BTreeSet<PathBuf>,
    duplicates: BTreeMap<PathBuf, Vec<(String, String, String, PathBuf)>>,
) -> Vec<DiscoveryWarning> {
    let mut warnings = Vec::new();
    if !archive_paths.is_empty() {
        warnings.push(DiscoveryWarning {
            message: format!(
                "Warning: unsupported archives on the search path; the packages inside are not listed:\n{}\n{}\n",
                archive_paths
                    .iter()
                    .map(|path| path.display().to_string())
                    .collect::<Vec<_>>()
                    .join("\n"),
                "-".repeat(72)
            ),
            failure: true,
        });
    }
    if !invalid_paths.is_empty() {
        warnings.push(DiscoveryWarning {
            message: format!(
                "Warning: missing or invalid metadata in these site directories:\n{}\n{}\n",
                invalid_paths
                    .iter()
                    .map(|path| path.display().to_string())
                    .collect::<Vec<_>>()
                    .join("\n"),
                "-".repeat(72)
            ),
            failure: true,
        });
    }
    if !duplicates.is_empty() {
        let mut warning = String::from("Warning: duplicate package metadata:\n");
        for (path, packages) in duplicates {
            writeln!(warning, "\"{}\"", path.display()).expect("writing to a string cannot fail");
            for (name, version, first_version, first_path) in packages {
                writeln!(
                    warning,
                    "  {name:<32} {version:<16} (using {first_version}, \"{}\")",
                    first_path.display()
                )
                .expect("writing to a string cannot fail");
            }
        }
        warning.push_str("NOTE: This warning isn't a failure warning.\n");
        warning.push_str(&"-".repeat(72));
        warning.push('\n');
        warnings.push(DiscoveryWarning {
            message: warning,
            failure: false,
        });
    }
    warnings
}

fn read_headers(path: &Path) -> Result<String, Error> {
    // METADATA bodies embed whole package descriptions; the headers end at the first blank
    // line, so stop reading there instead of loading the full file.
    let mut reader = io::BufReader::new(fs::File::open(path)?);
    let mut headers = String::new();
    loop {
        let start = headers.len();
        if io::BufRead::read_line(&mut reader, &mut headers)? == 0 || &headers[start..] == "\n" {
            headers.truncate(start);
            return Ok(headers);
        }
    }
}

pub fn canonicalize_name(name: &str) -> String {
    let mut result = String::with_capacity(name.len());
    let mut separator = false;
    for character in name.chars().flat_map(char::to_lowercase) {
        if matches!(character, '-' | '_' | '.') {
            separator = true;
        } else {
            if separator && !result.is_empty() {
                result.push('-');
            }
            result.push(character);
            separator = false;
        }
    }
    result
}
