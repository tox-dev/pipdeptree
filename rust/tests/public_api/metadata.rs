use std::fs;
use std::path::{Path, PathBuf};

use rstest::{fixture, rstest};
use serde_json::{Value, json};
use tempfile::TempDir;

use super::common::{
    PackageSite, execute, execute_in, execute_with_python, stdout, with_python, write_oversized,
};

mod vcs;

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
#[case::site_file(
    "lib/python3.14/site-packages",
    "demo.py",
    "lib/python3.14/site-packages/demo.py",
    4
)]
#[case::posix_script("lib/python3.14/site-packages", "../../../bin/demo", "bin/demo", 4)]
#[case::dist_packages_data(
    "lib/python3/dist-packages",
    "../../../share/demo/data",
    "share/demo/data",
    4
)]
#[case::pypy_script("lib/pypy3.11/site-packages", "../../../bin/demo", "bin/demo", 4)]
#[case::windows_script("Lib/site-packages", "../../Scripts/demo.exe", "Scripts/demo.exe", 4)]
#[case::windows_user_script(
    "Python314/site-packages",
    "../Scripts/demo.exe",
    "Python314/Scripts/demo.exe",
    4
)]
#[case::above_prefix("lib/python3.14/site-packages", "../../../../outside", "../outside", 0)]
#[case::above_target_directory("target", "../outside", "outside", 0)]
#[case::beside_a_bare_site_packages("home/site-packages", "../private", "home/private", 0)]
fn counts_record_rows_inside_the_installation_prefix(
    #[case] site: &str,
    #[case] row: &str,
    #[case] file: &str,
    #[case] size: u64,
) {
    let root = tempfile::tempdir().unwrap();
    let prefix = root.path().join("env");
    let site = prefix.join(site);
    let file = prefix.join(file);
    fs::create_dir_all(file.parent().unwrap()).unwrap();
    fs::write(&file, "data").unwrap();

    assert_eq!(
        sized_distribution(&site, &format!("{row},,\n")),
        json!(size)
    );
}

fn sized_distribution(site: &Path, record: &str) -> Value {
    let metadata = site.join("demo-1.dist-info");
    fs::create_dir_all(&metadata).unwrap();
    fs::write(metadata.join("METADATA"), "Name: demo\nVersion: 1\n").unwrap();
    fs::write(metadata.join("RECORD"), record).unwrap();
    size_raw(site)
}

fn size_raw(site: &Path) -> Value {
    let output = execute(&[
        "--path",
        site.to_str().unwrap(),
        "--computed",
        "size-raw",
        "--json",
    ]);
    let value: Value = serde_json::from_slice(&output.stdout).unwrap();
    value[0]["package"]["computed"]["size_raw"].clone()
}

#[rstest]
#[cfg_attr(unix, case::fifo(make_fifo))]
#[cfg_attr(unix, case::device(link_to_device))]
#[case::oversized(write_oversized)]
fn counts_nothing_for_an_unreadable_record(#[case] create: fn(&Path, &str)) {
    let site = PackageSite::new();
    site.write_file("demo.py", "data");
    let metadata = site.write("demo-1.dist-info", "Name: demo\nVersion: 1\n");
    create(&metadata.join("RECORD"), "demo.py,,\n");

    assert_eq!(size_raw(site.path()), json!(0));
}

#[cfg(unix)]
fn make_fifo(path: &Path, _: &str) {
    assert!(
        std::process::Command::new("mkfifo")
            .arg(path)
            .status()
            .unwrap()
            .success()
    );
}

#[cfg(unix)]
fn link_to_device(path: &Path, _: &str) {
    std::os::unix::fs::symlink("/dev/zero", path).unwrap();
}

#[rstest]
fn ignores_absolute_record_rows_outside_the_site(outside_file: (TempDir, PathBuf)) {
    let (_outside, file) = outside_file;
    let site = PackageSite::new();
    site.write_file("demo.py", "data");

    assert_eq!(
        sized_distribution(site.path(), &format!("demo.py,,\n{},,\n", file.display())),
        json!(4)
    );
}

