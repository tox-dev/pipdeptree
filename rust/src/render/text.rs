use std::collections::{BTreeSet, HashSet};
use std::fmt::Write as _;

use crate::graph::{Dependency, Graph, ReverseRoot};
use crate::options::{ComputedField, Options};
use crate::process::ProcessRunner;

use super::rich_text::{self, DependencyLabel, Status};
use super::shared::{format_size, required_version, reverse_required_extra};

#[derive(Clone, Copy, Eq, PartialEq)]
pub(super) enum TextStyle {
    Plain,
    Unicode,
    Rich,
    Frozen,
}

pub(super) fn render(
    processes: &dyn ProcessRunner,
    graph: &Graph,
    options: &Options,
    style: TextStyle,
    color: bool,
) -> String {
    let mut renderer = TreeRenderer {
        graph,
        options,
        processes,
        style,
        color,
        unicode: is_unicode(&options.encoding),
        path: HashSet::new(),
        lines: Vec::new(),
    };
    if options.reverse && style != TextStyle::Frozen {
        for root in graph.reverse_roots(options.all) {
            renderer.path.clear();
            match root {
                ReverseRoot::Installed(index) => {
                    renderer
                        .lines
                        .push(root_label(processes, graph, index, style, options, color));
                    renderer.path.insert(index);
                    renderer.walk_reverse(index, None, "", 0);
                }
                ReverseRoot::Missing { name, parents } => {
                    let version = graph.missing_version(name);
                    renderer.lines.push(if style == TextStyle::Rich && color {
                        rich_text::root(name, version, "")
                    } else {
                        format!("{name}=={version}")
                    });
                    renderer.walk_reverse_parents(parents, "", 0);
                }
            }
        }
        return renderer.lines.join("\n");
    }
    for root in graph.roots(options.reverse, options.all) {
        renderer
            .lines
            .push(root_label(processes, graph, root, style, options, color));
        renderer.path.clear();
        renderer.path.insert(root);
        if options.reverse {
            renderer.walk_reverse(root, None, "", 0);
        } else {
            renderer.walk_forward(root, None, "", 0);
        }
    }
    renderer.lines.join("\n")
}

struct TreeRenderer<'a> {
    graph: &'a Graph,
    options: &'a Options,
    processes: &'a dyn ProcessRunner,
    style: TextStyle,
    color: bool,
    unicode: bool,
    path: HashSet<usize>,
    lines: Vec<String>,
}

impl TreeRenderer<'_> {
    fn walk_forward(
        &mut self,
        parent: usize,
        extras: Option<&BTreeSet<String>>,
        prefix: &str,
        depth: usize,
    ) {
        if self.options.depth.is_some_and(|limit| depth >= limit) {
            return;
        }
        let children = extras.map_or_else(
            || self.graph.expanded_children(parent),
            |extras| self.graph.children(parent, extras),
        );
        let unique = (self.style == TextStyle::Rich
            && self.options.computed.iter().any(|field| field.is_unique()))
        .then(|| self.graph.unique_dependencies(parent));
        // A child already on the path closes a cycle; the chain stops without re-printing it.
        let children = children
            .filter(|dependency| {
                dependency
                    .target
                    .is_none_or(|target| !self.path.contains(&target))
            })
            .collect::<Vec<_>>();
        let count = children.len();
        for (position, dependency) in children.into_iter().enumerate() {
            let last = position + 1 == count;
            self.lines.push(format!(
                "{}{}",
                tree_prefix(prefix, self.style, last, self.color, self.unicode),
                self.dependency_label(
                    dependency,
                    dependency.target.is_some_and(|target| {
                        unique.is_some_and(|unique| unique.contains(&target))
                    }),
                )
            ));
            let Some(child) = dependency.target else {
                continue;
            };
            self.path.insert(child);
            let extras = dependency.requested_extras();
            let next_prefix = format!("{}{}", prefix, continuation(self.style, last, self.unicode));
            self.walk_forward(child, Some(&extras), &next_prefix, depth + 1);
            self.path.remove(&child);
        }
    }

    fn walk_reverse(
        &mut self,
        child: usize,
        required_extra: Option<&str>,
        prefix: &str,
        depth: usize,
    ) {
        self.walk_reverse_parents(self.graph.parents_for(child, required_extra), prefix, depth);
    }

    fn walk_reverse_parents(
        &mut self,
        parents: Vec<(usize, &Dependency)>,
        prefix: &str,
        depth: usize,
    ) {
        if self.options.depth.is_some_and(|limit| depth >= limit) {
            return;
        }
        let mut parents = parents;
        parents.retain(|(parent, _)| !self.path.contains(parent));
        let count = parents.len();
        for (position, (parent, dependency)) in parents.into_iter().enumerate() {
            let last = position + 1 == count;
            let label = reverse_label(
                self.processes,
                self.graph,
                parent,
                dependency,
                self.style,
                self.options,
                self.color,
            );
            self.lines.push(format!(
                "{}{}",
                tree_prefix(prefix, self.style, last, self.color, self.unicode),
                label
            ));
            self.path.insert(parent);
            let required_extra =
                reverse_required_extra(self.graph, parent, dependency).map(ToOwned::to_owned);
            let next_prefix = format!("{}{}", prefix, continuation(self.style, last, self.unicode));
            self.walk_reverse(parent, required_extra.as_deref(), &next_prefix, depth + 1);
            self.path.remove(&parent);
        }
    }
}

