use std::fs;

use rstest::{fixture, rstest};
use serde_json::{Value, json};

use super::common::{PackageSite, execute, execute_in, execute_with_python, stdout, with_python};

#[test]
fn renders_selected_metadata_and_size() {
    let site = PackageSite::new();
    let metadata = site.write(
        "demo-1.dist-info",
        concat!(
            "Name: Demo.Name\n",
            "Version: 1\n",
            "Author: first\n",
            " second\n",
            "Author: third\n",
            "Unknown: retained\n",
            " folded\n",
            "Discarded: ignored\n",
            " folded but discarded\n",
            "License-Expression: MIT License\n",
            "Requires-Python: >=3.10\n",
            "\n",
            "invalid body\n",
        ),
    );
    fs::write(site.path().join("demo.py"), "data").unwrap();
    fs::write(
        metadata.join("RECORD"),
        "demo.py,,\nmissing.py,,\n\"unterminated\n",
    )
    .unwrap();

    let output = execute_in(
        &site,
        &[
            "--packages",
            "demo_name",
            "--metadata",
            "license,author,unknown,absent",
            "--computed",
            "size,size-raw",
            "--json",
        ],
    );
    let value: Value = serde_json::from_slice(&output.stdout).unwrap();

    assert_eq!(
        (
            output.code,
            value[0]["package"]["key"].clone(),
            value[0]["package"]["metadata"].clone(),
            value[0]["package"]["computed"].clone(),
            output.stderr.as_str(),
        ),
        (
            0,
            json!("demo-name"),
            json!({
                "author": ["first second", "third"],
                "absent": "N/A",
                "license": "MIT License",
                "unknown": "retained folded",
            }),
            json!({"size": "4 B", "size_raw": 4}),
            "",
        )
    );
}

#[rstest]
fn discovers_metadata_forms(metadata_sites: (PackageSite, PackageSite)) {
    let (first, second) = metadata_sites;
    let output = execute(&[
        "--path",
        first.path().to_str().unwrap(),
        "--path",
        second.path().to_str().unwrap(),
        "--path",
        "/path/that/does/not/exist",
        "--warn",
        "suppress",
        "--json",
    ]);

    assert_eq!(
        (
            output.code,
            visible_names(&output),
            output.stderr.contains("missing or invalid metadata"),
            output.stderr.contains("duplicate package metadata"),
        ),
        (
            0,
            ["demo", "egg", "file", "leading"]
                .map(str::to_string)
                .to_vec(),
            false,
            false,
        )
    );
}

#[rstest]
#[case::suppress("suppress", 0)]
#[case::fail("fail", 1)]
fn reports_metadata_warnings(
    metadata_sites: (PackageSite, PackageSite),
    #[case] warning: &str,
    #[case] code: i32,
) {
    let (first, second) = metadata_sites;
    let warnings = execute(&[
        "--path",
        first.path().to_str().unwrap(),
        "--path",
        second.path().to_str().unwrap(),
        "--warn",
        warning,
    ]);

    assert_eq!(
        (
            warnings.code,
            warnings.stderr.contains("missing or invalid metadata"),
            warnings.stderr.contains("duplicate package metadata"),
            warnings.stderr.contains(second.path().to_str().unwrap()),
            warnings.stderr.contains(first.path().to_str().unwrap()),
        ),
        (code, true, true, true, true)
    );
}

#[test]
fn keeps_packages_with_malformed_header_lines() {
    let site = PackageSite::new();
    site.write(
        "legacy-1.dist-info",
        "Name: legacy\nMalformed header\nVersion: 1\n",
    );

    let output = execute(&[
        "--path",
        site.path().to_str().unwrap(),
        "--warn",
        "fail",
        "--json",
    ]);

    assert_eq!(
        (output.code, visible_names(&output), output.stderr.as_str()),
        (0, vec!["legacy".to_string()], "")
    );
}

#[fixture]
fn metadata_sites() -> (PackageSite, PackageSite) {
    let first = PackageSite::new();
    first.write("demo-1.dist-info", "Name: demo\nVersion: 1\n");
    first.write_file("file.egg-info", "Name: file\nVersion: 1\n");
    first.write_file("leading.egg-info", " folded\nName: leading\nVersion: 1\n");
    let egg = first.path().join("egg.egg-info");
    fs::create_dir(&egg).unwrap();
    fs::write(egg.join("PKG-INFO"), "Name: egg\nVersion: 1\n").unwrap();
    first.write("missing-name.dist-info", "Version: 1\n");
    first.write("invalid.dist-info", "invalid header\n");
    let second = PackageSite::new();
    second.write("duplicate-2.dist-info", "Name: demo\nVersion: 2\n");
    (first, second)
}

