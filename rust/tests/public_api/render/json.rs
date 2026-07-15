use super::{execute, lock_file, path, render_site, sized_site};
use rstest::rstest;
use serde_json::{Value, json};

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

#[test]
fn lists_missing_packages_in_flat_reverse_json() {
    let site = render_site();
    let output = execute(&site, &["--json", "--reverse"]);
    let value: Value = serde_json::from_slice(&output.stdout).unwrap();
    let entry = value
        .as_array()
        .unwrap()
        .iter()
        .find(|entry| entry["package"]["key"] == "missing")
        .expect("missing package appears in reverse flat json");

    assert_eq!(
        (
            &entry["package"]["installed_version"],
            &entry["dependencies"][0]["package_name"],
        ),
        (&json!("?"), &json!("root"))
    );
}

#[test]
fn reverses_flat_json_dependencies() {
    let site = render_site();
    let output = execute(&site, &["--json", "--reverse"]);
    let value: Value = serde_json::from_slice(&output.stdout).unwrap();
    let child = value
        .as_array()
        .unwrap()
        .iter()
        .find(|entry| entry["package"]["key"] == "child")
        .unwrap();
    let dependents = child["dependencies"].as_array().unwrap();

    assert_eq!(
        (
            dependents
                .iter()
                .map(|entry| entry["key"].as_str().unwrap())
                .collect::<Vec<_>>(),
            &dependents[1]["required_version"],
        ),
        (vec!["other", "root"], &json!(">=2"))
    );
}

#[test]
fn lists_missing_candidates_in_resolved_json() {
    let (_directory, lock) = lock_file(concat!(
        "lock-version = '1.0'\n",
        "[[packages]]\nname = 'root'\nversion = '1'\n",
        "dependencies = [{ name = 'ghost' }]\n",
    ));

    let forward = super::super::common::execute(&["--json-tree", "from-lock", path(&lock)]);
    let reverse = super::super::common::execute(&["--json", "--reverse", "from-lock", path(&lock)]);
    let forward_value: Value = serde_json::from_slice(&forward.stdout).unwrap();
    let reverse_value: Value = serde_json::from_slice(&reverse.stdout).unwrap();
    let entry = reverse_value
        .as_array()
        .unwrap()
        .iter()
        .find(|entry| entry["package"]["key"] == "ghost")
        .expect("unresolved candidate appears in reverse flat json");

    assert_eq!(
        (
            &forward_value[0]["dependencies"][0]["candidate_version"],
            &entry["package"]["candidate_version"],
            &entry["dependencies"][0]["package_name"],
        ),
        (&json!("?"), &json!("?"), &json!("root"))
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
        &["--json", "--reverse"],
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