fn root_label(
    processes: &dyn ProcessRunner,
    graph: &Graph,
    index: usize,
    style: TextStyle,
    options: &Options,
    color: bool,
) -> String {
    let package = &graph.nodes[index].package;
    if style == TextStyle::Frozen {
        return package.frozen(processes);
    }
    let suffix = node_suffix(graph, index, options, ", ");
    if style == TextStyle::Rich && color {
        rich_text::root(&package.name, &package.version, &suffix)
    } else {
        format!("{}=={}{}", package.name, package.version, suffix)
    }
}

fn reverse_label(
    processes: &dyn ProcessRunner,
    graph: &Graph,
    parent: usize,
    dependency: &Dependency,
    style: TextStyle,
    options: &Options,
    color: bool,
) -> String {
    let package = &graph.nodes[parent].package;
    if style == TextStyle::Frozen {
        return package.frozen(processes);
    }
    let mut required = dependency.target.map_or_else(
        || dependency.key().to_string(),
        |target| graph.nodes[target].package.name.clone(),
    );
    if let Some(specifier) = dependency.version_spec() {
        required.push_str(&specifier);
    }
    if let Some(extra) = &dependency.activated_by {
        let _ = write!(required, ", extra: {extra}");
    }
    let suffix = node_suffix(graph, parent, options, ", ");
    if style == TextStyle::Rich && color {
        rich_text::reverse(&package.name, &package.version, &required, &suffix)
    } else {
        format!(
            "{}=={} [requires: {required}]{}",
            package.name, package.version, suffix
        )
    }
}

impl TreeRenderer<'_> {
    fn dependency_label(&self, dependency: &Dependency, unique: bool) -> String {
        if self.style == TextStyle::Frozen {
            return dependency.target.map_or_else(
                || dependency.key().to_string(),
                |target| self.graph.nodes[target].package.frozen(self.processes),
            );
        }
        let installed = dependency.installed_version(self.graph).unwrap_or("?");
        let name = dependency.target.map_or_else(
            || dependency.key(),
            |target| self.graph.nodes[target].package.name.as_str(),
        );
        let extra = dependency
            .activated_by
            .as_ref()
            .map_or_else(String::new, |extra| format!(", extra: {extra}"));
        let detail = if self.options.resolved() {
            if self.style == TextStyle::Rich {
                format!("candidate: {installed}")
            } else {
                format!("candidate: {installed}{extra}")
            }
        } else {
            let required = required_version(dependency);
            if self.style == TextStyle::Rich {
                format!("required: {required} installed: {installed}")
            } else {
                format!("required: {required}, installed: {installed}{extra}")
            }
        };
        let suffix = dependency.target.map_or_else(String::new, |target| {
            node_suffix(self.graph, target, self.options, ", ")
        });
        if self.style == TextStyle::Rich {
            let status = match (
                dependency.installed_version(self.graph).is_none(),
                dependency.is_conflicting(self.graph),
                unique,
            ) {
                (true, _, _) => Status::Error,
                (false, true, _) => Status::Warning,
                (false, false, _) => Status::Success,
            };
            if self.color {
                return rich_text::dependency(&DependencyLabel {
                    status,
                    unique,
                    unicode: self.unicode,
                    name,
                    candidate: self.options.resolved().then_some(installed),
                    required: dependency.version_spec().as_deref().unwrap_or("Any"),
                    installed,
                    extra: dependency.activated_by.as_deref(),
                    suffix: &suffix,
                });
            }
            let marker = status_marker(status, self.unicode);
            let star = if unique {
                format!(" {}", star_marker(self.unicode))
            } else {
                String::new()
            };
            let extra = dependency
                .activated_by
                .as_ref()
                .map_or_else(String::new, |extra| format!(" [extra: {extra}]"));
            format!("{marker}{star} {name} {detail}{extra}{suffix}")
        } else {
            format!("{name} [{detail}]{suffix}")
        }
    }
}