#[test]
fn renders_classifier_licenses() {
    let site = PackageSite::new();
    site.write(
        "demo-1.dist-info",
        concat!(
            "Name: demo\n",
            "Version: 1\n",
            "Classifier: License :: OSI Approved :: BSD License\n",
            "Classifier: License :: OSI Approved :: MIT License\n",
        ),
    );

    let output = execute_in(
        &site,
        &["--metadata", "license", "--packages", "demo", "--json"],
    );
    let value: Value = serde_json::from_slice(&output.stdout).unwrap();

    assert_eq!(
        (
            output.code,
            value[0]["package"]["metadata"]["license"].clone(),
            output.stderr.as_str(),
        ),
        (0, json!("BSD License, MIT License"), "")
    );
}

#[test]
fn freezes_arbitrary_versions() {
    let site = PackageSite::new();
    site.write(
        "demo-invalid.dist-info",
        "Name: demo\nVersion: invalid version!\n",
    );

    let output = execute_in(&site, &["--freeze"]);

    assert_eq!(
        (output.code, stdout(&output), output.stderr.as_str()),
        (0, "demo===invalid version!\n", "")
    );
}

#[test]
fn discovers_empty_runtime_path_from_current_directory() {
    let directory = tempfile::tempdir().unwrap();
    let metadata = directory.path().join("demo-1.dist-info");
    fs::create_dir(&metadata).unwrap();
    fs::write(metadata.join("METADATA"), "Name: demo\nVersion: 1\n").unwrap();

    let output = with_python(|python| {
        use pyo3::prelude::PyAnyMethods as _;

        let sys = pyo3::types::PyModule::import(python, "sys").unwrap();
        let path = sys.getattr("path").unwrap();
        let original = path.call_method0("copy").unwrap();
        path.call_method0("clear").unwrap();
        path.call_method1("append", ("",)).unwrap();
        let current = std::env::current_dir().unwrap();
        std::env::set_current_dir(directory.path()).unwrap();
        let output = execute_with_python(python, &["--warn", "silence", "--json"]);
        std::env::set_current_dir(current).unwrap();
        sys.setattr("path", original).unwrap();
        output
    });

    assert_eq!(
        (output.code, stdout(&output), output.stderr.as_str()),
        (
            0,
            concat!(
                "[\n",
                "    {\n",
                "        \"package\": {\n",
                "            \"key\": \"demo\",\n",
                "            \"package_name\": \"demo\",\n",
                "            \"installed_version\": \"1\"\n",
                "        },\n",
                "        \"dependencies\": []\n",
                "    }\n",
                "]\n",
            ),
            "",
        )
    );
}

