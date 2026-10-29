use std::collections::{BTreeMap, BTreeSet, HashMap};

use rayon::prelude::*;
use rustc_hash::FxHashSet as HashSet;
use serde::Serialize;
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
pub use vcs::reset_caches as reset_vcs_caches;

const MAX_LICENSE_NAME: usize = 64;
// An installed name and version form the .dist-info directory name, which common file systems cap
// at 255 bytes, so a package installed on one of them stays within this limit.
pub const MAX_IDENTITY_LENGTH: usize = 255;
const ARCHIVE_SUFFIXES: [&str; 5] = ["egg", "pyz", "pyzw", "whl", "zip"];

#[derive(Debug)]
pub struct Package {
    pub name: String,
    pub key: String,
    pub version: String,
    pub requires: Vec<String>,
    metadata: Headers,
    metadata_dir: Option<PathBuf>,
    legacy_editable: Option<PathBuf>,
    size: OnceLock<u64>,
    frozen: OnceLock<String>,
    license: OnceLock<String>,
}

#[derive(Debug)]
pub struct DiscoveryWarning {
    pub message: String,
    pub failure: bool,
}

#[derive(Clone, Debug, Serialize)]
pub struct ResolvedDeclaration {
    pub requirement_text: String,
    pub dependency_specifier: String,
    pub requirement_condition: Option<String>,
    pub dependency_extras: Vec<String>,
    pub required_for_parent_extras: Vec<String>,
    pub required_without_parent_extras: bool,
}

#[derive(Clone, Debug)]
pub struct ResolvedEdge {
    pub child: String,
    pub declaration: Option<ResolvedDeclaration>,
}

// The common currency of every package source (installed environment, lock file, index resolve):
// the packages to render plus any environment-level warnings gathered while finding them.
#[derive(Debug)]
pub struct Discovered {
    pub packages: Vec<Package>,
    pub warnings: Vec<DiscoveryWarning>,
    pub resolved_edges: Option<HashMap<String, Vec<ResolvedEdge>>>,
}

impl Discovered {
    pub const fn new(packages: Vec<Package>) -> Self {
        Self {
            packages,
            warnings: Vec::new(),
            resolved_edges: None,
        }
    }
}

#[derive(Debug)]
struct Header {
    name: String,
    values: Vec<String>,
}

#[derive(Debug, Default)]
struct Headers(Vec<Header>);

impl Package {
    // A package resolved from a lock file or index has no on-disk dist-info: metadata() and
    // license() therefore report N/A, and size is seeded to 0 (rather than left lazy) because
    // compute_size has no metadata_dir to read and callers never ask a resolved package for it.
    pub fn synthetic(name: &str, version: &str, requires: &[String]) -> Self {
        let name = printable(name);
        Self {
            key: canonicalize_name(&name),
            name,
            version: printable(version),
            requires: requires
                .iter()
                .map(|requirement| printable(requirement))
                .collect(),
            metadata: Headers::default(),
            metadata_dir: None,
            legacy_editable: None,
            size: OnceLock::from(0),
            frozen: OnceLock::new(),
            license: OnceLock::new(),
        }
    }

    pub fn metadata(&self, field: &str) -> Vec<String> {
        if field.eq_ignore_ascii_case("license") {
            // license() wraps its value in one pair of parentheses; a value of its own (such as
            // "GPL v3 (GPLv3+)") keeps the parentheses it carries.
            let license = self.license();
            let value = license
                .strip_prefix('(')
                .and_then(|value| value.strip_suffix(')'))
                .unwrap_or(&license)
                .to_string();
            return vec![if value.to_ascii_lowercase().contains("license") {
                value
            } else {
                format!("{value} License")
            }];
        }
        // The stored header names are lowercased at parse time; lowercase the caller's field once
        // so the lookup compares bytes directly rather than case-insensitively per header.
        self.metadata
            .get_all(&field.to_ascii_lowercase())
            .map_or_else(|| vec!["N/A".to_string()], ToOwned::to_owned)
    }

    pub fn license(&self) -> String {
        self.license.get_or_init(|| self.compute_license()).clone()
    }