fn tree_prefix(prefix: &str, style: TextStyle, last: bool, color: bool, unicode: bool) -> String {
    let value = format!("{prefix}{}", branch(style, last, unicode));
    if style == TextStyle::Rich && color {
        rich_text::tree_prefix(&value)
    } else {
        value
    }
}

pub(super) const fn status_marker(status: Status, unicode: bool) -> &'static str {
    match (status, unicode) {
        (Status::Success, true) => "✓",
        (Status::Success, false) => "v",
        (Status::Warning, true) => "⚠",
        (Status::Warning, false) => "!",
        (Status::Error, true) => "✗",
        (Status::Error, false) => "x",
    }
}

pub(super) const fn star_marker(unicode: bool) -> &'static str {
    if unicode { "⭐" } else { "*" }
}

const fn branch(style: TextStyle, last: bool, unicode: bool) -> &'static str {
    match (style, last, unicode) {
        (TextStyle::Frozen, ..) => "  ",
        (TextStyle::Plain, ..) => "  - ",
        (TextStyle::Unicode, true, _) => "└── ",
        (TextStyle::Unicode, false, _) => "├── ",
        (TextStyle::Rich, true, true) => "┗━━ ",
        (TextStyle::Rich, false, true) => "┣━━ ",
        (TextStyle::Rich, true, false) => "`-- ",
        (TextStyle::Rich, false, false) => "+-- ",
    }
}

const fn continuation(style: TextStyle, last: bool, unicode: bool) -> &'static str {
    match (style, last, unicode) {
        (TextStyle::Frozen | TextStyle::Plain, ..) => "  ",
        (TextStyle::Unicode | TextStyle::Rich, true, _) => "    ",
        (TextStyle::Unicode, false, _) => "│   ",
        (TextStyle::Rich, false, true) => "┃   ",
        (TextStyle::Rich, false, false) => "|   ",
    }
}

pub(super) fn node_suffix(
    graph: &Graph,
    index: usize,
    options: &Options,
    separator: &str,
) -> String {
    let parts = node_suffix_parts(graph, index, options);
    if parts.is_empty() {
        String::new()
    } else {
        format!(" ({})", parts.join(separator))
    }
}

pub(super) fn node_suffix_parts(graph: &Graph, index: usize, options: &Options) -> Vec<String> {
    let mut parts = options
        .metadata
        .iter()
        .flat_map(|field| graph.nodes[index].package.metadata(field))
        .map(|value| value.split_whitespace().collect::<Vec<_>>().join(" "))
        .collect::<Vec<_>>();
    let unique = options
        .computed
        .iter()
        .any(|field| field.is_unique())
        .then(|| graph.unique_dependencies(index));
    for field in &options.computed {
        match field {
            ComputedField::Size => parts.push(format_size(graph.nodes[index].package.size())),
            ComputedField::SizeRaw => parts.push(graph.nodes[index].package.size().to_string()),
            ComputedField::UniqueDepsCount => {
                if let Some(unique) = unique.filter(|unique| !unique.is_empty()) {
                    parts.push(format!("{} unique deps", unique.len()));
                }
            }
            ComputedField::UniqueDepsNames => {
                if let Some(unique) = unique.filter(|unique| !unique.is_empty()) {
                    parts.push(format!(
                        "unique: {}",
                        unique
                            .iter()
                            .map(|dependency| graph.nodes[*dependency].package.key.as_str())
                            .collect::<Vec<_>>()
                            .join(" | ")
                    ));
                }
            }
            ComputedField::UniqueDepsSize => {
                if let Some(unique) = unique.filter(|unique| !unique.is_empty()) {
                    parts.push(format!(
                        "unique size: {}",
                        format_size(
                            unique
                                .iter()
                                .map(|dependency| graph.nodes[*dependency].package.size())
                                .sum()
                        )
                    ));
                }
            }
        }
    }
    parts
}

pub(super) fn is_unicode(encoding: &str) -> bool {
    matches!(
        encoding.to_ascii_lowercase().as_str(),
        "utf-8" | "utf-16" | "utf-32"
    )
}
