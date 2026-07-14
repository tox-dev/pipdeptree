use std::collections::{BTreeSet, HashSet};

use serde::Serialize;
use serde_json::{Map, Value, json};

use crate::graph::{Dependency, Graph, ReverseRoot};
use crate::options::Options;

use super::json::computed_json;

pub(super) fn render(graph: &Graph, options: &Options) -> String {
    let entries = if options.reverse {
        graph
            .reverse_roots(false)
            .into_iter()
            .map(|root| match root {
                ReverseRoot::Installed(index) => {
                    reverse_tree_json(graph, index, None, None, &mut HashSet::new(), options)
                }
                ReverseRoot::Missing { name, parents } => {
                    missing_reverse_json(graph, name, &parents, options)
                }
            })
            .collect::<Vec<_>>()
    } else {
        graph
            .roots(false, false)
            .into_iter()
            .map(|root| {
                forward_tree_json(
                    graph,
                    root,
                    None,
                    &BTreeSet::new(),
                    &mut HashSet::new(),
                    options,
                )
            })
            .collect::<Vec<_>>()
    };
    let mut output = Vec::new();
    let formatter = serde_json::ser::PrettyFormatter::with_indent(b"    ");
    let mut serializer = serde_json::Serializer::with_formatter(&mut output, formatter);
    entries
        .serialize(&mut serializer)
        .expect("serializing dependency tree cannot fail");
    String::from_utf8(output).expect("JSON is UTF-8")
}

fn forward_tree_json(
    graph: &Graph,
    index: usize,
    incoming: Option<&Dependency>,
    extras: &BTreeSet<String>,
    path: &mut HashSet<usize>,
    options: &Options,
) -> Value {
    path.insert(index);
    let mut value = incoming.map_or_else(
        || package_json(graph, index, options),
        |dependency| dependency_json(graph, dependency, options),
    );
    if !options.resolved() && incoming.is_none() {
        value["required_version"] = Value::String(graph.nodes[index].package.version.clone());
    }
    let children = if incoming.is_none() {
        graph.expanded_children(index)
    } else {
        graph.children(index, extras)
    };
    let dependencies = children
        .into_iter()
        .filter_map(|dependency| dependency.target.map(|target| (dependency, target)))
        .filter(|(_, target)| !path.contains(target))
        .map(|(dependency, target)| {
            let mut next = path.clone();
            forward_tree_json(
                graph,
                target,
                Some(dependency),
                &dependency.requested_extras(),
                &mut next,
                options,
            )
        })
        .collect::<Vec<_>>();
    value["dependencies"] = Value::Array(dependencies);
    value
}

fn reverse_tree_json(
    graph: &Graph,
    index: usize,
    incoming: Option<&Dependency>,
    required_extra: Option<&str>,
    path: &mut HashSet<usize>,
    options: &Options,
) -> Value {
    path.insert(index);
    let mut value = package_json(graph, index, options);
    if let Some(dependency) = incoming {
        if !options.resolved() {
            value["required_version"] = Value::String(
                dependency
                    .version_spec()
                    .unwrap_or_else(|| "Any".to_string()),
            );
        }
    } else if !options.resolved() {
        value["required_version"] = Value::String(graph.nodes[index].package.version.clone());
    }
    let dependencies = graph
        .parents_for(index, required_extra)
        .into_iter()
        .filter(|(parent, _)| !path.contains(parent))
        .map(|(parent, dependency)| {
            let mut next = path.clone();
            let required_extra = dependency
                .activated_by
                .as_deref()
                .filter(|extra| !graph.extra_is_global(parent, extra));
            reverse_tree_json(
                graph,
                parent,
                Some(dependency),
                required_extra,
                &mut next,
                options,
            )
        })
        .collect::<Vec<_>>();
    value["dependencies"] = Value::Array(dependencies);
    value
}

fn missing_reverse_json(
    graph: &Graph,
    name: &str,
    parents: &[(usize, &Dependency)],
    options: &Options,
) -> Value {
    let mut object = Map::from_iter([
        ("key".to_string(), Value::String(name.to_string())),
        ("package_name".to_string(), Value::String(name.to_string())),
        (
            if options.resolved() {
                "candidate_version"
            } else {
                "installed_version"
            }
            .to_string(),
            Value::String(graph.missing_version(name).to_string()),
        ),
    ]);
    if !options.resolved() {
        object.insert(
            "required_version".to_string(),
            Value::String(graph.missing_version(name).to_string()),
        );
    }
    // Optional dependencies without an installed target never render, so missing reverse
    // roots always arrive through mandatory edges and carry no activating extra.
    let dependencies = parents
        .iter()
        .map(|(parent, dependency)| {
            reverse_tree_json(
                graph,
                *parent,
                Some(dependency),
                None,
                &mut HashSet::new(),
                options,
            )
        })
        .collect::<Vec<_>>();
    object.insert("dependencies".to_string(), Value::Array(dependencies));
    Value::Object(object)
}

fn package_json(graph: &Graph, index: usize, options: &Options) -> Value {
    let package = &graph.nodes[index].package;
    let mut object = Map::from_iter([
        ("key".to_string(), Value::String(package.key.clone())),
        (
            "package_name".to_string(),
            Value::String(package.name.clone()),
        ),
        (
            if options.resolved() {
                "candidate_version"
            } else {
                "installed_version"
            }
            .to_string(),
            Value::String(package.version.clone()),
        ),
    ]);
    add_context_json(graph, index, options, &mut object);
    Value::Object(object)
}

fn dependency_json(graph: &Graph, dependency: &Dependency, options: &Options) -> Value {
    let target = dependency
        .target
        .expect("tree dependencies always point to installed packages");
    let mut object = Map::new();
    object.insert(
        "key".to_string(),
        Value::String(dependency.key().to_string()),
    );
    object.insert(
        "package_name".to_string(),
        Value::String(graph.nodes[target].package.name.clone()),
    );
    let version = graph.nodes[target].package.version.clone();
    if options.resolved() {
        object.insert("candidate_version".to_string(), Value::String(version));
    } else {
        object.insert("installed_version".to_string(), Value::String(version));
        object.insert(
            "required_version".to_string(),
            Value::String(
                dependency
                    .version_spec()
                    .unwrap_or_else(|| "Any".to_string()),
            ),
        );
    }
    if let Some(extra) = &dependency.activated_by {
        object.insert("extra".to_string(), Value::String(extra.clone()));
    }
    Value::Object(object)
}

fn add_context_json(
    graph: &Graph,
    index: usize,
    options: &Options,
    object: &mut Map<String, Value>,
) {
    if !options.metadata.is_empty() {
        let metadata = options
            .metadata
            .iter()
            .map(|field| {
                let values = graph.nodes[index].package.metadata(field);
                let value = if values.len() == 1 {
                    Value::String(values[0].clone())
                } else {
                    json!(values)
                };
                (field.clone(), value)
            })
            .collect();
        object.insert("metadata".to_string(), Value::Object(metadata));
    }
    if !options.computed.is_empty() {
        object.insert(
            "computed".to_string(),
            Value::Object(computed_json(graph, index, &options.computed)),
        );
    }
}
