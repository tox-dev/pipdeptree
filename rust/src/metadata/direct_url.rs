use std::collections::BTreeMap;

use serde_json::{Map, Value};

#[derive(Debug)]
pub(super) struct DirectUrl {
    pub(super) url: String,
    pub(super) subdirectory: Option<String>,
    pub(super) info: DirectInfo,
}

#[derive(Debug)]
pub(super) enum DirectInfo {
    Vcs(VcsInfo),
    Archive(ArchiveInfo),
    Directory { editable: bool },
}

#[derive(Debug)]
pub(super) struct VcsInfo {
    pub(super) vcs: String,
    pub(super) commit_id: Option<String>,
    pub(super) requested_revision: Option<String>,
}

#[derive(Debug)]
pub(super) struct ArchiveInfo {
    pub(super) hashes: BTreeMap<String, String>,
}

impl DirectUrl {
    pub(super) fn parse(content: &str) -> Result<Self, String> {
        let value: Value = serde_json::from_str(content).map_err(|error| error.to_string())?;
        let object = value
            .as_object()
            .ok_or_else(|| "direct_url.json must be a JSON object".to_string())?;
        let url = string_field(object, "url", true)?
            .expect("required URL was checked")
            .to_string();
        let subdirectory = string_field(object, "subdirectory", false)?.map(ToOwned::to_owned);
        let infos = ["vcs_info", "archive_info", "dir_info"]
            .into_iter()
            .filter(|name| object.contains_key(*name))
            .collect::<Vec<_>>();
        if infos.len() != 1 {
            return Err("direct_url.json must contain exactly one info block".to_string());
        }
        let name = infos[0];
        let info = object[name]
            .as_object()
            .ok_or_else(|| format!("{name} must be an object"))?;
        let info = if name == "vcs_info" {
            DirectInfo::Vcs(parse_vcs(info)?)
        } else if name == "archive_info" {
            DirectInfo::Archive(parse_archive(info)?)
        } else {
            DirectInfo::Directory {
                editable: bool_field(info, "editable")?.unwrap_or(false),
            }
        };
        Ok(Self {
            url,
            subdirectory,
            info,
        })
    }

    pub(super) const fn editable(&self) -> bool {
        matches!(self.info, DirectInfo::Directory { editable: true })
    }

    pub(super) fn redacted_url(&self) -> String {
        redact_url(
            &self.url,
            matches!(&self.info, DirectInfo::Vcs(info) if info.vcs == "git"),
        )
    }
}

impl VcsInfo {
    pub(super) fn reference(&self) -> Option<&str> {
        self.commit_id
            .as_deref()
            .or(self.requested_revision.as_deref())
    }
}

impl ArchiveInfo {
    pub(super) fn hash_fragment(&self) -> Option<String> {
        self.hashes
            .first_key_value()
            .map(|(algorithm, digest)| format!("{algorithm}={digest}"))
    }
}

fn parse_vcs(object: &Map<String, Value>) -> Result<VcsInfo, String> {
    Ok(VcsInfo {
        vcs: string_field(object, "vcs", true)?
            .expect("required VCS was checked")
            .to_string(),
        commit_id: string_field(object, "commit_id", false)?.map(ToOwned::to_owned),
        requested_revision: string_field(object, "requested_revision", false)?
            .map(ToOwned::to_owned),
    })
}

fn parse_archive(object: &Map<String, Value>) -> Result<ArchiveInfo, String> {
    let hash = string_field(object, "hash", false)?.map(ToOwned::to_owned);
    if hash.as_deref().is_some_and(|value| {
        value
            .split_once('=')
            .is_none_or(|(algorithm, digest)| algorithm.is_empty() || digest.is_empty())
    }) {
        return Err("archive_info.hash must contain an algorithm and digest".to_string());
    }
    let mut hashes = BTreeMap::new();
    if let Some(value) = object.get("hashes") {
        let object = value
            .as_object()
            .ok_or_else(|| "archive_info.hashes must be an object".to_string())?;
        for (algorithm, digest) in object {
            hashes.insert(
                algorithm.clone(),
                match digest {
                    Value::String(digest) => digest.clone(),
                    digest => digest.to_string(),
                },
            );
        }
    }
    if hashes.is_empty() {
        if let Some(hash) = &hash {
            let (algorithm, digest) = hash
                .split_once('=')
                .expect("archive hash syntax was validated");
            hashes.insert(algorithm.to_string(), digest.to_string());
        }
    }
    Ok(ArchiveInfo { hashes })
}

fn string_field<'a>(
    object: &'a Map<String, Value>,
    name: &str,
    required: bool,
) -> Result<Option<&'a str>, String> {
    match object.get(name) {
        Some(value) => value
            .as_str()
            .map(Some)
            .ok_or_else(|| format!("{name} must be a string")),
        None if required => Err(format!("missing required {name}")),
        None => Ok(None),
    }
}

fn bool_field(object: &Map<String, Value>, name: &str) -> Result<Option<bool>, String> {
    object.get(name).map_or(Ok(None), |value| {
        value
            .as_bool()
            .map(Some)
            .ok_or_else(|| format!("{name} must be a boolean"))
    })
}

fn redact_url(url: &str, preserve_git: bool) -> String {
    let Some((scheme, rest)) = url.split_once("://") else {
        return url.to_string();
    };
    if scheme.is_empty()
        || !scheme
            .chars()
            .all(|character| character.is_ascii_alphabetic() || character == '+')
    {
        return url.to_string();
    }
    // Credentials live in the authority; an @ later in the URL is path or fragment data.
    let (authority, path) = rest
        .split_once('/')
        .map_or((rest, None), |(authority, path)| (authority, Some(path)));
    let Some((credentials, host)) = authority.split_once('@') else {
        return url.to_string();
    };
    if (preserve_git && credentials == "git") || environment_credentials(credentials) {
        return url.to_string();
    }
    path.map_or_else(
        || format!("{scheme}://{host}"),
        |path| format!("{scheme}://{host}/{path}"),
    )
}

fn environment_credentials(value: &str) -> bool {
    value.split_once(':').map_or_else(
        || environment_reference(value),
        |(user, password)| environment_reference(user) && environment_reference(password),
    )
}

fn environment_reference(value: &str) -> bool {
    value
        .strip_prefix("${")
        .and_then(|value| value.strip_suffix('}'))
        .is_some_and(|name| {
            !name.is_empty()
                && name.chars().all(|character| {
                    character.is_ascii_alphanumeric() || matches!(character, '_' | '-')
                })
        })
}
