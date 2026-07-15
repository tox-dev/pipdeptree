use serde::ser::{SerializeMap, SerializeSeq};
use serde::{Serialize, Serializer};
use serde_json::{Map, Value, json};

use crate::graph::{Dependency, Graph};
use crate::options::{ComputedField, Options};

use super::shared::{format_size, required_version};

pub(super) fn render(graph: &Graph, options: &Options) -> String {
    let mut output = Vec::new();
    let formatter = serde_json::ser::PrettyFormatter::with_indent(b"    ");
    let mut serializer = serde_json::Serializer::with_formatter(&mut output, formatter);
    JsonGraph { graph, options }
        .serialize(&mut serializer)
        .expect("serializing dependency graph cannot fail");
    String::from_utf8(output).expect("serde_json output is UTF-8")
}

struct JsonGraph<'a> {
    graph: &'a Graph,
    options: &'a Options,
}

impl Serialize for JsonGraph<'_> {
    fn serialize<S>(&self, serializer: S) -> Result<S::Ok, S::Error>
    where
        S: Serializer,
    {
        let missing = if self.options.reverse {
            self.graph.missing_dependents()
        } else {
            std::collections::BTreeMap::new()
        };
        let mut sequence =
            serializer.serialize_seq(Some(self.graph.visible_indices().count() + missing.len()))?;
        for index in self.graph.visible_indices() {
            sequence.serialize_element(&JsonEntry {
                graph: self.graph,
                options: self.options,
                index,
            })?;
        }
        for (name, dependents) in missing {
            sequence.serialize_element(&JsonMissingEntry {
                graph: self.graph,
                options: self.options,
                name,
                dependents,
            })?;
        }
        sequence.end()
    }
}

struct JsonMissingEntry<'a> {
    graph: &'a Graph,
    options: &'a Options,
    name: &'a str,
    dependents: Vec<(usize, &'a crate::graph::Dependency)>,
}

impl Serialize for JsonMissingEntry<'_> {
    fn serialize<S>(&self, serializer: S) -> Result<S::Ok, S::Error>
    where
        S: Serializer,
    {
        let package = MissingPackage {
            graph: self.graph,
            options: self.options,
            name: self.name,
        };
        let mut object = serializer.serialize_map(Some(2))?;
        object.serialize_entry("package", &package)?;
        let dependents = self
            .dependents
            .iter()
            .map(|(parent, dependency)| JsonDependent {
                graph: self.graph,
                options: self.options,
                parent: *parent,
                dependency,
            })
            .collect::<Vec<_>>();
        object.serialize_entry("dependencies", &dependents)?;
        object.end()
    }
}

struct MissingPackage<'a> {
    graph: &'a Graph,
    options: &'a Options,
    name: &'a str,
}

impl Serialize for MissingPackage<'_> {
    fn serialize<S>(&self, serializer: S) -> Result<S::Ok, S::Error>
    where
        S: Serializer,
    {
        let mut object = serializer.serialize_map(Some(3))?;
        let version_key = if self.options.resolved() {
            "candidate_version"
        } else {
            "installed_version"
        };
        object.serialize_entry("key", self.name)?;
        object.serialize_entry("package_name", self.name)?;
        object.serialize_entry(version_key, self.graph.missing_version(self.name))?;
        object.end()
    }
}

struct JsonEntry<'a> {
    graph: &'a Graph,
    options: &'a Options,
    index: usize,
}

impl Serialize for JsonEntry<'_> {
    fn serialize<S>(&self, serializer: S) -> Result<S::Ok, S::Error>
    where
        S: Serializer,
    {
        let mut object = serializer.serialize_map(Some(2))?;
        let package = JsonPackage {
            graph: self.graph,
            options: self.options,
            index: self.index,
        };
        object.serialize_entry("package", &package)?;
        let dependencies = JsonDependencies {
            graph: self.graph,
            options: self.options,
            index: self.index,
        };
        object.serialize_entry("dependencies", &dependencies)?;
        object.end()
    }
}

struct JsonDependencies<'a> {
    graph: &'a Graph,
    options: &'a Options,
    index: usize,
}

impl Serialize for JsonDependencies<'_> {
    fn serialize<S>(&self, serializer: S) -> Result<S::Ok, S::Error>
    where
        S: Serializer,
    {
        if self.options.reverse {
            let dependents = self.graph.parents_for(self.index, None);
            let mut sequence = serializer.serialize_seq(Some(dependents.len()))?;
            for (parent, dependency) in dependents {
                sequence.serialize_element(&JsonDependent {
                    graph: self.graph,
                    options: self.options,
                    parent,
                    dependency,
                })?;
            }
            return sequence.end();
        }
        let dependencies = self.graph.expanded_children(self.index).collect::<Vec<_>>();
        let mut sequence = serializer.serialize_seq(Some(dependencies.len()))?;
        for dependency in dependencies {
            sequence.serialize_element(&JsonDependency {
                graph: self.graph,
                options: self.options,
                dependency,
            })?;
        }
        sequence.end()
    }
}

struct JsonDependent<'a> {
    graph: &'a Graph,
    options: &'a Options,
    parent: usize,
    dependency: &'a crate::graph::Dependency,
}

