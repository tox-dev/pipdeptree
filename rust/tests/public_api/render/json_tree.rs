use super::{execute, lock_file, path, render_site, text};
use rstest::rstest;
use serde_json::{Value, json};

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
fn lists_missing_dependencies_in_forward_json_tree() {
    let site = render_site();
    let output = execute(&site, &["--json-tree"]);
    let value: Value = serde_json::from_slice(&output.stdout).unwrap();
    let root = value
        .as_array()
        .unwrap()
        .iter()
        .find(|entry| entry["key"] == "root")
        .unwrap();
    let missing = root["dependencies"]
        .as_array()
        .unwrap()
        .iter()
        .find(|entry| entry["key"] == "missing")
        .expect("missing dependency appears under its dependent");

    assert_eq!(
        (&missing["installed_version"], &missing["dependencies"]),
        (&json!("?"), &json!([]))
    );
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