#[fixture]
fn outside_file() -> (TempDir, PathBuf) {
    let directory = tempfile::tempdir().unwrap();
    let file = directory.path().join("secret");
    fs::write(&file, "x".repeat(100)).unwrap();
    (directory, file)
}

#[test]
fn ignores_record_rows_that_are_not_regular_files() {
    let site = PackageSite::new();
    fs::create_dir(site.path().join("demo")).unwrap();
    site.write_file("demo/__init__.py", "data");

    assert_eq!(
        sized_distribution(site.path(), "demo,,\ndemo/__init__.py,,\n"),
        json!(4)
    );
}

#[test]
fn ignores_the_site_record_for_a_single_file_egg_info() {
    let root = tempfile::tempdir().unwrap();
    let site = root.path().join("site");
    fs::create_dir(&site).unwrap();
    fs::write(site.join("demo-1.egg-info"), "Name: demo\nVersion: 1\n").unwrap();
    fs::write(site.join("RECORD"), "outside,,\n").unwrap();
    fs::write(root.path().join("outside"), "data").unwrap();

    assert_eq!(size_raw(&site), json!(0));
}

#[cfg(unix)]
#[rstest]
fn ignores_record_rows_linked_outside_the_site(outside_file: (TempDir, PathBuf)) {
    let (_outside, file) = outside_file;
    let site = PackageSite::new();
    site.write_file("demo.py", "data");
    std::os::unix::fs::symlink(&file, site.path().join("link.py")).unwrap();

    assert_eq!(
        sized_distribution(site.path(), "demo.py,,\nlink.py,,\n"),
        json!(4)
    );
}

#[cfg(unix)]
#[test]
fn counts_files_of_a_distribution_linked_into_the_site() {
    let profile = tempfile::tempdir().unwrap();
    let store = tempfile::tempdir().unwrap();
    let real_site = store.path().join("lib/python3.14/site-packages");
    let real_metadata = real_site.join("demo-1.dist-info");
    fs::create_dir_all(&real_metadata).unwrap();
    fs::write(real_metadata.join("METADATA"), "Name: demo\nVersion: 1\n").unwrap();
    fs::write(
        real_metadata.join("RECORD"),
        "demo.py,,\n../../../bin/demo,,\n",
    )
    .unwrap();
    fs::write(real_site.join("demo.py"), "data").unwrap();
    fs::create_dir(store.path().join("bin")).unwrap();
    fs::write(store.path().join("bin/demo"), "data").unwrap();
    let site = profile.path().join("lib/python3.14/site-packages");
    fs::create_dir_all(&site).unwrap();
    std::os::unix::fs::symlink(&real_metadata, site.join("demo-1.dist-info")).unwrap();
    std::os::unix::fs::symlink(real_site.join("demo.py"), site.join("demo.py")).unwrap();
    fs::create_dir(profile.path().join("bin")).unwrap();
    std::os::unix::fs::symlink(
        store.path().join("bin/demo"),
        profile.path().join("bin/demo"),
    )
    .unwrap();

    assert_eq!(size_raw(&site), json!(8));
}