    fn compute_license(&self) -> String {
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
        if !licenses.is_empty() {
            return format!("({})", licenses.join(", "));
        }
        // The License field predates License-Expression and stays valid metadata, but it is free
        // text and some projects paste the whole license into it. Folding joins its continuation
        // lines into one value, so only an identifier-length one names a license.
        self.metadata
            .first("license")
            .filter(|value| !value.is_empty() && value.chars().count() <= MAX_LICENSE_NAME)
            .map_or_else(|| "(N/A)".to_string(), |value| format!("({value})"))
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
        if let Ok(content) = fs::read_to_string(metadata_dir.join("direct_url.json"))
            && let Ok(direct) = DirectUrl::parse(&content)
        {
            if direct.editable() {
                if let Some(location) = file_url_to_path(&direct.url) {
                    return vcs::editable_requirement(
                        processes,
                        &location,
                        &requirement_text(&self.name),
                        &requirement_text(&self.version),
                    );
                }
            } else {
                return self.direct_specifier(&direct);
            }
        }
        if let Some(location) = &self.legacy_editable {
            return vcs::editable_requirement(
                processes,
                location,
                &requirement_text(&self.name),
                &requirement_text(&self.version),
            );
        }
        self.regular_specifier()
    }

    fn direct_specifier(&self, direct: &DirectUrl) -> String {
        let mut result = format!("{} @ ", requirement_text(&self.name));
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
        let name = requirement_text(&self.name);
        let version = requirement_text(&self.version);
        if Version::from_str(&version).is_ok() {
            format!("{name}=={version}")
        } else {
            format!("{name}==={version}")
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
        if oversized_identity(&name, &version).is_some() {
            return Ok(None);
        }
        let requires = metadata
            .get_all("requires-dist")
            .map_or_else(Vec::new, <[String]>::to_vec);
        if let Some(retained_fields) = retained_fields {
            metadata.retain(retained_fields);
        }
        Ok(Some(Self {
            key: canonicalize_name(&name),
            name,
            version,
            requires,
            metadata,
            metadata_dir: Some(metadata_dir),
            legacy_editable: None,
            size: OnceLock::new(),
            frozen: OnceLock::new(),
            license: OnceLock::new(),
        }))
    }

    fn compute_size(&self) -> u64 {
        let metadata_dir = self
            .metadata_dir
            .as_ref()
            .expect("resolved package sizes are initialized at construction");
        let site = metadata_dir.parent().unwrap_or(metadata_dir);
        let Ok(file) = fs::File::open(metadata_dir.join("RECORD")) else {
            return 0;
        };
        // RECORD rows come from whoever built the distribution, so a row counts only when it
        // resolves to a regular file inside the installation. pip records console scripts and data
        // files relative to the site directory (`../../../bin/demo`), so the boundary is the prefix
        // that holds the site directory. A dist-info linked in from elsewhere (Nix profiles,
        // symlink farms) keeps its files under the prefix of its real location.
        let prefixes = [
            site.canonicalize().ok(),
            metadata_dir
                .canonicalize()
                .ok()
                .and_then(|directory| directory.parent().map(Path::to_path_buf)),
        ]
        .into_iter()
        .flatten()
        .map(|site| Self::installation_prefix(&site).to_path_buf())
        .collect::<Vec<_>>();
        let inside = |path: &Path| prefixes.iter().any(|prefix| path.starts_with(prefix));
        // A distribution has far fewer directories than files: resolve each directory once and
        // resolve a file on its own only when it is a link.
        let mut directories = HashMap::<PathBuf, Option<PathBuf>>::new();
        csv::ReaderBuilder::new()
            .has_headers(false)
            .from_reader(file)
            .records()
            .filter_map(Result::ok)
            .filter_map(|row| {
                let path = site.join(row.get(0)?);
                let parent = path.parent()?;
                if !directories.contains_key(parent) {
                    let resolved = parent
                        .canonicalize()
                        .ok()
                        .filter(|directory| inside(directory));
                    directories.insert(parent.to_path_buf(), resolved);
                }
                let file = directories[parent].as_ref()?.join(path.file_name()?);
                let metadata = fs::symlink_metadata(&file).ok()?;
                if metadata.is_symlink() {
                    fs::metadata(file.canonicalize().ok().filter(|target| inside(target))?).ok()
                } else {
                    Some(metadata)
                }
            })
            .filter(fs::Metadata::is_file)
            .map(|metadata| metadata.len())
            .sum()
    }

    // lib/pythonX.Y/site-packages (POSIX, Debian dist-packages, PyPy, macOS user site),
    // Lib/site-packages (Windows) and PythonXY/site-packages (Windows user site); any other
    // directory, such as a --target install, is its own prefix.
    fn installation_prefix(site: &Path) -> &Path {
        let [own, parent, grandparent] = [0, 1, 2].map(|level| {
            site.ancestors()
                .nth(level)
                .and_then(Path::file_name)
                .map_or_else(String::new, |name| {
                    name.to_string_lossy().to_ascii_lowercase()
                })
        });
        let levels = if !matches!(own.as_str(), "site-packages" | "dist-packages") {
            0
        } else if (parent.starts_with("python") || parent.starts_with("pypy"))
            && grandparent.starts_with("lib")
        {
            3
        } else if parent == "lib" {
            2
        } else {
            usize::from(parent.starts_with("python"))
        };
        site.ancestors()
            .nth(levels)
            .expect("every matched name has a parent directory")
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
                    value.push_str(&printable(line.trim()));
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
            headers[position].values.push(printable(value.trim()));
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
            .find(|header| header.name == field)
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
) -> Result<Discovered, Error> {
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
        retained_fields.extend([
            "classifier".to_string(),
            "license".to_string(),
            "license-expression".to_string(),
        ]);
    }
    if summary {
        retained_fields.insert("requires-python".to_string());
    }
    discover_with_fields(paths, Some(&retained_fields))
}

fn discover_with_fields(
    paths: &[PathBuf],
    retained_fields: Option<&HashSet<String>>,
) -> Result<Discovered, Error> {
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
    let mut legacy_editables = EggLinks::new(search_paths.len());
    let mut invalid_paths = BTreeSet::new();
    let mut duplicates = BTreeMap::<PathBuf, Vec<(String, String, String, PathBuf)>>::new();
    let mut seen = BTreeMap::<String, (String, PathBuf)>::new();
    let mut archive_paths = BTreeSet::new();
    // Walking directories is cheap; reading and parsing each METADATA dominates discovery. Collect
    // the entries sequentially (preserving search-path and directory order for a deterministic
    // dedup), parse them across cores, then fold the results back in the same order.
    let mut candidates = Vec::new();
    for (search, path) in search_paths.iter().enumerate() {
        let Ok(entries) = fs::read_dir(path) else {
            // Nonexistent sys.path entries are routine; a file (zipped egg, zipapp) held
            // packages the old importlib-based discovery listed, so losing it deserves a warning.
            if is_archive(path) {
                archive_paths.insert(path.clone());
            }
            continue;
        };
        for entry in entries.filter_map(Result::ok) {
            candidates.push((search, path.clone(), entry.path()));
        }
    }
    let found = candidates
        .par_iter()
        .filter_map(|(search, path, entry)| classify(*search, path, entry, retained_fields))
        .collect::<Vec<_>>();
    let mut packages = Vec::new();
    for entry in found {
        match entry {
            Found::EggLink(search, path) => legacy_editables.insert(search, &path),
            Found::Invalid(path) => {
                invalid_paths.insert(path);
            }
            Found::Package(package, path)
                if let Some((version, first_path)) = seen.get(&package.key) =>
            {
                duplicates.entry(path).or_default().push((
                    package.name,
                    package.version,
                    version.clone(),
                    first_path.clone(),
                ));
            }
            Found::Package(package, path) => {
                seen.insert(package.key.clone(), (package.version.clone(), path.clone()));
                packages.push(*package);
            }
        }
    }
    for package in &mut packages {
        package.legacy_editable = legacy_editables.find(&package.name).cloned();
    }
    Ok(Discovered {
        packages,
        warnings: path_warnings(&archive_paths, &invalid_paths, duplicates),
        resolved_edges: None,
    })
}

// Windows puts the console-script launcher itself on sys.path[0] (a zip appended to an .exe), and it
// never holds installed distributions; only a recognized archive suffix is worth warning about.
fn is_archive(path: &Path) -> bool {
    path.extension().is_some_and(|suffix| {
        ARCHIVE_SUFFIXES
            .iter()
            .any(|known| suffix.eq_ignore_ascii_case(known))
    }) && path.is_file()
}

enum Found {
    EggLink(usize, PathBuf),
    Package(Box<Package>, PathBuf),
    Invalid(PathBuf),
}

// Stat and parse one directory entry off the main thread. The path carried alongside a package is
// its search-path root, which the caller uses for duplicate and invalid-metadata reporting.
fn classify(
    search: usize,
    path: &Path,
    entry: &Path,
    retained_fields: Option<&HashSet<String>>,
) -> Option<Found> {
    // DirEntry::metadata does not traverse links; symlinked dist-info directories are a normal
    // layout (Nix, Debian, symlink installs), so stat the target.
    let kind = fs::metadata(entry).ok()?.file_type();
    let name = entry.file_name()?.to_string_lossy();
    if kind.is_file() && name.ends_with(".egg-link") {
        // Its first line reaches the freeze output: through a link, that of any readable file.
        return (!entry.is_symlink()).then(|| Found::EggLink(search, entry.to_path_buf()));
    }
    let (metadata_file, package_metadata_dir) = if kind.is_dir() && name.ends_with(".dist-info") {
        (entry.join("METADATA"), entry.to_path_buf())
    } else if kind.is_dir() && name.ends_with(".egg-info") {
        (entry.join("PKG-INFO"), entry.to_path_buf())
    } else if kind.is_file() && name.ends_with(".egg-info") {
        (entry.to_path_buf(), path.to_path_buf())
    } else {
        return None;
    };
    Some(
        match Package::from_metadata(package_metadata_dir, &metadata_file, retained_fields) {
            Ok(Some(package)) => Found::Package(Box::new(package), path.to_path_buf()),
            _ => Found::Invalid(path.to_path_buf()),
        },
    )
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
        if io::BufRead::read_line(&mut reader, &mut headers)? == 0
            || matches!(&headers[start..], "\n" | "\r\n")
        {
            headers.truncate(start);
            return Ok(headers);
        }
        if headers.ends_with("\r\n") {
            headers.truncate(headers.len() - 2);
            headers.push('\n');
        }
    }
}

