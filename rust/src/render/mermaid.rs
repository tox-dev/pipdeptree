use std::collections::HashMap;
use std::fmt::Write as _;

use crate::graph::{Dependency, Graph};
use crate::options::Options;

use super::shared::edge_label;
use super::text::node_suffix_parts;

const RESERVED_IDS: [&str; 20] = [
    "C4Component",
    "C4Container",
    "C4Deployment",
    "C4Dynamic",
    "_blank",
    "_parent",
    "_self",
    "_top",
    "call",
    "class",
    "classDef",
    "click",
    "end",
    "flowchart",
    "flowchart-v2",
    "graph",
    "interpolate",
    "linkStyle",
    "style",
    "subgraph",
];

pub(super) fn render(graph: &Graph, options: &Options) -> String {
    let mut ids = HashMap::new();
    let mut nodes = Vec::new();
    let mut edges = Vec::new();
    for index in graph.visible_indices() {
        let package = &graph.nodes[index].package;
        let id = mermaid_id(&package.key, &mut ids);
        let label = [package.name.clone(), package.version.clone()]
            .into_iter()
            .chain(node_suffix_parts(graph, index, options))
            .map(|part| node_text(&part))
            .collect::<Vec<_>>();
        nodes.push(format!("{id}[\"{}\"]", label.join("<br/>")));
        if options.reverse {
            for (parent, dependency) in graph.parents(index) {
                let parent_id = mermaid_id(&graph.nodes[parent].package.key, &mut ids);
                edges.push(format!(
                    "{id} -- \"{}\" --> {parent_id}",
                    edge_text(dependency)
                ));
            }
        } else {
            for dependency in graph.expanded_children(index) {
                let dependency_id = mermaid_id(dependency.key(), &mut ids);
                if dependency.target.is_none() {
                    nodes.push(format!(
                        "{dependency_id}[\"{}<br/>(missing)\"]:::missing",
                        node_text(dependency.key())
                    ));
                    edges.push(format!("{id} -.-> {dependency_id}"));
                } else {
                    edges.push(format!(
                        "{id} -- \"{}\" --> {dependency_id}",
                        edge_text(dependency)
                    ));
                }
            }
        }
    }
    if options.reverse {
        for (name, dependents) in graph.missing_dependents() {
            let id = mermaid_id(name, &mut ids);
            nodes.push(format!(
                "{id}[\"{}<br/>(missing)\"]:::missing",
                node_text(name)
            ));
            for (parent, _) in dependents {
                let parent_id = mermaid_id(&graph.nodes[parent].package.key, &mut ids);
                edges.push(format!("{id} -.-> {parent_id}"));
            }
        }
    }
    nodes.sort_unstable();
    nodes.dedup();
    edges.sort_unstable();
    edges.dedup();
    let mut output = String::from("flowchart TD\n    classDef missing stroke-dasharray: 5\n");
    for line in nodes.into_iter().chain(edges) {
        output.push_str("    ");
        output.push_str(&line);
        output.push('\n');
    }
    output
}

fn mermaid_id(key: &str, ids: &mut HashMap<String, String>) -> String {
    if let Some(value) = ids.get(key) {
        return value.clone();
    }
    // Canonical names hold only these characters, none of them `_`, so a placeholder cannot
    // collide with a canonical name, while any other character could end the id or the statement.
    let mut value = if !key.is_empty()
        && key
            .bytes()
            .all(|byte| byte.is_ascii_lowercase() || byte.is_ascii_digit() || byte == b'-')
    {
        key.to_string()
    } else {
        format!("package_{}", ids.len())
    };
    if RESERVED_IDS.contains(&key) {
        let mut suffix = 0;
        while ids.values().any(|existing| existing == &value)
            || RESERVED_IDS.contains(&value.as_str())
        {
            value = format!("{key}_{suffix}");
            suffix += 1;
        }
    }
    ids.insert(key.to_string(), value.clone());
    value
}

// Labels are HTML joined with `<br/>`: `"` ends the label, `#` starts an entity code, a leading
// backtick opens a Markdown string and a line break ends the statement. Mermaid's `#<decimal>;`
// entity codes keep each of them literal text.
fn node_text(value: &str) -> String {
    entity_escape(value, |character| {
        matches!(character, '"' | '#' | '&' | '<' | '>' | '`')
    })
}

fn entity_escape(value: &str, special: impl Fn(char) -> bool) -> String {
    let mut escaped = String::with_capacity(value.len());
    for character in value.chars() {
        if special(character) || character.is_control() {
            let _ = write!(escaped, "#{};", u32::from(character));
        } else {
            escaped.push(character);
        }
    }
    escaped
}

// Version specifiers use `<` and `>`, so edge labels keep them as written.
fn edge_text(dependency: &Dependency) -> String {
    entity_escape(&edge_label(dependency), |character| {
        matches!(character, '"' | '#' | '&' | '`')
    })
}