impl Serialize for JsonDependent<'_> {
    fn serialize<S>(&self, serializer: S) -> Result<S::Ok, S::Error>
    where
        S: Serializer,
    {
        let package = &self.graph.nodes[self.parent].package;
        let resolved = self.options.resolved();
        let mut object = serializer.serialize_map(Some(3 + usize::from(!resolved)))?;
        object.serialize_entry("key", &package.key)?;
        object.serialize_entry("package_name", &package.name)?;
        let version_key = if resolved {
            "candidate_version"
        } else {
            "installed_version"
        };
        object.serialize_entry(version_key, &package.version)?;
        if !resolved {
            let required = self.dependency.version_spec();
            object.serialize_entry("required_version", required.as_deref().unwrap_or("Any"))?;
        }
        object.end()
    }
}

struct JsonPackage<'a> {
    graph: &'a Graph,
    options: &'a Options,
    index: usize,
}

impl Serialize for JsonPackage<'_> {
    fn serialize<S>(&self, serializer: S) -> Result<S::Ok, S::Error>
    where
        S: Serializer,
    {
        let package = &self.graph.nodes[self.index].package;
        let mut object = serializer.serialize_map(Some(
            3 + usize::from(!self.options.computed.is_empty())
                + usize::from(!self.options.metadata.is_empty()),
        ))?;
        object.serialize_entry("key", &package.key)?;
        object.serialize_entry("package_name", &package.name)?;
        let version_key = if self.options.resolved() {
            "candidate_version"
        } else {
            "installed_version"
        };
        object.serialize_entry(version_key, &package.version)?;
        if !self.options.metadata.is_empty() {
            let metadata = JsonMetadata {
                package,
                fields: &self.options.metadata,
            };
            object.serialize_entry("metadata", &metadata)?;
        }
        if !self.options.computed.is_empty() {
            let computed = JsonComputed {
                graph: self.graph,
                fields: &self.options.computed,
                index: self.index,
            };
            object.serialize_entry("computed", &computed)?;
        }
        object.end()
    }
}

struct JsonMetadata<'a> {
    package: &'a crate::metadata::Package,
    fields: &'a [String],
}

impl Serialize for JsonMetadata<'_> {
    fn serialize<S>(&self, serializer: S) -> Result<S::Ok, S::Error>
    where
        S: Serializer,
    {
        let mut fields = self.fields.iter().collect::<Vec<_>>();
        fields.sort_unstable();
        fields.dedup();
        let mut object = serializer.serialize_map(Some(fields.len()))?;
        for field in fields {
            let values = self.package.metadata(field);
            if let [value] = values.as_slice() {
                object.serialize_entry(field, value)?;
            } else {
                object.serialize_entry(field, &values)?;
            }
        }
        object.end()
    }
}

struct JsonComputed<'a> {
    graph: &'a Graph,
    fields: &'a [ComputedField],
    index: usize,
}

impl Serialize for JsonComputed<'_> {
    fn serialize<S>(&self, serializer: S) -> Result<S::Ok, S::Error>
    where
        S: Serializer,
    {
        computed_json(self.graph, self.index, self.fields).serialize(serializer)
    }
}

struct JsonDependency<'a> {
    graph: &'a Graph,
    options: &'a Options,
    dependency: &'a Dependency,
}

impl Serialize for JsonDependency<'_> {
    fn serialize<S>(&self, serializer: S) -> Result<S::Ok, S::Error>
    where
        S: Serializer,
    {
        let field_count = if self.options.resolved() { 3 } else { 4 }
            + usize::from(self.dependency.activated_by.is_some());
        let mut object = serializer.serialize_map(Some(field_count))?;
        let version = self.dependency.installed_version(self.graph).unwrap_or("?");
        object.serialize_entry("key", self.dependency.key())?;
        let package_name = self.dependency.target.map_or_else(
            || self.dependency.key(),
            |target| self.graph.nodes[target].package.name.as_str(),
        );
        object.serialize_entry("package_name", package_name)?;
        if self.options.resolved() {
            object.serialize_entry("candidate_version", version)?;
        } else {
            object.serialize_entry("installed_version", version)?;
            object.serialize_entry("required_version", &required_version(self.dependency))?;
        }
        if let Some(extra) = &self.dependency.activated_by {
            object.serialize_entry("extra", extra)?;
        }
        object.end()
    }
}

pub(super) fn computed_json(
    graph: &Graph,
    index: usize,
    fields: &[ComputedField],
) -> Map<String, Value> {
    let unique = fields
        .iter()
        .any(|field| field.is_unique())
        .then(|| graph.unique_dependencies(index));
    fields
        .iter()
        .map(|field| match field {
            ComputedField::Size => (
                "size".to_string(),
                json!(format_size(graph.nodes[index].package.size())),
            ),
            ComputedField::SizeRaw => (
                "size_raw".to_string(),
                json!(graph.nodes[index].package.size()),
            ),
            ComputedField::UniqueDepsCount => (
                "unique_deps_count".to_string(),
                json!(
                    unique
                        .as_ref()
                        .expect("unique fields initialize dependencies")
                        .len()
                ),
            ),
            ComputedField::UniqueDepsNames => (
                "unique_deps_names".to_string(),
                json!(
                    unique
                        .as_ref()
                        .expect("unique fields initialize dependencies")
                        .iter()
                        .map(|dependency| graph.nodes[*dependency].package.key.as_str())
                        .collect::<Vec<_>>()
                ),
            ),
            ComputedField::UniqueDepsSize => (
                "unique_deps_size".to_string(),
                json!(format_size(
                    unique
                        .as_ref()
                        .expect("unique fields initialize dependencies")
                        .iter()
                        .map(|dependency| graph.nodes[*dependency].package.size())
                        .sum()
                )),
            ),
        })
        .collect()
}
