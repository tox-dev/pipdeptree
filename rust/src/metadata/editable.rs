use std::collections::HashMap;
use std::fs;
use std::path::{Path, PathBuf};

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
            fs::read_to_string(path)
                .ok()?
                .lines()
                .next()
                .map(|target| (name.to_string_lossy(), PathBuf::from(target)))
        }) else {
            return;
        };
        self.0[search].insert(name.into_owned(), target);
    }

    pub(super) fn find(&self, package: &str) -> Option<&PathBuf> {
        for links in &self.0 {
            for name in egg_link_names(package) {
                if let Some(target) = links.get(&name) {
                    return Some(target);
                }
            }
        }
        None
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