#[rstest]
#[case::archive("bundle.zip", 1, true)]
#[case::uppercase_archive("bundle.ZIP", 1, true)]
#[case::console_script_launcher("pipdeptree.exe", 0, false)]
fn warns_only_about_archive_search_paths(
    #[case] name: &str,
    #[case] code: i32,
    #[case] warns: bool,
) {
    let site = PackageSite::new();
    site.write("demo-1.dist-info", "Name: demo\nVersion: 1\n");
    let file = site.path().join(name);
    fs::write(&file, "not a directory").unwrap();

    let output = execute(&[
        "--path",
        site.path().to_str().unwrap(),
        "--path",
        file.to_str().unwrap(),
        "--warn",
        "fail",
    ]);

    assert_eq!(
        (
            output.code,
            stdout(&output).contains("demo==1"),
            output.stderr.contains("unsupported archives"),
            output.stderr.contains(name),
        ),
        (code, true, warns, warns)
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
#[case::name_at_limit(255, 255, true)]
#[case::name_over_limit(256, 1, false)]
#[case::version_over_limit(1, 256, false)]
fn limits_metadata_name_and_version_length(
    #[case] name: usize,
    #[case] version: usize,
    #[case] listed: bool,
) {
    let name = "p".repeat(name);
    let site = PackageSite::new();
    site.write(
        "demo-1.dist-info",
        &format!("Name: {name}\nVersion: {}\n", "1".repeat(version)),
    );

    let output = execute(&["--path", site.path().to_str().unwrap()]);

    assert_eq!(
        (
            output.code,
            stdout(&output).contains(&name),
            output.stderr.contains("missing or invalid metadata"),
        ),
        (0, listed, !listed)
    );
}

#[rstest]
#[cfg_attr(
    unix,
    case::fifo(|metadata: &Path| {
        assert!(std::process::Command::new("mkfifo").arg(metadata).status().unwrap().success());
    })
)]
#[cfg_attr(
    unix,
    case::device(|metadata: &Path| std::os::unix::fs::symlink("/dev/zero", metadata).unwrap())
)]
#[case::oversized_headers(|metadata: &Path| {
    fs::write(metadata, "Name: demo\nVersion: 1\nDescription: ").unwrap();
    fs::OpenOptions::new().append(true).open(metadata).unwrap().set_len((16 << 20) + 1).unwrap();
})]
fn reports_unreadable_metadata_as_invalid(#[case] create: fn(&Path)) {
    let site = PackageSite::new();
    site.write("helper-1.dist-info", "Name: helper\nVersion: 1\n");
    let metadata = site.path().join("demo-1.dist-info");
    fs::create_dir(&metadata).unwrap();
    create(&metadata.join("METADATA"));

    let output = execute(&["--path", site.path().to_str().unwrap(), "--freeze"]);

    assert_eq!(
        (
            output.code,
            stdout(&output),
            output.stderr.contains("missing or invalid metadata")
        ),
        (0, "helper==1\n", true)
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

#[cfg(unix)]
#[test]
fn discovers_symlinked_distributions() {
    let site = PackageSite::new();
    let real = tempfile::tempdir().unwrap();
    let metadata = real.path().join("beta-2.dist-info");
    fs::create_dir(&metadata).unwrap();
    fs::write(metadata.join("METADATA"), "Name: beta\nVersion: 2\n").unwrap();
    std::os::unix::fs::symlink(&metadata, site.path().join("beta-2.dist-info")).unwrap();

    let output = execute_in(&site, &["--json"]);

    assert_eq!(
        (output.code, visible_names(&output)),
        (0, vec!["beta".to_string()])
    );
}

#[test]
fn canonicalizes_boundary_separators() {
    let site = PackageSite::new();
    site.write("odd-1.dist-info", "Name: demo.\nVersion: 1\n");

    let output = execute_in(&site, &["--json"]);
    let value: Value = serde_json::from_slice(&output.stdout).unwrap();

    assert_eq!(
        (output.code, value[0]["package"]["key"].clone()),
        (0, json!("demo-"))
    );
}

#[test]
fn reads_the_legacy_license_field() {
    let site = PackageSite::new();
    site.write(
        "demo-1.dist-info",
        "Name: demo\nVersion: 1\nLicense: BSD-3-Clause\n",
    );

    let output = execute_in(
        &site,
        &["--metadata", "license", "--packages", "demo", "--json"],
    );
    let value: Value = serde_json::from_slice(&output.stdout).unwrap();

    assert_eq!(
        value[0]["package"]["metadata"]["license"].clone(),
        json!("BSD-3-Clause License")
    );
}

#[test]
fn ignores_a_license_field_holding_the_license_text() {
    let site = PackageSite::new();
    site.write(
        "demo-1.dist-info",
        concat!(
            "Name: demo\n",
            "Version: 1\n",
            "License: Redistribution and use in source and binary forms, with or without\n",
            "        modification, are permitted provided that the following conditions\n",
            "        are met.\n",
        ),
    );

    let output = execute_in(
        &site,
        &["--metadata", "license", "--packages", "demo", "--json"],
    );
    let value: Value = serde_json::from_slice(&output.stdout).unwrap();

    assert_eq!(
        value[0]["package"]["metadata"]["license"].clone(),
        json!("N/A License")
    );
}

#[test]
fn prefers_classifiers_over_the_license_field() {
    let site = PackageSite::new();
    site.write(
        "demo-1.dist-info",
        concat!(
            "Name: demo\n",
            "Version: 1\n",
            "License: BSD-3-Clause\n",
            "Classifier: License :: OSI Approved :: MIT License\n",
        ),
    );

    let output = execute_in(
        &site,
        &["--metadata", "license", "--packages", "demo", "--json"],
    );
    let value: Value = serde_json::from_slice(&output.stdout).unwrap();

    assert_eq!(
        value[0]["package"]["metadata"]["license"].clone(),
        json!("MIT License")
    );
}

#[test]
fn stops_crlf_headers_at_the_body() {
    let site = PackageSite::new();
    site.write(
        "windows-1.dist-info",
        "Name: windows\r\nVersion: 1\r\n\r\nRequires-Dist: phantom\r\n",
    );

    let output = execute_in(&site, &["--json"]);

    assert_eq!(
        (
            output.code,
            stdout(&output).contains("\"package_name\": \"windows\""),
            stdout(&output).contains("phantom"),
        ),
        (0, true, false)
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
        (0, "demo===invalid?version!\n", "")
    );
}

#[test]
fn replaces_control_characters_in_header_values() {
    let site = PackageSite::new();
    site.write(
        "hostile-1.dist-info",
        "Name: hostile\x1b[2K\nVersion: 1.0\x1b]52;c;QUJD\x07\nLicense-Expression: MIT\r\x00\n \u{9b}\n",
    );

    let output = execute_in(&site, &["--license"]);

    assert_eq!(
        (output.code, stdout(&output), output.stderr.as_str()),
        (
            0,
            "hostile\u{fffd}[2K==1.0\u{fffd}]52;c;QUJD\u{fffd} (MIT\u{fffd}\u{fffd} \u{fffd} License)\n",
            ""
        )
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
    "demo @ hg+ssh://example.com/demo\n"
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
#[case::at_sign_in_path(
    r#"{"url":"https://example.com/releases@v1/demo.whl","archive_info":{}}"#,
    "demo @ https://example.com/releases@v1/demo.whl\n"
)]
#[case::at_sign_in_password(
    r#"{"url":"https://corp.example:Sp@rk-s3cr3t@pkgs.example.com/demo.whl","archive_info":{}}"#,
    "demo @ https://pkgs.example.com/demo.whl\n"
)]
#[case::at_sign_in_query(
    r#"{"url":"https://user:token@example.com?release=v1@main","archive_info":{}}"#,
    "demo @ https://example.com?release=v1@main\n"
)]
#[case::at_sign_in_fragment(
    r#"{"url":"https://user:token@example.com#egg=demo@v1","archive_info":{}}"#,
    "demo @ https://example.com#egg=demo@v1\n"
)]
#[case::scheme_with_punctuation(
    r#"{"url":"static-http://deploy:s3cr3t@hg.example.com/repo","vcs_info":{"vcs":"hg","commit_id":"abc"}}"#,
    "demo @ hg+static-http://hg.example.com/repo@abc\n"
)]
#[case::scheme_with_digit(
    r#"{"url":"s3://access:s3cr3t@bucket.example.com/demo.whl","archive_info":{}}"#,
    "demo @ s3://bucket.example.com/demo.whl\n"
)]
#[case::credentials_without_path(
    r#"{"url":"https://user:token@example.com","archive_info":{}}"#,
    "demo @ https://example.com\n"
)]
#[case::archive_hashes(
    concat!(
        r#"{"url":"https://example.com/demo.whl","archive_info":{"hashes":{"md5":"bad","sha256":"abc"}},"#,
        r#""subdirectory":"pkg"}"#
    ),
    "demo @ https://example.com/demo.whl#sha256=abc&subdirectory=pkg\n"
)]
#[case::archive_hashes_prefers_strongest(
    r#"{"url":"https://example.com/demo.whl","archive_info":{"hashes":{"sha512":"def","sha256":"abc"}}}"#,
    "demo @ https://example.com/demo.whl#sha512=def\n"
)]
#[case::archive_hashes_unknown_algorithm(
    r#"{"url":"https://example.com/demo.whl","archive_info":{"hashes":{"blake2b":"abc"}}}"#,
    "demo @ https://example.com/demo.whl#blake2b=abc\n"
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
#[case::control_characters(
    r#"{"url":"https://example.com/demo\u001b[A.whl","subdirectory":"s\u0007","archive_info":{"hashes":{"sha256":"ab\u009bcd"}}}"#,
    "demo @ https://example.com/demo\u{fffd}[A.whl#sha256=ab\u{fffd}cd&subdirectory=s\u{fffd}\n"
)]
#[case::whitespace(
    r#"{"url":"https://example.com/demo.whl --index-url\u2028https://evil","subdirectory":"s\t--x","archive_info":{}}"#,
    "demo @ https://example.com/demo.whl%20--index-url%E2%80%A8https://evil#subdirectory=s%09--x\n"
)]
#[case::vcs_name_with_space(
    r#"{"url":"https://example.com/demo","vcs_info":{"vcs":"git --x","commit_id":"abc"}}"#,
    "demo @ git%20--x+https://example.com/demo@abc\n"
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