// Warnings and reverse renderers copy a package's name and version once per requirement or edge,
// so an unbounded one makes the output grow with the product of its length and the edge count.
pub const fn oversized_identity(name: &str, version: &str) -> Option<&'static str> {
    if name.len() > MAX_IDENTITY_LENGTH {
        Some("name")
    } else if version.len() > MAX_IDENTITY_LENGTH {
        Some("version")
    } else {
        None
    }
}

// Package strings reach terminals, which act on ESC, BEL, CR and C1 sequences, and `dot`, which
// stops reading a line at NUL. U+FFFD keeps the tampering visible where dropping the character
// would hide it.
pub fn printable(value: &str) -> String {
    value
        .chars()
        .map(|character| {
            if character.is_control() && character != '\t' {
                char::REPLACEMENT_CHARACTER
            } else {
                character
            }
        })
        .collect()
}

// Freeze output is a pip requirements file, read line by line: a line break starts a new line, a
// leading '-' an option and '#' a comment, and a "coding:" in a comment on the first two lines
// makes pip decode the whole file with that codec (PEP 263). Valid project names and versions use
// none of these characters, so '?' replaces anything outside their alphabet and a leading
// non-alphanumeric.
fn requirement_text(value: &str) -> String {
    value
        .char_indices()
        .map(|(index, character)| {
            if character.is_ascii_alphanumeric()
                || (index > 0 && matches!(character, '.' | '_' | '-' | '!' | '+'))
            {
                character
            } else {
                '?'
            }
        })
        .collect()
}

// PEP 503: collapse each separator run to '-' and lowercase, keeping boundary separators.
pub fn canonicalize_name(name: &str) -> String {
    let mut result = String::with_capacity(name.len());
    let mut separator = false;
    for character in name.chars().flat_map(char::to_lowercase) {
        if matches!(character, '-' | '_' | '.') {
            separator = true;
        } else {
            if separator {
                result.push('-');
                separator = false;
            }
            result.push(character);
        }
    }
    if separator {
        result.push('-');
    }
    result
}
