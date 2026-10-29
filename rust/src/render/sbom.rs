use std::collections::{BTreeMap, BTreeSet};

use cyclonedx_bom::models::bom::BomReference;
use cyclonedx_bom::models::component::Classification;
use cyclonedx_bom::models::composition::{AggregateType, Composition, Compositions};
use cyclonedx_bom::models::dependency::{Dependencies, Dependency as BomDependency};
use cyclonedx_bom::models::external_reference::{
    ExternalReference, ExternalReferenceType, ExternalReferences,
};
use cyclonedx_bom::models::license::{LicenseChoice, Licenses};
use cyclonedx_bom::models::property::{Properties, Property};
use cyclonedx_bom::models::tool::Tools;
use cyclonedx_bom::prelude::{
    Bom, Component, Components, DateTime, Metadata, NormalizedString, Purl, SpecVersion, Uri,
    Validate,
};
use serde_json::{Value, json};

use crate::Error;
use crate::graph::{Dependency, Graph};
use crate::metadata::Package;
use crate::options::{Command, Options};

pub(super) fn render(graph: &Graph, options: &Options) -> Result<Vec<u8>, Error> {
    let mut components = BTreeMap::new();
    let mut dependencies = Vec::new();
    let mut unknown = BTreeSet::new();
    for index in graph.visible_indices() {
        let package = &graph.nodes[index].package;
        let mut component = package_component(package)?;
        let reference = component.bom_ref.clone().expect("package has a reference");
        let mut properties = component.properties.take().map_or_else(Vec::new, |p| p.0);
        let mut children = BTreeSet::new();
        for dependency in graph.expanded_children(index) {
            let child = if let Some(target) = dependency.target {
                package_purl(&graph.nodes[target].package)?.to_string()
            } else {
                let missing = missing_component(dependency);
                let reference = missing
                    .bom_ref
                    .clone()
                    .expect("missing package has a reference");
                components.entry(reference.clone()).or_insert(missing);
                unknown.insert(reference.clone());
                reference
            };
            children.insert(child);
        }
        for field in &options.metadata {
            for value in metadata_values(package, field) {
                properties.push(Property::new(
                    format!("pipdeptree:metadata:{field}"),
                    &value,
                ));
            }
        }
        for (field, value) in super::json::computed_json(graph, index, &options.computed) {
            // A property value is plain text, so a list becomes one property per item, as repeated
            // metadata does.
            let values = match value {
                Value::Array(items) => items,
                value => vec![value],
            };
            for value in values {
                let text = match value {
                    Value::String(text) => text,
                    value => value.to_string(),
                };
                properties.push(Property::new(format!("pipdeptree:computed:{field}"), &text));
            }
        }
        if !properties.is_empty() {
            component.properties = Some(Properties(properties));
        }
        components.insert(reference.clone(), component);
        dependencies.push(BomDependency {
            dependency_ref: reference,
            dependencies: children.into_iter().collect(),
        });
    }
    let bom = Bom {
        metadata: Some(metadata(options)),
        components: Some(Components(components.into_values().collect())),
        dependencies: Some(Dependencies(dependencies)),
        compositions: (!unknown.is_empty()).then(|| {
            Compositions(vec![Composition {
                bom_ref: None,
                aggregate: AggregateType::Unknown,
                assemblies: None,
                dependencies: Some(unknown.into_iter().map(BomReference::new).collect()),
                vulnerabilities: None,
                signature: None,
            }])
        }),
        spec_version: SpecVersion::V1_5,
        ..Bom::default()
    };
    let mut output = Vec::new();
    bom.output_as_json_v1_5(&mut output)
        .expect("CycloneDX 1.5 model can be serialized to memory");
    // The library omits empty dependsOn arrays. An explicit empty array distinguishes known
    // leaves from missing distributions, whose dependency graph is unknown and has no entry.
    let mut value: serde_json::Value = serde_json::from_slice(&output)?;
    let entries = value["dependencies"]
        .as_array_mut()
        .expect("BOM includes a dependency array");
    for entry in entries {
        entry
            .as_object_mut()
            .expect("CycloneDX dependency is an object")
            .entry("dependsOn")
            .or_insert_with(|| json!([]));
    }
    let mut output = serde_json::to_vec_pretty(&value)?;
    output.push(b'\n');
    Ok(output)
}

fn metadata(options: &Options) -> Metadata {
    let source = match &options.command {
        None => "environment",
        Some(Command::FromLock { .. }) => "lock",
        Some(Command::FromIndex { .. }) => "index",
    };
    let mut tool = Component::new(
        Classification::Application,
        "pipdeptree",
        env!("PIPDEPTREE_VERSION"),
        None,
    );
    tool.publisher = Some(NormalizedString::new("tox-dev"));
    Metadata {
        timestamp: Some(DateTime::now().expect("the current time formats as ISO 8601")),
        // The tool list form is deprecated since CycloneDX 1.5.
        tools: Some(Tools::Object {
            services: None,
            components: Some(Components(vec![tool])),
        }),
        properties: Some(Properties(vec![Property::new("pipdeptree:source", source)])),
        ..Metadata::default()
    }
}

fn package_purl(package: &Package) -> Result<Purl, Error> {
    Purl::new("pypi", &package.key, &package.version).map_err(|error| {
        Error::message(format!(
            "could not identify {} in SBOM: {error}",
            package.name
        ))
    })
}

