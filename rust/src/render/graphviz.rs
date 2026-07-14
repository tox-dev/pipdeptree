use std::collections::{HashMap, VecDeque};

use crate::Error;
use crate::graph::Graph;
use crate::options::Options;
use crate::process::{ProcessRequest, ProcessRunner};

use super::shared::edge_label;
use super::text::node_suffix_parts;

pub(super) fn render(graph: &Graph, options: &Options) -> String {
    let reachable = reachable_with_depth(graph, options);
    let mut body = Vec::new();
    for index in graph.visible_indices() {
        if reachable
            .as_ref()
            .is_some_and(|depths| !depths.contains_key(&index))
        {
            continue;
        }
        let package = &graph.nodes[index].package;
        let package_id = dot_id(&package.key);
        let mut label = vec![package.name.clone(), package.version.clone()];
        label.extend(node_suffix_parts(graph, index, options));
        body.push(format!(
            "\t{} [label=\"{}\"]\n",
            package_id,
            label
                .iter()
                .map(|part| dot_label_component(part))
                .collect::<Vec<_>>()
                .join("\\n")
        ));
        if options.depth.is_some_and(|limit| {
            reachable
                .as_ref()
                .and_then(|depths| depths.get(&index))
                .is_some_and(|depth| *depth >= limit)
        }) {
            continue;
        }
        if options.reverse {
            for (parent, dependency) in graph.parents(index) {
                if reachable
                    .as_ref()
                    .is_none_or(|depths| depths.contains_key(&parent))
                {
                    body.push(format!(
                        "\t{} -> {} [label=\"{}\"]\n",
                        package_id,
                        dot_id(&graph.nodes[parent].package.key),
                        dot_label_component(&edge_label(dependency))
                    ));
                }
            }
        } else {
            for dependency in graph.expanded_children(index) {
                if let Some(target) = dependency.target {
                    if reachable
                        .as_ref()
                        .is_none_or(|depths| depths.contains_key(&target))
                    {
                        body.push(format!(
                            "\t{} -> {} [label=\"{}\"]\n",
                            package_id,
                            dot_id(dependency.key()),
                            dot_label_component(&edge_label(dependency))
                        ));
                    }
                } else {
                    body.push(format!(
                        "\t{} [label=\"{}\\n(missing)\" style=dashed]\n",
                        dot_id(dependency.key()),
                        dot_label_component(dependency.key())
                    ));
                    body.push(format!(
                        "\t{} -> {} [style=dashed]\n",
                        package_id,
                        dot_id(dependency.key())
                    ));
                }
            }
        }
    }
    if options.reverse {
        for (name, dependents) in graph.missing_dependents() {
            body.push(format!(
                "\t{} [label=\"{}\\n(missing)\" style=dashed]\n",
                dot_id(name),
                dot_label_component(name)
            ));
            for (parent, _) in dependents {
                body.push(format!(
                    "\t{} -> {} [style=dashed]\n",
                    dot_id(name),
                    dot_id(&graph.nodes[parent].package.key)
                ));
            }
        }
    }
    body.sort_unstable();
    body.dedup();
    let mut output = String::from("digraph {\n");
    for line in body {
        output.push_str(&line);
    }
    output.push_str("}\n");
    output
}

pub(super) fn dot_id(value: &str) -> String {
    let unquoted = value
        .chars()
        .next()
        .is_some_and(|first| first.is_ascii_alphabetic() || first == '_')
        && value
            .chars()
            .all(|character| character.is_ascii_alphanumeric() || character == '_')
        && !matches!(
            value.to_ascii_lowercase().as_str(),
            "digraph" | "edge" | "graph" | "node" | "strict" | "subgraph"
        );
    if unquoted {
        value.to_string()
    } else {
        format!("\"{}\"", value.replace('\\', "\\\\").replace('"', "\\\""))
    }
}

fn dot_label_component(value: &str) -> String {
    value.replace('"', "\\\"")
}

pub(super) fn pipe(
    processes: &dyn ProcessRunner,
    dot: &str,
    format: &str,
) -> Result<Vec<u8>, Error> {
    let output = processes
        .run(&ProcessRequest::new("dot", [format!("-T{format}")]).with_stdin(dot.as_bytes()))
        .map_err(|error| Error::message(format!("graphviz is not available: {error}")))?;
    if !output.success {
        return Err(Error::message(
            String::from_utf8_lossy(&output.stderr).trim().to_string(),
        ));
    }
    Ok(output.stdout)
}

fn reachable_with_depth(graph: &Graph, options: &Options) -> Option<HashMap<usize, usize>> {
    let limit = options.depth?;
    let mut result = HashMap::new();
    let mut queue = graph
        .roots(options.reverse, false)
        .into_iter()
        .map(|root| (root, 0))
        .collect::<VecDeque<_>>();
    while let Some((index, depth)) = queue.pop_front() {
        if result.contains_key(&index) {
            continue;
        }
        result.insert(index, depth);
        if depth >= limit {
            continue;
        }
        if options.reverse {
            queue.extend(
                graph
                    .parents(index)
                    .into_iter()
                    .map(|(parent, _)| (parent, depth + 1)),
            );
        } else {
            queue.extend(
                graph
                    .expanded_children(index)
                    .filter_map(|dependency| dependency.target)
                    .map(|child| (child, depth + 1)),
            );
        }
    }
    Some(result)
}
