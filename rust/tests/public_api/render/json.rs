use rstest::rstest;
use serde_json::{Value, json};

use super::{execute, lock_file, path, render_site, sized_site, text};

#[test]
fn renders_flat_json_fields() {
    let site = render_site();
    let output = execute(
        &site,
        &[
            "--json",
            "--metadata",
            "classifier,license,unknown",
            "--computed",
            "size,size-raw,unique-deps-count,unique-deps-names,unique-deps-size",
        ],
    );
    let value: Value = serde_json::from_slice(&output.stdout).unwrap();
    let root = value
        .as_array()
        .unwrap()
        .iter()
        .find(|entry| entry["package"]["key"] == "root")
        .unwrap();

    assert_eq!(
        (
            &root["package"]["metadata"],
            &root["package"]["computed"],
            &root["dependencies"][0]["installed_version"],
            &root["dependencies"][0]["required_version"],
            &root["dependencies"][1]["extra"],
            &root["dependencies"][2]["installed_version"],
        ),
        (
            &json!({
                "classifier": ["first", "second"],
                "license": "GPL-3.0 License",
                "unknown": "N/A",
            }),
            &json!({
                "size": "0 B",
                "size_raw": 0,
                "unique_deps_count": 2,
                "unique_deps_names": ["leaf", "unique"],
                "unique_deps_size": "0 B",
            }),
            &json!("1"),
            &json!(">=2"),
            &Value::Null,
            &json!("1"),
        )
    );
}

#[rstest]
#[case::bytes(0, "0 B")]
#[case::kilobytes(1_536, "1.5 KB")]
#[case::megabytes(1_572_864, "1.5 MB")]
#[case::gigabytes(1_610_612_736, "1.5 GB")]
fn formats_computed_sizes(#[case] bytes: u64, #[case] expected: &str) {
    let site = sized_site(bytes);
    let output = execute(&site, &["--json", "--computed", "size"]);
    let value: Value = serde_json::from_slice(&output.stdout).unwrap();

    assert_eq!(value[0]["package"]["computed"]["size"], expected);
}

#[rstest]
#[case::forward(&["--json-tree"] as &[&str])]
#[case::reverse(&["--json-tree", "--reverse"])]
fn renders_json_trees(#[case] args: &[&str]) {
    let site = render_site();
    let output = execute(
        &site,
        &args
            .iter()
            .copied()
            .chain([
                "--metadata",
                "classifier",
                "--computed",
                "size,size-raw,unique-deps-count,unique-deps-names,unique-deps-size",
            ])
            .collect::<Vec<_>>(),
    );
    let value: Value = serde_json::from_slice(&output.stdout).unwrap();

    assert_eq!(
        (
            value.is_array(),
            text(&output).contains("\"dependencies\""),
            text(&output).contains("\"computed\""),
            text(&output).contains("\"metadata\""),
        ),
        (true, true, true, true)
    );
}

#[test]
fn orders_json_tree_keys_by_insertion() {
    let site = render_site();
    let output = execute(&site, &["--json-tree"]);
    let rendered = text(&output);
    let positions = [
        "\"key\"",
        "\"package_name\"",
        "\"installed_version\"",
        "\"required_version\"",
        "\"dependencies\"",
    ]
    .map(|field| rendered.find(field).unwrap());

    assert!(positions.is_sorted(), "unexpected key order: {rendered}");
}

#[test]
fn lists_missing_packages_in_reverse_json_tree() {
    let site = render_site();
    let output = execute(&site, &["--json-tree", "--reverse"]);
    let value: Value = serde_json::from_slice(&output.stdout).unwrap();
    let entry = value
        .as_array()
        .unwrap()
        .iter()
        .find(|entry| entry["key"] == "missing")
        .expect("missing package renders as a reverse root");

    assert_eq!(
        (
            &entry["installed_version"],
            &entry["dependencies"][0]["package_name"],
            &entry["dependencies"][0]["required_version"],
        ),
        (&json!("?"), &json!("root"), &json!("Any"))
    );
}

#[test]
fn stops_reverse_json_tree_cycles() {
    let site = super::PackageSite::new();
    site.write(
        "first-1.dist-info",
        "Name: first\nVersion: 1\nRequires-Dist: second\n",
    );
    site.write(
        "second-1.dist-info",
        "Name: second\nVersion: 1\nRequires-Dist: first\n",
    );

    let output = execute(&site, &["--json-tree", "--reverse"]);
    let value: Value = serde_json::from_slice(&output.stdout).unwrap();

    assert_eq!(
        (
            output.code,
            &value[0]["key"],
            &value[0]["dependencies"][0]["key"],
            &value[0]["dependencies"][0]["dependencies"][0],
        ),
        (0, &json!("first"), &json!("second"), &Value::Null)
    );
}

#[test]
fn lists_missing_candidates_in_resolved_reverse_json_tree() {
    let (_directory, lock) = lock_file(concat!(
        "lock-version = '1.0'\n",
        "[[packages]]\nname = 'root'\nversion = '1'\n",
        "dependencies = [{ name = 'ghost' }]\n",
    ));

    let output =
        super::super::common::execute(&["--json-tree", "--reverse", "from-lock", path(&lock)]);
    let value: Value = serde_json::from_slice(&output.stdout).unwrap();
    let entry = value
        .as_array()
        .unwrap()
        .iter()
        .find(|entry| entry["key"] == "ghost")
        .expect("unresolved candidate renders as a reverse root");

    assert_eq!(
        (
            &entry["candidate_version"],
            &entry["required_version"],
            &entry["dependencies"][0]["package_name"],
        ),
        (&json!("?"), &Value::Null, &json!("root"))
    );
}

#[test]
fn renders_resolved_json_fields() {
    let (_directory, lock) = lock_file(concat!(
        "lock-version = '1.0'\n",
        "[[packages]]\nname = 'root'\nversion = '1'\n",
        "dependencies = [{ name = 'child' }]\n",
        "[[packages]]\nname = 'child'\nversion = '2'\n",
    ));

    for args in [
        &["--json"] as &[&str],
        &["--json-tree"],
        &["--json-tree", "--reverse"],
    ] {
        let output = super::super::common::execute(
            &args
                .iter()
                .copied()
                .chain(["from-lock", path(&lock)])
                .collect::<Vec<_>>(),
        );
        let value: Value = serde_json::from_slice(&output.stdout).unwrap();
        let value = value.to_string();

        assert_eq!(
            (
                value.contains("candidate_version"),
                value.contains("installed_version"),
            ),
            (true, false)
        );
    }
}