fn metadata_values(package: &Package, field: &str) -> Vec<String> {
    package
        .metadata(field)
        .into_iter()
        .filter(|value| !value.is_empty() && value != "N/A")
        .collect()
}

fn package_component(package: &Package) -> Result<Component, Error> {
    let purl = package_purl(package)?;
    let mut component = Component::new(
        Classification::Library,
        &package.name,
        &package.version,
        Some(purl.to_string()),
    );
    if package.version.is_empty() {
        component.version = None;
    }
    component.purl = Some(purl);
    component.external_references = external_references(package);
    component.licenses = licenses(package);
    let mut properties = Vec::new();
    for value in metadata_values(package, "provides-extra") {
        properties.push(Property::new("pipdeptree:provides-extra", &value));
    }
    component.properties = Some(Properties(properties));
    Ok(component)
}

fn licenses(package: &Package) -> Option<Licenses> {
    if let Some(expression) = metadata_values(package, "license-expression").first() {
        let license = LicenseChoice::expression(expression);
        return Some(Licenses(vec![
            if license.validate_version(SpecVersion::V1_5).passed() {
                license
            } else {
                LicenseChoice::license(expression)
            },
        ]));
    }
    // Each license classifier names a license of its own; joined they would name none.
    let mut licenses = metadata_values(package, "classifier")
        .iter()
        .filter_map(|classifier| classifier.strip_prefix("License :: "))
        .filter_map(|classifier| classifier.rsplit(" :: ").next())
        .map(LicenseChoice::license)
        .collect::<Vec<_>>();
    if licenses.is_empty() {
        let license = package.license();
        if license != "(N/A)" {
            licenses.push(LicenseChoice::license(
                license
                    .strip_prefix('(')
                    .and_then(|value| value.strip_suffix(')'))
                    .unwrap_or(&license),
            ));
        }
    }
    (!licenses.is_empty()).then_some(Licenses(licenses))
}

fn missing_component(dependency: &Dependency) -> Component {
    // Unlike installed metadata, dependency names have already passed PEP 508 parsing.
    let purl = Purl::new("pypi", dependency.key(), "")
        .expect("parsed dependency has a nonempty package name");
    let mut component = Component::new(
        Classification::Library,
        dependency.key(),
        "",
        Some(purl.to_string()),
    );
    component.version = None;
    component.purl = Some(purl);
    component.properties = Some(Properties(vec![Property::new(
        "pipdeptree:missing",
        "true",
    )]));
    component
}

fn external_references(package: &Package) -> Option<ExternalReferences> {
    let mut references = Vec::new();
    for value in metadata_values(package, "project-url") {
        let Some((label, url)) = value.split_once(',') else {
            continue;
        };
        let label = label.trim();
        add_reference(
            &mut references,
            reference_type(label),
            url.trim(),
            format!("from packaging metadata Project-URL: {label}"),
        );
    }
    for (field, kind) in [
        ("home-page", ExternalReferenceType::Website),
        ("download-url", ExternalReferenceType::Distribution),
    ] {
        for url in metadata_values(package, field) {
            add_reference(
                &mut references,
                kind.clone(),
                url.trim(),
                format!("from packaging metadata: {field}"),
            );
        }
    }
    (!references.is_empty()).then_some(ExternalReferences(references))
}

fn add_reference(
    references: &mut Vec<ExternalReference>,
    kind: ExternalReferenceType,
    url: &str,
    comment: String,
) {
    // Core metadata may contain placeholders or malformed URLs. Do not emit invalid references.
    let Ok(url) = url::Url::parse(url) else {
        return;
    };
    let mut reference = ExternalReference::new(kind, Uri::new(url.as_str()));
    reference.comment = Some(comment);
    if !references.contains(&reference) {
        references.push(reference);
    }
}

fn reference_type(label: &str) -> ExternalReferenceType {
    // PEP 753 normalization and aliases, plus the labels cyclonedx-py maps, so both generators
    // agree on the reference type.
    let label = label
        .chars()
        .filter(|character| !character.is_ascii_punctuation() && !character.is_ascii_whitespace())
        .map(|character| character.to_ascii_lowercase())
        .collect::<String>();
    match label.as_str() {
        "homepage" | "home" | "website" => ExternalReferenceType::Website,
        "source" | "sourcecode" | "repository" | "github" | "code" => ExternalReferenceType::Vcs,
        "issues" | "issue" | "issuetracker" | "bugtracker" | "bugs" | "bugreports" | "tracker" => {
            ExternalReferenceType::IssueTracker
        }
        "documentation" | "docs" => ExternalReferenceType::Documentation,
        "changelog" | "changes" | "whatsnew" | "history" | "releasenotes" => {
            ExternalReferenceType::ReleaseNotes
        }
        "download" | "downloads" => ExternalReferenceType::Distribution,
        "license" => ExternalReferenceType::License,
        "chat" => ExternalReferenceType::Chat,
        "mailinglist" => ExternalReferenceType::MailingList,
        "support" => ExternalReferenceType::Support,
        "security" | "securitypolicy" => ExternalReferenceType::SecurityContact,
        _ => ExternalReferenceType::Other,
    }
}
