use std::collections::{BTreeMap, BTreeSet};

use cyclonedx_bom::models::component::{Classification, Scope};
use cyclonedx_bom::models::dependency::{Dependencies, Dependency as BomDependency};
use cyclonedx_bom::models::external_reference::{
    ExternalReference, ExternalReferenceType, ExternalReferences,
};
use cyclonedx_bom::models::license::{LicenseChoice, Licenses};
use cyclonedx_bom::models::property::{Properties, Property};
use cyclonedx_bom::models::tool::{Tool, Tools};
use cyclonedx_bom::prelude::{
    Bom, Component, Components, Metadata, Purl, SpecVersion, Uri, Validate,
};
use serde_json::json;

use crate::Error;
use crate::graph::{Dependency, Graph};
use crate::metadata::Package;
use crate::options::{Command, Options};

pub(super) fn render(graph: &Graph, options: &Options) -> Result<Vec<u8>, Error> {
    let mut components = BTreeMap::new();
    let mut dependencies = Vec::new();
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
                let missing = missing_component(dependency)?;
                let reference = missing
                    .bom_ref
                    .clone()
                    .expect("missing package has a reference");
                components.entry(reference.clone()).or_insert(missing);
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
            properties.push(Property::new(
                format!("pipdeptree:computed:{field}"),
                &value.to_string(),
            ));
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
    let source = match &options.command {
        None => "environment",
        Some(Command::FromLock { .. }) => "lock",
        Some(Command::FromIndex { .. }) => "index",
    };
    let bom = Bom {
        metadata: Some(Metadata {
            tools: Some(Tools::List(vec![Tool::new(
                "tox-dev",
                "pipdeptree",
                env!("PIPDEPTREE_VERSION"),
            )])),
            properties: Some(Properties(vec![Property::new("pipdeptree:source", source)])),
            ..Metadata::default()
        }),
        components: Some(Components(components.into_values().collect())),
        dependencies: Some(Dependencies(dependencies)),
        spec_version: SpecVersion::V1_5,
        ..Bom::default()
    };
    let mut output = Vec::new();
    bom.output_as_json_v1_5(&mut output)
        .map_err(|error| Error::message(format!("could not serialize CycloneDX SBOM: {error}")))?;
    // The library omits empty dependsOn arrays. An explicit empty array distinguishes known
    // leaves from missing distributions, whose dependency graph is unknown and has no entry.
    let mut value: serde_json::Value = serde_json::from_slice(&output)?;
    if let Some(entries) = value["dependencies"].as_array_mut() {
        for entry in entries {
            entry
                .as_object_mut()
                .expect("CycloneDX dependency is an object")
                .entry("dependsOn")
                .or_insert_with(|| json!([]));
        }
    }
    let mut output = serde_json::to_vec_pretty(&value)?;
    output.push(b'\n');
    Ok(output)
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
    if let Some(expression) = metadata_values(package, "license-expression").first() {
        let license = LicenseChoice::expression(expression);
        component.licenses = Some(Licenses(vec![if license
            .validate_version(SpecVersion::V1_5)
            .passed()
        {
            license
        } else {
            LicenseChoice::license(expression)
        }]));
    } else {
        let license = package.license();
        if license != "(N/A)" {
            component.licenses = Some(Licenses(vec![LicenseChoice::license(
                license
                    .strip_prefix('(')
                    .and_then(|value| value.strip_suffix(')'))
                    .unwrap_or(&license),
            )]));
        }
    }
    let mut properties = Vec::new();
    for value in metadata_values(package, "provides-extra") {
        properties.push(Property::new("pipdeptree:provides-extra", &value));
    }
    component.properties = Some(Properties(properties));
    Ok(component)
}

fn missing_component(dependency: &Dependency) -> Result<Component, Error> {
    let purl = Purl::new("pypi", dependency.key(), "").map_err(|error| {
        Error::message(format!(
            "could not identify missing dependency in SBOM: {error}"
        ))
    })?;
    let mut component = Component::new(
        Classification::Library,
        dependency.key(),
        "",
        Some(purl.to_string()),
    );
    component.version = None;
    component.purl = Some(purl);
    component.scope = Some(Scope::Excluded);
    component.properties = Some(Properties(vec![Property::new(
        "pipdeptree:missing",
        "true",
    )]));
    Ok(component)
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
    // Python well-known Project-URL labels ignore case, whitespace, and punctuation.
    let label = label
        .chars()
        .filter(|character| !character.is_ascii_punctuation() && !character.is_ascii_whitespace())
        .map(|character| character.to_ascii_lowercase())
        .collect::<String>();
    match label.as_str() {
        "homepage" | "website" => ExternalReferenceType::Website,
        "source" | "sourcecode" | "repository" | "code" => ExternalReferenceType::Vcs,
        "issues" | "issuetracker" | "bugtracker" | "bugs" => ExternalReferenceType::IssueTracker,
        "documentation" | "docs" => ExternalReferenceType::Documentation,
        "changelog" | "changes" | "releasenotes" => ExternalReferenceType::ReleaseNotes,
        "download" | "downloads" => ExternalReferenceType::Distribution,
        "license" => ExternalReferenceType::License,
        "chat" => ExternalReferenceType::Chat,
        "mailinglist" => ExternalReferenceType::MailingList,
        "support" => ExternalReferenceType::Support,
        "security" | "securitypolicy" => ExternalReferenceType::Advisories,
        _ => ExternalReferenceType::Other,
    }
}
