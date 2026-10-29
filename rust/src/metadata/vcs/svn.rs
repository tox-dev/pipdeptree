use std::fs;
use std::path::Path;

use crate::metadata::read_bounded;
use crate::process::ProcessRunner;

use super::shared::{
    CommandError, ExitStatusPolicy, VcsError, VcsRequirement, VcsResult, build_requirement,
    command, marker_root,
};

pub(super) struct Svn;

impl super::Vcs for Svn {
    fn root(
        &self,
        _processes: &dyn ProcessRunner,
        location: &Path,
    ) -> Result<Option<std::path::PathBuf>, VcsError> {
        Ok(marker_root(location, ".svn", true))
    }

    fn requirement(
        &self,
        processes: &dyn ProcessRunner,
        location: &Path,
        package: &str,
        root: &Path,
    ) -> VcsResult {
        let (info, failure) = match command(
            processes,
            "svn",
            &["info", "--xml"],
            location,
            ExitStatusPolicy::RequireSuccess,
        ) {
            Ok(output) => (parse_info(&output), VcsError::NoRemote),
            Err(CommandError::Failed) => (None, VcsError::NoRemote),
            Err(CommandError::TimedOut) => (None, VcsError::TimedOut),
            Err(CommandError::NotFound) => {
                return VcsResult::error(Some("svn"), VcsError::CommandNotFound);
            }
        };
        let Some((remote, revision)) = info.or_else(|| legacy_info(location)) else {
            return VcsResult::error(Some("svn"), failure);
        };
        build_requirement(VcsRequirement {
            vcs: "svn",
            remote: &remote,
            commit: &revision,
            package,
            location,
            root,
            always_prefix: true,
            include_subdirectory: false,
        })
    }
}

fn legacy_info(location: &Path) -> Option<(String, String)> {
    // Two lines of this file reach the freeze output; through a link they could come from any
    // readable file.
    let administrative = location.join(".svn");
    let entries = administrative.join("entries");
    (fs::symlink_metadata(&administrative).ok()?.is_dir()
        && fs::symlink_metadata(&entries).ok()?.is_file())
    .then_some(())?;
    let content = read_bounded(&entries).ok()?;
    parse_entries(&content)
}

fn parse_info(output: &str) -> Option<(String, String)> {
    let entry = output.split("<entry").nth(1)?.split('>').next()?;
    let revision = attribute(entry, "revision").unwrap_or_default();
    let url = output.split("<url>").nth(1)?.split("</url>").next()?.trim();
    (!url.is_empty()).then(|| (xml_unescape(url), revision))
}

fn attribute(element: &str, name: &str) -> Option<String> {
    let marker = format!(r#"{name}=""#);
    element
        .split(&marker)
        .nth(1)?
        .split('"')
        .next()
        .map(ToOwned::to_owned)
}

fn xml_unescape(value: &str) -> String {
    // &amp; goes last so a double-escaped entity like &amp;lt; decodes once, to &lt;.
    value
        .replace("&lt;", "<")
        .replace("&gt;", ">")
        .replace("&quot;", "\"")
        .replace("&apos;", "'")
        .replace("&amp;", "&")
}

fn parse_entries(content: &str) -> Option<(String, String)> {
    if content.starts_with("<?xml") {
        return None;
    }
    let lines = content.lines().collect::<Vec<_>>();
    let revision = lines.get(3)?.trim();
    let url = lines.get(4)?.trim();
    (!url.is_empty() && revision.parse::<u64>().is_ok())
        .then(|| (url.to_string(), revision.to_string()))
}
