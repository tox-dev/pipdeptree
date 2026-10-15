use std::collections::BTreeSet;

use cyclonedx_bom::prelude::{Bom, SpecVersion, Validate};
use rstest::rstest;
use serde_json::{Value, json};

use super::super::common::{PackageSite, execute_with_python, install_resolver, with_python};
use super::{execute, lock_file, path, render_site};

fn read(output: &_pipdeptree::Execution) -> Value {
    assert_eq!(output.code, 0, "{}", output.stderr);
    assert!(output.stdout.ends_with(b"\n"));
    let bom = Bom::parse_from_json(output.stdout.as_slice()).unwrap();
    let validation = bom.validate_version(SpecVersion::V1_5);
    assert!(validation.passed(), "{validation:?}");
    let value: Value = serde_json::from_slice(&output.stdout).unwrap();
    let references = value["components"]
        .as_array()
        .unwrap()
        .iter()
        .map(|component| component["bom-ref"].as_str().unwrap())
        .collect::<BTreeSet<_>>();
    assert_eq!(
        references.len(),
        value["components"].as_array().unwrap().len()
    );
    for dependency in value["dependencies"].as_array().unwrap() {
        assert!(references.contains(dependency["ref"].as_str().unwrap()));
        for child in dependency["dependsOn"].as_array().unwrap() {
            assert!(references.contains(child.as_str().unwrap()));
        }
    }
    value
}

fn component<'a>(value: &'a Value, name: &str) -> &'a Value {
    value["components"]
        .as_array()
        .unwrap()
        .iter()
        .find(|entry| entry["name"] == name)
        .unwrap()
}

fn edges(value: &Value, reference: &str) -> Value {
    value["dependencies"]
        .as_array()
        .unwrap()
        .iter()
        .find(|entry| entry["ref"] == reference)
        .unwrap()["dependsOn"]
        .clone()
}

fn render_environment(site: &PackageSite) -> _pipdeptree::Execution {
    execute(
        site,
        &[
            "-o",
            "cyclonedx-json",
            "--metadata",
            "classifier",
            "--computed",
            "size-raw",
        ],
    )
}

#[test]
fn renders_environment_identity_and_metadata() {
    let output = render_environment(&render_site());
    assert_eq!(output.stderr, "");
    let value = read(&output);
    assert_eq!(value["bomFormat"], "CycloneDX");
    assert_eq!(value["specVersion"], "1.5");
    assert_eq!(value["metadata"]["properties"][0]["value"], "environment");
    assert_eq!(
        value["metadata"]["tools"]["components"][0]["name"],
        "pipdeptree"
    );
    let root = component(&value, "root");
    assert_eq!(root["type"], "library");
    assert_eq!(root["purl"], "pkg:pypi/root@1");
    assert_eq!(root["licenses"], json!([{"expression": "GPL-3.0"}]));
    assert!(
        root["properties"]
            .as_array()
            .unwrap()
            .contains(&json!({"name": "pipdeptree:metadata:classifier", "value": "first"}))
    );
    assert!(
        root["properties"]
            .as_array()
            .unwrap()
            .contains(&json!({"name": "pipdeptree:computed:size_raw", "value": "0"}))
    );
    assert!(
        component(&value, "unique")["properties"]
            .as_array()
            .unwrap()
            .contains(&json!({"name": "pipdeptree:provides-extra", "value": "feature"}))
    );
    assert!(!String::from_utf8_lossy(&output.stdout).contains("pipdeptree:dependency"));
}

#[test]
fn marks_missing_dependencies_with_an_unknown_graph() {
    let value = read(&render_environment(&render_site()));
    let missing = component(&value, "missing");
    assert!(missing.get("version").is_none());
    assert!(missing.get("scope").is_none());
    assert_eq!(missing["purl"], "pkg:pypi/missing");
    assert_eq!(
        value["compositions"],
        json!([{"aggregate": "unknown", "dependencies": ["pkg:pypi/missing"]}])
    );
    assert_eq!(
        edges(&value, "pkg:pypi/root@1"),
        json!(["pkg:pypi/child@1", "pkg:pypi/missing", "pkg:pypi/unique@1"])
    );
}

#[test]
fn renders_a_new_serial_per_run() {
    let site = render_site();
    let mut first = read(&render_environment(&site));
    let mut second = read(&render_environment(&site));
    let serial = first["serialNumber"].as_str().unwrap();
    assert!(serial.starts_with("urn:uuid:"));
    assert_eq!(serial.len(), 45);
    assert_ne!(first["serialNumber"], second["serialNumber"]);
    for document in [&mut first, &mut second] {
        document.as_object_mut().unwrap().remove("serialNumber");
        document["metadata"]
            .as_object_mut()
            .unwrap()
            .remove("timestamp")
            .unwrap();
    }
    assert_eq!(first, second);
}