#[rstest]
#[cfg_attr(unix, case::fifo(make_fifo))]
#[cfg_attr(unix, case::device(link_to_device))]
#[case::oversized(write_oversized)]
fn falls_back_for_unreadable_direct_urls(#[case] create: fn(&Path, &str)) {
    let site = PackageSite::new();
    let metadata = site.write("demo-1.dist-info", "Name: demo\nVersion: 1\n");
    create(
        &metadata.join("direct_url.json"),
        r#"{"url":"https://example.com/demo.whl","archive_info":{}}"#,
    );

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

#[test]
fn ignores_the_site_direct_url_for_a_single_file_egg_info() {
    let site = PackageSite::new();
    site.write_file("demo-1.egg-info", "Name: demo\nVersion: 1\n");
    site.write_file(
        "direct_url.json",
        r#"{"url":"https://example.com/demo.whl","archive_info":{}}"#,
    );

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

#[rstest]
#[case::space("my%20proj")]
#[case::line_break_and_escape("x%0A--index-url%20https:evil%1B[31m")]
#[case::unicode_line_separator("x%E2%80%A8--index-url%20https:evil")]
fn freezes_editable_locations_that_need_encoding_as_file_urls(#[case] encoded: &str) {
    let site = PackageSite::new();
    let metadata = site.write("demo-1.dist-info", "Name: demo\nVersion: 1\n");
    let url = format!(
        "{}/{encoded}",
        url::Url::from_file_path(site.path()).unwrap()
    );
    fs::write(
        metadata.join("direct_url.json"),
        format!(r#"{{"url":"{url}","dir_info":{{"editable":true}}}}"#),
    )
    .unwrap();

    let output = execute_in(&site, &["--freeze"]);
    let expected = format!("# Editable install with no version control (demo==1)\n-e {url}\n");

    assert_eq!(
        (output.code, stdout(&output), output.stderr.as_str()),
        (0, expected.as_str(), "")
    );
}

#[test]
fn freezes_unicode_editable_locations_as_paths() {
    let site = PackageSite::new();
    let metadata = site.write("demo-1.dist-info", "Name: demo\nVersion: 1\n");
    fs::write(
        metadata.join("direct_url.json"),
        format!(
            r#"{{"url":"{}/%E6%97%A5%E6%9C%AC","dir_info":{{"editable":true}}}}"#,
            url::Url::from_file_path(site.path()).unwrap()
        ),
    )
    .unwrap();

    let output = execute_in(&site, &["--freeze"]);
    let expected = format!(
        "# Editable install with no version control (demo==1)\n-e {}\n",
        site.path().join("日本").display()
    );

    assert_eq!(
        (output.code, stdout(&output), output.stderr.as_str()),
        (0, expected.as_str(), "")
    );
}

#[test]
fn freezes_editable_comment_without_coding_declaration() {
    let site = PackageSite::new();
    let metadata = site.write(
        "demo-0.dist-info",
        "Name: demo\nVersion: 0 coding:utf-7 +AAo---index-url=http://127.0.0.1:9/x+AAo-#\n",
    );
    fs::write(
        metadata.join("direct_url.json"),
        format!(
            r#"{{"url":"{}","dir_info":{{"editable":true}}}}"#,
            url::Url::from_file_path(site.path()).unwrap()
        ),
    )
    .unwrap();

    let output = execute_in(&site, &["--freeze"]);
    let expected = format!(
        "# Editable install with no version control (demo==0?coding?utf-7?+AAo---index-url?http???127.0.0.1?9?x+AAo-?)\n-e {}\n",
        site.path().display()
    );

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
fn ignores_oversized_legacy_editable_links() {
    let site = PackageSite::new();
    let metadata = site.path().join("demo-1.egg-info");
    fs::create_dir(&metadata).unwrap();
    fs::write(metadata.join("PKG-INFO"), "Name: demo\nVersion: 1\n").unwrap();
    write_oversized(
        &site.path().join("demo.egg-link"),
        &format!("{}\n", site.path().display()),
    );

    let output = execute_in(&site, &["--freeze"]);

    assert_eq!(
        (output.code, stdout(&output), output.stderr.as_str()),
        (0, "demo==1\n", "")
    );
}

#[test]
fn freezes_legacy_editable_targets_with_spaces_as_file_urls() {
    let site = PackageSite::new();
    let project = site.path().join("my proj --index-url=https:evil");
    let metadata = project.join("demo-1.egg-info");
    fs::create_dir_all(&metadata).unwrap();
    fs::write(metadata.join("PKG-INFO"), "Name: demo\nVersion: 1\n").unwrap();
    site.write_file("demo.egg-link", &format!("{}\n.\n", project.display()));

    let output = execute(&[
        "--path",
        site.path().to_str().unwrap(),
        "--path",
        project.to_str().unwrap(),
        "--warn",
        "silence",
        "--freeze",
    ]);
    let expected = format!(
        "# Editable install with no version control (demo==1)\n-e {}\n",
        url::Url::from_file_path(&project).unwrap()
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

#[rstest]
#[case::dist_info("demo-1.dist-info/METADATA", ".")]
#[case::another_directory("demo-1.egg-info/PKG-INFO", "other")]
fn ignores_legacy_editable_links_of_other_installs(#[case] metadata: &str, #[case] link: &str) {
    let site = PackageSite::new();
    let metadata = site.path().join(metadata);
    fs::create_dir(metadata.parent().unwrap()).unwrap();
    fs::write(&metadata, "Name: demo\nVersion: 1\n").unwrap();
    fs::create_dir(site.path().join("other")).unwrap();
    site.write_file(
        "demo.egg-link",
        &site.path().join(link).display().to_string(),
    );

    let output = execute_in(&site, &["--freeze"]);

    assert_eq!(
        (output.code, stdout(&output), output.stderr.as_str()),
        (0, "demo==1\n", "")
    );
}

#[cfg(unix)]
#[test]
fn ignores_symlinked_legacy_editable_links() {
    let site = PackageSite::new();
    let metadata = site.path().join("demo-1.egg-info");
    fs::create_dir(&metadata).unwrap();
    fs::write(metadata.join("PKG-INFO"), "Name: demo\nVersion: 1\n").unwrap();
    let outside = tempfile::tempdir().unwrap();
    fs::write(
        outside.path().join("file"),
        site.path().display().to_string(),
    )
    .unwrap();
    std::os::unix::fs::symlink(
        outside.path().join("file"),
        site.path().join("demo.egg-link"),
    )
    .unwrap();

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