#[rstest]
#[case::vcs_commit(
    r#"{"url":"https://user:token@example.com/demo.git","vcs_info":{"vcs":"git","commit_id":"abc"}}"#,
    "demo @ git+https://example.com/demo.git@abc\n"
)]
#[case::vcs_revision(
    r#"{"url":"ssh://git@example.com/demo","vcs_info":{"vcs":"hg","requested_revision":"feature"}}"#,
    "demo @ hg+ssh://example.com/demo@feature\n"
)]
#[case::vcs_full(
    concat!(
        r#"{"url":"https://user:token@example.com/demo.git","vcs_info":{"vcs":"git","commit_id":"abc","#,
        r#""requested_revision":"feature"},"subdirectory":"pkg"}"#
    ),
    "demo @ git+https://example.com/demo.git@abc#subdirectory=pkg\n"
)]
#[case::archive_hash(
    r#"{"url":"https://user:token@example.com/demo.whl","archive_info":{"hash":"sha256=abc"}}"#,
    "demo @ https://example.com/demo.whl#sha256=abc\n"
)]
#[case::archive_hashes(
    concat!(
        r#"{"url":"https://example.com/demo.whl","archive_info":{"hashes":{"sha512":"def","sha256":"abc"}},"#,
        r#""subdirectory":"pkg"}"#
    ),
    "demo @ https://example.com/demo.whl#sha256=abc&subdirectory=pkg\n"
)]
#[case::archive_hashes_precede_hash(
    r#"{"url":"https://example.com/demo.whl","archive_info":{"hash":"sha256=old","hashes":{"sha256":"new"}}}"#,
    "demo @ https://example.com/demo.whl#sha256=new\n"
)]
#[case::numeric_archive_hash(
    r#"{"url":"https://example.com/demo.whl","archive_info":{"hashes":{"sha256":123}}}"#,
    "demo @ https://example.com/demo.whl#sha256=123\n"
)]
#[case::directory(
    r#"{"url":"https://example.com/demo","dir_info":{"editable":false},"subdirectory":"pkg"}"#,
    "demo @ https://example.com/demo#subdirectory=pkg\n"
)]
#[case::environment_credentials(
    r#"{"url":"https://${USER}:${TOKEN}@example.com/demo.whl","archive_info":{}}"#,
    "demo @ https://${USER}:${TOKEN}@example.com/demo.whl\n"
)]
#[case::git_user(
    r#"{"url":"ssh://git@example.com/demo.git","vcs_info":{"vcs":"git"}}"#,
    "demo @ git+ssh://git@example.com/demo.git\n"
)]
#[case::token_credentials(
    r#"{"url":"https://token@example.com/demo.whl","archive_info":{}}"#,
    "demo @ https://example.com/demo.whl\n"
)]
#[case::mixed_environment_credentials(
    r#"{"url":"https://${TOKEN}:secret@example.com/demo.whl","archive_info":{}}"#,
    "demo @ https://example.com/demo.whl\n"
)]
#[case::scp_vcs(
    r#"{"url":"git@example.com:demo.git","vcs_info":{"vcs":"git","commit_id":"abc"}}"#,
    "demo @ git+git@example.com:demo.git@abc\n"
)]
#[case::invalid_scheme(
    r#"{"url":"1https://user:token@example.com/demo.whl","archive_info":{}}"#,
    "demo @ 1https://user:token@example.com/demo.whl\n"
)]
#[case::no_credentials(
    r#"{"url":"https://example.com/demo.whl","archive_info":{}}"#,
    "demo @ https://example.com/demo.whl\n"
)]
#[case::no_scheme(
    r#"{"url":"local-demo.whl","archive_info":{}}"#,
    "demo @ local-demo.whl\n"
)]
fn freezes_direct_urls(#[case] direct_url: &str, #[case] expected: &str) {
    let site = PackageSite::new();
    let metadata = site.write("demo-1.dist-info", "Name: demo\nVersion: 1\n");
    fs::write(metadata.join("direct_url.json"), direct_url).unwrap();

    let output = execute_in(&site, &["--freeze"]);

    assert_eq!(
        (output.code, stdout(&output), output.stderr.as_str()),
        (0, expected, "")
    );
}

#[rstest]
#[case::malformed("not json")]
#[case::array("[]")]
#[case::missing_url(r#"{"archive_info":{}}"#)]
#[case::non_string_url(r#"{"url":1,"archive_info":{}}"#)]
#[case::non_string_subdirectory(
    r#"{"url":"https://example.com/demo","subdirectory":1,"archive_info":{}}"#
)]
#[case::missing_info(r#"{"url":"https://example.com/demo"}"#)]
#[case::multiple_info(r#"{"url":"https://example.com/demo","archive_info":{},"dir_info":{}}"#)]
#[case::non_object_info(r#"{"url":"https://example.com/demo","archive_info":[]}"#)]
#[case::non_object_vcs_info(r#"{"url":"https://example.com/demo","vcs_info":[]}"#)]
#[case::non_object_directory_info(r#"{"url":"https://example.com/demo","dir_info":[]}"#)]
#[case::missing_vcs(r#"{"url":"https://example.com/demo","vcs_info":{}}"#)]
#[case::non_string_vcs(r#"{"url":"https://example.com/demo","vcs_info":{"vcs":1}}"#)]
#[case::non_string_commit(
    r#"{"url":"https://example.com/demo","vcs_info":{"vcs":"git","commit_id":1}}"#
)]
#[case::non_string_revision(
    r#"{"url":"https://example.com/demo","vcs_info":{"vcs":"git","requested_revision":1}}"#
)]
#[case::invalid_hash(r#"{"url":"https://example.com/demo","archive_info":{"hash":"sha256"}}"#)]
#[case::hash_without_algorithm(
    r#"{"url":"https://example.com/demo","archive_info":{"hash":"=abc"}}"#
)]
#[case::hash_without_digest(
    r#"{"url":"https://example.com/demo","archive_info":{"hash":"sha256="}}"#
)]
#[case::non_object_hashes(r#"{"url":"https://example.com/demo","archive_info":{"hashes":[]}}"#)]
#[case::non_boolean_editable(r#"{"url":"https://example.com/demo","dir_info":{"editable":"yes"}}"#)]
fn falls_back_for_invalid_direct_urls(#[case] direct_url: &str) {
    let site = PackageSite::new();
    let metadata = site.write("demo-1.dist-info", "Name: demo\nVersion: 1\n");
    fs::write(metadata.join("direct_url.json"), direct_url).unwrap();

    let output = execute_in(&site, &["--freeze"]);

    assert_eq!(
        (output.code, stdout(&output), output.stderr.as_str()),
        (0, "demo==1\n", "")
    );
}