#[rstest]
#[case::none("none", false)]
#[case::explicit("explicit", true)]
#[case::active("active", true)]
fn obeys_extras_selection(#[case] mode: &str, #[case] included: bool) {
    let site = render_site();
    let value = read(&execute(&site, &["-o", "cyclonedx-json", "--extras", mode]));
    assert_eq!(
        edges(&value, "pkg:pypi/unique@1"),
        if included {
            json!(["pkg:pypi/leaf@1"])
        } else {
            json!([])
        }
    );
}

#[test]
fn filters_components_without_dangling_edges_and_keeps_forward_direction() {
    let site = render_site();
    let value = read(&execute(
        &site,
        &[
            "-o",
            "cyclonedx-json",
            "-p",
            "child",
            "--reverse",
            "--exclude",
            "other",
        ],
    ));
    assert_eq!(
        value["components"]
            .as_array()
            .unwrap()
            .iter()
            .map(|entry| entry["name"].as_str().unwrap())
            .collect::<Vec<_>>(),
        ["child", "missing", "root"]
    );
    assert_eq!(
        edges(&value, "pkg:pypi/root@1"),
        json!(["pkg:pypi/child@1", "pkg:pypi/missing"])
    );
    assert_eq!(edges(&value, "pkg:pypi/child@1"), json!([]));
}

#[test]
fn handles_cycles_and_duplicate_requirements() {
    let site = PackageSite::new();
    site.write("a-1.dist-info", "Name: A_Name\nVersion: 1+local\nSummary: Test package\nRequires-Dist: b>=1\nRequires-Dist: b<3; python_version >= '3'\nLicense: Custom license\n");
    site.write(
        "b-2.dist-info",
        "Name: b\nVersion: 2\nRequires-Dist: a-name\n",
    );
    let value = read(&execute(&site, &["-o", "cyclonedx-json"]));
    let a = component(&value, "A_Name");
    assert_eq!(a["purl"], "pkg:pypi/a-name@1+local");
    assert!(a.get("description").is_none());
    assert_eq!(
        a["licenses"],
        json!([{"license": {"name": "Custom license"}}])
    );

    assert_eq!(
        edges(&value, a["bom-ref"].as_str().unwrap()),
        json!(["pkg:pypi/b@2"])
    );
}

#[test]
fn renders_lock_versions_and_omits_unavailable_metadata() {
    let (_directory, lock) = lock_file(
        "lock-version = '1.0'\n[[packages]]\nname = 'Root.Name'\nversion = '1'\ndependencies = [{ name = 'child' }, { name = 'missing' }]\n[[packages]]\nname = 'child'\n",
    );
    let value = read(&super::super::common::execute(&[
        "from-lock",
        path(&lock),
        "-o",
        "cyclonedx-json",
    ]));
    assert_eq!(value["metadata"]["properties"][0]["value"], "lock");
    assert_eq!(
        component(&value, "Root.Name")["purl"],
        "pkg:pypi/root-name@1"
    );
    assert!(component(&value, "Root.Name").get("licenses").is_none());
    assert!(component(&value, "child").get("version").is_none());
    assert_eq!(
        value["compositions"],
        json!([{"aggregate": "unknown", "dependencies": ["pkg:pypi/missing"]}])
    );
}

#[test]
fn renders_index_dependencies_with_extras() {
    let directory = tempfile::tempdir().unwrap();
    let output = with_python(|python| {
        install_resolver(python, &directory.path().join("capture.txt")).unwrap();
        execute_with_python(
            python,
            &[
                "--warn",
                "silence",
                "from-index",
                "parent[feature]",
                "-o",
                "cyclonedx-json",
            ],
        )
    });
    let value = read(&output);
    assert_eq!(value["metadata"]["properties"][0]["value"], "index");
    assert_eq!(
        edges(&value, "pkg:pypi/parent@1"),
        json!(["pkg:pypi/child@2", "pkg:pypi/external"])
    );
}

#[test]
fn renders_empty_environment() {
    let site = PackageSite::new();
    let value = read(&execute(&site, &["-o", "cyclonedx-json"]));
    assert_eq!(value["components"], json!([]));
    assert_eq!(value["dependencies"], json!([]));
}

#[test]
fn rejects_summary_sbom() {
    let output = execute(&render_site(), &["--summary", "-o", "cyclonedx-json"]);
    assert_eq!(output.stdout, [] as [u8; 0]);
    assert_ne!(output.code, 0);
    assert!(output.stderr.contains("--summary supports only"));
}

