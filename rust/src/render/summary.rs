use std::collections::{BTreeMap, HashSet};
use std::str::FromStr;

use anstyle::Style;
use pep508_rs::pep440_rs::{Version, VersionSpecifiers};
use serde_json::json;

use crate::graph::Graph;
use crate::options::{Format, Options};

use super::shared::format_size;
use super::text::is_unicode;

pub(super) fn render(graph: &Graph, options: &Options, color: bool) -> String {
    let summary = Summary::new(graph, options.resolved());
    if options.output_format == Format::Json {
        return summary.json();
    }
    let rows = summary.rows();
    if options.output_format == Format::Rich {
        return rich_table(
            "environment summary",
            &rows,
            color,
            is_unicode(&options.encoding),
        );
    }
    let width = rows.iter().map(|(label, _)| label.len()).max().unwrap_or(0);
    rows.into_iter()
        .map(|(label, value)| format!("{:<width$} {value}", format!("{label}:"), width = width + 1))
        .collect::<Vec<_>>()
        .join("\n")
}

struct Summary {
    total: usize,
    direct: usize,
    max_depth: usize,
    cycles: usize,
    installed: Option<InstalledSummary>,
}

struct InstalledSummary {
    missing: usize,
    conflicting_packages: usize,
    conflicting_edges: usize,
    licenses: BTreeMap<String, usize>,
    min_requires_python: String,
    total_size: u64,
}

impl Summary {
    fn new(graph: &Graph, resolved: bool) -> Self {
        let total = graph.visible_indices().count();
        let direct = direct_dependencies(graph);
        let installed = (!resolved).then(|| {
            let (conflicting_packages, conflicting_edges) = graph.conflicts();
            InstalledSummary {
                missing: graph.missing_dependencies(),
                conflicting_packages,
                conflicting_edges,
                licenses: license_breakdown(graph),
                min_requires_python: min_requires_python(graph),
                total_size: graph
                    .visible_indices()
                    .map(|index| graph.nodes[index].package.size())
                    .sum(),
            }
        });
        Self {
            total,
            direct,
            max_depth: max_depth(graph),
            cycles: graph.cycle_count(),
            installed,
        }
    }

    fn rows(&self) -> Vec<(String, String)> {
        let mut rows = vec![
            ("total packages".to_string(), self.total.to_string()),
            ("direct dependencies".to_string(), self.direct.to_string()),
            (
                "transitive dependencies".to_string(),
                (self.total - self.direct).to_string(),
            ),
            ("max depth".to_string(), self.max_depth.to_string()),
            ("cyclic dependencies".to_string(), self.cycles.to_string()),
        ];
        let Some(installed) = &self.installed else {
            let note = "n/a (resolved from index/lock - package metadata unavailable)".to_string();
            rows.extend(
                [
                    "missing dependencies",
                    "conflicting dependencies",
                    "licenses",
                ]
                .map(|label| (label.to_string(), note.clone())),
            );
            return rows;
        };
        rows.extend([
            (
                "missing dependencies".to_string(),
                installed.missing.to_string(),
            ),
            (
                "conflicting dependencies".to_string(),
                format!(
                    "{} ({} edges)",
                    installed.conflicting_packages, installed.conflicting_edges
                ),
            ),
            ("licenses".to_string(), license_text(&installed.licenses)),
            (
                "unknown licenses".to_string(),
                installed
                    .licenses
                    .get("(N/A)")
                    .copied()
                    .unwrap_or(0)
                    .to_string(),
            ),
            (
                "copyleft licenses".to_string(),
                if has_copyleft(&installed.licenses) {
                    "yes"
                } else {
                    "no"
                }
                .to_string(),
            ),
            (
                "min requires-python".to_string(),
                installed.min_requires_python.clone(),
            ),
            ("total size".to_string(), format_size(installed.total_size)),
        ]);
        rows
    }

    fn json(&self) -> String {
        let mut value = json!({
            "total_packages": self.total,
            "direct_dependencies": self.direct,
            "transitive_dependencies": self.total - self.direct,
            "max_depth": self.max_depth,
            "cyclic_dependencies": self.cycles,
        });
        if let Some(installed) = &self.installed {
            value["missing_dependencies"] = json!(installed.missing);
            value["conflicting_dependencies"] = json!({
                "packages": installed.conflicting_packages,
                "edges": installed.conflicting_edges,
            });
            value["licenses"] = json!({
                "breakdown": installed.licenses,
                "unknown": installed.licenses.get("(N/A)").copied().unwrap_or(0),
                "copyleft": has_copyleft(&installed.licenses),
            });
            value["min_requires_python"] = json!(installed.min_requires_python);
            value["total_size"] = json!(format_size(installed.total_size));
            value["total_size_raw"] = json!(installed.total_size);
        }
        serde_json::to_string_pretty(&value).expect("serializing summary cannot fail")
    }
}

