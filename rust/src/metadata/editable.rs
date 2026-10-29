use std::collections::HashMap;
use std::path::{Path, PathBuf};

use super::read_bounded;

pub(super) fn file_url_to_path(value: &str) -> Option<PathBuf> {
    let url = url::Url::parse(value).ok()?;
    (url.scheme() == "file").then_some(())?;
    url.to_file_path().ok()
}

pub(super) struct EggLinks(Vec<HashMap<String, PathBuf>>);

impl EggLinks {
    pub(super) fn new(paths: usize) -> Self {
        Self((0..paths).map(|_| HashMap::new()).collect())
    }

    pub(super) fn insert(&mut self, search: usize, path: &Path) {
        let Some((name, target)) = path.file_name().and_then(|name| {
            read_bounded(path)
                .ok()?
                .lines()
                .next()
                .map(|target| (name.to_string_lossy(), PathBuf::from(target)))
        }) else {
            return;
        };
        self.0[search].insert(name.into_owned(), target);
    }

    // `setup.py develop` writes the directory that holds the project's .egg-info directory; a link
    // that names another directory, or a package installed another way, did not come from it.
    pub(super) fn find(&self, package: &str, metadata_dir: &Path) -> Option<&PathBuf> {
        if metadata_dir
            .extension()
            .is_none_or(|suffix| suffix != "egg-info")
        {
            return None;
        }
        let location = metadata_dir.parent()?.canonicalize().ok()?;
        let names = egg_link_names(package);
        self.0
            .iter()
            .flat_map(|links| names.iter().filter_map(|name| links.get(name)))
            .find(|target| target.canonicalize().is_ok_and(|target| target == location))
    }
}

fn egg_link_names(package: &str) -> Vec<String> {
    let mut safe = String::with_capacity(package.len());
    let mut separator = false;
    for character in package.chars() {
        if character.is_ascii_alphanumeric() || character == '.' {
            if separator {
                safe.push('-');
                separator = false;
            }
            safe.push(character);
        } else {
            separator = true;
        }
    }
    let safe_name = format!("{safe}.egg-link");
    if safe == package {
        vec![safe_name]
    } else {
        vec![safe_name, format!("{package}.egg-link")]
    }
}