#[test]
fn renders_external_references_from_installed_metadata() {
    let site = PackageSite::new();
    site.write(
        "demo-1.dist-info",
        concat!(
            "Name: demo\nVersion: 1\n",
            "Project-URL: Source Code, https://github.com/example/demo\n",
            "Project-URL: Documentation, https://example.org/docs\n",
            "Project-URL: Issue_Tracker, https://example.org/issues\n",
            "Project-URL: Changes, https://example.org/changes\n",
            "Project-URL: Donate, https://example.org/donate\n",
            "Project-URL: Homepage, https://example.org\n",
            "Project-URL: Chat, https://example.org/chat\n",
            "Project-URL: Mailing List, https://example.org/mailing\n",
            "Project-URL: Support, https://example.org/support\n",
            "Project-URL: License, https://example.org/license\n",
            "Project-URL: Security, https://example.org/security\n",
            "Project-URL: Download, https://example.org/download\n",
            "Project-URL: Bug Reports, https://example.org/bugs\n",
            "Project-URL: What's New, https://example.org/new\n",
            "Project-URL: GitHub, https://github.com/example/demo-fork\n",
            "Project-URL: Documentation, https://example.org/docs\n",
            "Project-URL: Invalid, not a URL\n",
            "Project-URL: Empty, \n",
            "Project-URL: Missing separator\n",
            "Home-page: https://example.org/home\n",
            "Download-URL: https://example.org/archive/demo.whl\n",
        ),
    );
    site.write(
        "empty-1.dist-info",
        "Name: empty\nVersion: 1\nHome-page: UNKNOWN\n",
    );
    let value = read(&execute(&site, &["-o", "cyclonedx-json"]));
    let references = component(&value, "demo")["externalReferences"]
        .as_array()
        .unwrap();
    assert_eq!(references.len(), 17);
    for (index, kind) in [
        "vcs",
        "documentation",
        "issue-tracker",
        "release-notes",
        "other",
        "website",
        "chat",
        "mailing-list",
        "support",
        "license",
        "security-contact",
        "distribution",
        "issue-tracker",
        "release-notes",
        "vcs",
        "website",
        "distribution",
    ]
    .into_iter()
    .enumerate()
    {
        assert_eq!(references[index]["type"], kind);
    }
    assert_eq!(references[0]["url"], "https://github.com/example/demo");
    assert_eq!(
        references[0]["comment"],
        "from packaging metadata Project-URL: Source Code"
    );
    assert_eq!(references[15]["url"], "https://example.org/home");
    assert_eq!(
        references[16]["url"],
        "https://example.org/archive/demo.whl"
    );
    assert!(
        component(&value, "empty")
            .get("externalReferences")
            .is_none()
    );
}

#[test]
fn preserves_invalid_spdx_expressions_as_named_licenses() {
    let site = PackageSite::new();
    site.write(
        "demo-1.dist-info",
        "Name: demo\nVersion: 1\nLicense-Expression: Not an SPDX expression\nLicense: MIT\n",
    );

    let value = read(&execute(&site, &["-o", "cyclonedx-json"]));

    assert_eq!(
        component(&value, "demo")["licenses"],
        json!([{"license": {"name": "Not an SPDX expression"}}])
    );
}

#[test]
fn renders_each_license_classifier_as_a_license() {
    let site = PackageSite::new();
    site.write(
        "demo-1.dist-info",
        concat!(
            "Name: demo\nVersion: 1\nLicense: Dual License\n",
            "Classifier: License :: OSI Approved :: BSD License\n",
            "Classifier: License :: OSI Approved :: Apache Software License\n",
            "Classifier: Programming Language :: Python\n",
        ),
    );

    let value = read(&execute(&site, &["-o", "cyclonedx-json"]));

    assert_eq!(
        component(&value, "demo")["licenses"],
        json!([
            {"license": {"name": "BSD License"}},
            {"license": {"name": "Apache Software License"}},
        ])
    );
}

#[test]
fn rejects_packages_without_a_purl_name() {
    let site = PackageSite::new();
    site.write("unnamed-1.dist-info", "Name: \nVersion: 1\n");

    let output = execute(&site, &["-o", "cyclonedx-json"]);

    assert_eq!(output.code, 1);
    assert_eq!(output.stdout, [] as [u8; 0]);
    assert!(
        output
            .stderr
            .contains("could not identify  in SBOM: Invalid Purl:"),
        "{}",
        output.stderr
    );
}
