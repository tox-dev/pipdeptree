use std::collections::HashMap;

use crate::graph::Graph;
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
        let mut label = vec![package.name.clone(), package.version.clone()];
        label.extend(node_suffix_parts(graph, index, options));
        nodes.push(format!("{id}[\"{}\"]", label.join("<br/>")));
        if options.reverse {
            for (parent, dependency) in graph.parents(index) {
                let parent_id = mermaid_id(&graph.nodes[parent].package.key, &mut ids);
                edges.push(format!(
                    "{id} -- \"{}\" --> {parent_id}",
                    edge_label(dependency)
                ));
            }
        } else {
            for dependency in graph.expanded_children(index) {
                let dependency_id = mermaid_id(dependency.key(), &mut ids);
                if dependency.target.is_none() {
                    nodes.push(format!(
                        "{dependency_id}[\"{}<br/>(missing)\"]:::missing",
                        dependency.key()
                    ));
                    edges.push(format!("{id} -.-> {dependency_id}"));
                } else {
                    edges.push(format!(
                        "{id} -- \"{}\" --> {dependency_id}",
                        edge_label(dependency)
                    ));
                }
            }
        }
    }
    if options.reverse {
        for (name, dependents) in graph.missing_dependents() {
            let id = mermaid_id(name, &mut ids);
            nodes.push(format!("{id}[\"{name}<br/>(missing)\"]:::missing"));
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
    let mut value = key.to_string();
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