#[test]
fn falls_back_for_non_utf8_direct_urls() {
    let site = PackageSite::new();
    let metadata = site.write("demo-1.dist-info", "Name: demo\nVersion: 1\n");
    fs::write(metadata.join("direct_url.json"), [0xff]).unwrap();

    let output = execute_in(&site, &["--freeze"]);

    assert_eq!(
        (output.code, stdout(&output), output.stderr.as_str()),
        (0, "demo==1\n", "")
    );
}

#[rstest]
#[case::file(true)]
#[case::https(false)]
fn freezes_editable_directories(#[case] file_url: bool) {
    let site = PackageSite::new();
    let metadata = site.write("demo-1.dist-info", "Name: demo\nVersion: 1\n");
    let url = if file_url {
        url::Url::from_file_path(site.path()).unwrap().to_string()
    } else {
        "https://example.com/demo".to_string()
    };
    fs::write(
        metadata.join("direct_url.json"),
        format!(r#"{{"url":"{url}","dir_info":{{"editable":true}}}}"#),
    )
    .unwrap();

    let output = execute_in(&site, &["--freeze"]);
    let expected = if file_url {
        format!(
            "# Editable install with no version control (demo==1)\n-e {}\n",
            site.path().display()
        )
    } else {
        "demo==1\n".to_string()
    };

    assert_eq!(
        (output.code, stdout(&output), output.stderr.as_str()),
        (0, expected.as_str(), "")
    );
}

#[test]
fn freezes_legacy_editable() {
    let site = PackageSite::new();
    let metadata = site.path().join("demo_name-1.egg-info");
    fs::create_dir(&metadata).unwrap();
    fs::write(metadata.join("PKG-INFO"), "Name: demo_name\nVersion: 1\n").unwrap();
    site.write_file(
        "demo-name.egg-link",
        &format!("{}\nignored\n", site.path().display()),
    );

    let output = execute_in(&site, &["--freeze"]);
    let expected = format!(
        "# Editable install with no version control (demo_name==1)\n-e {}\n",
        site.path().display()
    );

    assert_eq!(
        (output.code, stdout(&output), output.stderr.as_str()),
        (0, expected.as_str(), "")
    );
}

#[test]
fn ignores_empty_legacy_editable_links() {
    let site = PackageSite::new();
    let metadata = site.path().join("demo-1.egg-info");
    fs::create_dir(&metadata).unwrap();
    fs::write(metadata.join("PKG-INFO"), "Name: demo\nVersion: 1\n").unwrap();
    site.write_file("demo.egg-link", "");

    let output = execute_in(&site, &["--freeze"]);

    assert_eq!(
        (output.code, stdout(&output), output.stderr.as_str()),
        (0, "demo==1\n", "")
    );
}

fn visible_names(output: &_pipdeptree::Execution) -> Vec<String> {
    serde_json::from_slice::<Vec<Value>>(&output.stdout)
        .unwrap()
        .iter()
        .map(|value| {
            value["package"]["package_name"]
                .as_str()
                .unwrap()
                .to_string()
        })
        .collect()
}
