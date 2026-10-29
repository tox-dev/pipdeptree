use std::collections::{BTreeSet, HashSet};

use serde::Serialize;
use serde_json::{Map, Value, json};

use crate::graph::{Dependency, Graph, ReverseRoot};
use crate::options::Options;

use super::json::computed_json;
use super::shared::{required_version, reverse_required_extras};

pub(super) fn render(graph: &Graph, options: &Options) -> String {
    let entries = if options.reverse {
        graph
            .reverse_roots(false)
            .into_iter()
            .map(|root| match root {
                ReverseRoot::Installed(index) => {
                    reverse_tree_json(graph, index, None, None, &mut Walk::default(), options)
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
            .map(|root| forward_tree_json(graph, root, None, &mut Walk::default(), options))
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

// The path stops cycles; `expanded` holds the subtrees already written under the current root,
// keyed by package and the extras that select its edges, so each root's tree grows with its
// edges rather than its paths.
#[derive(Default)]
struct Walk {
    path: HashSet<usize>,
    expanded: HashSet<(usize, Option<BTreeSet<String>>)>,
}

impl Walk {
    fn repeats(&mut self, node: usize, extras: Option<&BTreeSet<String>>) -> bool {
        self.path.contains(&node) || !self.expanded.insert((node, extras.cloned()))
    }
}

// A repeated package keeps its entry, so every edge is written once, with an empty
// `dependencies` list and `"repeated": true` in place of the subtree shown earlier.
fn repeated_json(mut value: Value) -> Value {
    value["dependencies"] = Value::Array(Vec::new());
    value["repeated"] = Value::Bool(true);
    value
}

fn forward_tree_json(
    graph: &Graph,
    index: usize,
    incoming: Option<&Dependency>,
    walk: &mut Walk,
    options: &Options,
) -> Value {
    walk.path.insert(index);
    let mut value = incoming.map_or_else(
        || package_json(graph, index, options),
        |dependency| dependency_json(graph, dependency, options),
    );
    if !options.resolved() && incoming.is_none() {
        value["required_version"] = Value::String(graph.nodes[index].package.version.clone());
    }
    let children = incoming.map_or_else(
        || graph.expanded_children(index),
        |incoming| graph.children(incoming),
    );
    let mut dependencies = Vec::new();
    for dependency in children {
        let Some(target) = dependency.target else {
            dependencies.push(missing_dependency_json(dependency, options));
            continue;
        };
        dependencies.push(
            if walk.repeats(target, Some(&dependency.requested_extras()))
                && graph.children(dependency).next().is_some()
            {
                repeated_json(dependency_json(graph, dependency, options))
            } else {
                forward_tree_json(graph, target, Some(dependency), walk, options)
            },
        );
    }
    value["dependencies"] = Value::Array(dependencies);
    walk.path.remove(&index);
    value
}

fn reverse_tree_json(
    graph: &Graph,
    index: usize,
    incoming: Option<&Dependency>,
    required_extras: Option<&BTreeSet<String>>,
    walk: &mut Walk,
    options: &Options,
) -> Value {
    walk.path.insert(index);
    let mut value = package_json(graph, index, options);
    if let Some(dependency) = incoming {
        add_requirement_json(
            value.as_object_mut().expect("package JSON is an object"),
            dependency,
            options,
        );
    } else if !options.resolved() {
        value["required_version"] = Value::String(graph.nodes[index].package.version.clone());
    }
    let dependencies = graph
        .parents_for(index, required_extras)
        .into_iter()
        .map(|(parent, dependency)| reverse_parent_json(graph, parent, dependency, walk, options))
        .collect();
    value["dependencies"] = Value::Array(dependencies);
    walk.path.remove(&index);
    value
}

fn reverse_parent_json(
    graph: &Graph,
    parent: usize,
    dependency: &Dependency,
    walk: &mut Walk,
    options: &Options,
) -> Value {
    let required_extras = reverse_required_extras(graph, parent, dependency);
    if walk.repeats(parent, required_extras.as_ref())
        && !graph
            .parents_for(parent, required_extras.as_ref())
            .is_empty()
    {
        let mut value = package_json(graph, parent, options);
        add_requirement_json(
            value.as_object_mut().expect("package JSON is an object"),
            dependency,
            options,
        );
        return repeated_json(value);
    }
    reverse_tree_json(
        graph,
        parent,
        Some(dependency),
        required_extras.as_ref(),
        walk,
        options,
    )
}

fn missing_dependency_json(dependency: &Dependency, options: &Options) -> Value {
    let name = dependency.key();
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
            Value::String("?".to_string()),
        ),
    ]);
    add_requirement_json(&mut object, dependency, options);
    object.insert("dependencies".to_string(), Value::Array(Vec::new()));
    Value::Object(object)
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
            Value::String("?".to_string()),
        ),
    ]);
    if !options.resolved() {
        object.insert(
            "required_version".to_string(),
            Value::String("?".to_string()),
        );
    }
    // Optional dependencies without an installed target never render, so missing reverse
    // roots always arrive through mandatory edges and carry no activating extra.
    let mut walk = Walk::default();
    let dependencies = parents
        .iter()
        .map(|(parent, dependency)| {
            reverse_parent_json(graph, *parent, dependency, &mut walk, options)
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
    }
    add_requirement_json(&mut object, dependency, options);
    if let Some(extra) = &dependency.activated_by {
        object.insert("extra".to_string(), Value::String(extra.clone()));
    }
    Value::Object(object)
}

fn add_requirement_json(
    object: &mut Map<String, Value>,
    dependency: &Dependency,
    options: &Options,
) {
    if !options.resolved() || dependency.declaration.is_some() {
        object.insert(
            "required_version".to_string(),
            Value::String(required_version(dependency)),
        );
    }
    if let Some(declaration) = &dependency.declaration {
        object.insert(
            "declaration".to_string(),
            serde_json::to_value(declaration)
                .expect("resolved declarations contain serializable values"),
        );
    }
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