fn rich_table(title: &str, rows: &[(String, String)], color: bool, unicode: bool) -> String {
    let first = rows
        .iter()
        .map(|(label, _)| label.chars().count())
        .max()
        .unwrap_or(0);
    let second = rows
        .iter()
        .map(|(_, value)| value.chars().count())
        .max()
        .unwrap_or(0);
    let first_bar = if unicode { "━" } else { "-" }.repeat(first + 2);
    let second_bar = if unicode { "━" } else { "-" }.repeat(second + 2);
    let (top, vertical, bottom) = if unicode {
        (
            format!("┏{first_bar}┳{second_bar}┓"),
            "┃",
            format!("┗{first_bar}┻{second_bar}┛"),
        )
    } else {
        (
            format!("+{first_bar}+{second_bar}+"),
            "|",
            format!("+{first_bar}+{second_bar}+"),
        )
    };
    let width = first + second + 5;
    let mut lines = vec![format!("{:^width$}", title, width = width + 2), top];
    for (label, value) in rows {
        let label = if color {
            let style = Style::new().bold();
            format!("{style}{label:<first$}{style:#}")
        } else {
            format!("{label:<first$}")
        };
        lines.push(format!(
            "{vertical} {label} {vertical} {value:<second$} {vertical}"
        ));
    }
    lines.push(bottom);
    lines.join("\n")
}

fn max_depth(graph: &Graph) -> usize {
    let mut memo = vec![None; graph.nodes.len()];
    let mut on_path = vec![false; graph.nodes.len()];
    graph
        .roots(false, false)
        .into_iter()
        .map(|root| longest(graph, root, &mut on_path, &mut memo))
        .max()
        .unwrap_or(0)
}

fn direct_dependencies(graph: &Graph) -> usize {
    let transitive = graph
        .visible_indices()
        .flat_map(|index| graph.expanded_children(index))
        .filter_map(|dependency| dependency.target)
        .collect::<HashSet<_>>()
        .len();
    graph.visible_indices().count() - transitive
}

// Iterative post-order so a pathological chain cannot overflow the stack. A depth computed
// while a cycle member sat on the path depends on that path, so only cycle-free subtrees
// memoize; diamonds stay linear either way.
fn longest(graph: &Graph, start: usize, on_path: &mut [bool], memo: &mut [Option<usize>]) -> usize {
    let mut stack = vec![Frame::new(graph, start)];
    on_path[start] = true;
    loop {
        let frame = stack
            .last_mut()
            .expect("the loop breaks once the root frame pops");
        if let Some(child) = frame.children.next() {
            if on_path[child] {
                frame.cacheable = false;
            } else if let Some(depth) = memo[child] {
                frame.depth = frame.depth.max(depth);
            } else {
                on_path[child] = true;
                stack.push(Frame::new(graph, child));
            }
            continue;
        }
        let frame = stack.pop().expect("last_mut confirmed a frame");
        on_path[frame.node] = false;
        let depth = frame.depth + 1;
        if frame.cacheable {
            memo[frame.node] = Some(depth);
        }
        match stack.last_mut() {
            Some(parent) => {
                parent.depth = parent.depth.max(depth);
                parent.cacheable &= frame.cacheable;
            }
            None => return depth,
        }
    }
}

struct Frame {
    node: usize,
    children: std::vec::IntoIter<usize>,
    depth: usize,
    cacheable: bool,
}

impl Frame {
    fn new(graph: &Graph, node: usize) -> Self {
        Self {
            node,
            children: graph
                .expanded_children(node)
                .filter_map(|dependency| dependency.target)
                .collect::<Vec<_>>()
                .into_iter(),
            depth: 0,
            cacheable: true,
        }
    }
}

fn license_breakdown(graph: &Graph) -> BTreeMap<String, usize> {
    let mut result = BTreeMap::new();
    for index in graph.visible_indices() {
        *result
            .entry(graph.nodes[index].package.license())
            .or_default() += 1;
    }
    result
}

fn license_text(licenses: &BTreeMap<String, usize>) -> String {
    if licenses.is_empty() {
        return "none".to_string();
    }
    licenses
        .iter()
        .map(|(license, count)| format!("{license}: {count}"))
        .collect::<Vec<_>>()
        .join(", ")
}

fn has_copyleft(licenses: &BTreeMap<String, usize>) -> bool {
    licenses.keys().any(|license| {
        ["AGPL", "LGPL", "GPL", "MPL", "EUPL", "CDDL"]
            .iter()
            .any(|marker| license.to_ascii_uppercase().contains(marker))
    })
}

fn min_requires_python(graph: &Graph) -> String {
    let mut versions = Vec::new();
    for raw in graph
        .visible_indices()
        .filter_map(|index| graph.nodes[index].package.requires_python())
    {
        if VersionSpecifiers::from_str(raw).is_err() {
            continue;
        }
        for specifier in raw.split(',').map(str::trim) {
            if let Some(version) = specifier
                .strip_prefix(">=")
                .or_else(|| specifier.strip_prefix('>'))
                .or_else(|| specifier.strip_prefix("=="))
            {
                if let Ok(version) = Version::from_str(version.trim()) {
                    versions.push(version);
                }
            }
        }
    }
    versions
        .into_iter()
        .max()
        .map_or_else(|| "n/a".to_string(), |version| version.to_string())
}
