use rstest::rstest;
use serde_json::Value;

use super::{PackageSite, execute, lock_file, path, render_site, text};

#[test]
fn renders_installed_summary_metrics() {
    let site = render_site();
    let output = execute(&site, &["--summary", "--output", "json"]);
    let value: Value = serde_json::from_slice(&output.stdout).unwrap();

    assert_eq!(
        (
            value["total_packages"].as_u64(),
            value["direct_dependencies"].as_u64(),
            value["transitive_dependencies"].as_u64(),
            value["max_depth"].as_u64(),
            value["missing_dependencies"].as_u64(),
            value["conflicting_dependencies"]["packages"].as_u64(),
            value["conflicting_dependencies"]["edges"].as_u64(),
            value["licenses"]["copyleft"].as_bool(),
            value["min_requires_python"].as_str(),
            value["total_size_raw"].as_u64(),
        ),
        (
            Some(6),
            Some(3),
            Some(3),
            Some(3),
            Some(1),
            Some(1),
            Some(2),
            Some(true),
            Some("3.11"),
            Some(0),
        )
    );
}

#[rstest]
#[case::plain(&["--summary"] as &[&str], false, "total packages:")]
#[case::rich(&["--summary", "--output", "rich"], false, "environment summary")]
#[case::rich_color(&["--summary", "--output", "rich"], true, "\u{1b}[")]
fn renders_summary_tables(#[case] args: &[&str], #[case] color: bool, #[case] expected: &str) {
    let site = render_site();
    let output = super::execute_with(&_pipdeptree::SystemProcessRunner, &site, args, color);

    assert!(text(&output).contains(expected));
}

#[test]
fn renders_empty_summary() {
    let site = PackageSite::new();
    let output = execute(&site, &["--summary"]);

    assert_eq!(
        (
            text(&output).contains("licenses:                 none"),
            text(&output).contains("min requires-python:      n/a"),
        ),
        (true, true)
    );
}

#[test]
fn ignores_invalid_requires_python_in_summaries() {
    let site = PackageSite::new();
    site.write(
        "invalid-1.dist-info",
        "Name: invalid\nVersion: 1\nRequires-Python: invalid\n",
    );
    site.write(
        "valid-1.dist-info",
        "Name: valid\nVersion: 1\nRequires-Python: >3.12\n",
    );
    let output = execute(&site, &["--summary", "--output", "json"]);
    let value: Value = serde_json::from_slice(&output.stdout).unwrap();

    assert_eq!(value["min_requires_python"], "3.12");
}

#[test]
fn renders_resolved_summary() {
    let (_directory, lock) = lock_file(concat!(
        "lock-version = '1.0'\n",
        "[[packages]]\nname = 'root'\nversion = '1'\n",
    ));

    let text_output = super::super::common::execute(&["--summary", "from-lock", path(&lock)]);
    let json_output =
        super::super::common::execute(&["--summary", "--output", "json", "from-lock", path(&lock)]);
    let value: Value = serde_json::from_slice(&json_output.stdout).unwrap();

    assert_eq!(
        (
            text(&text_output).contains("n/a (resolved from index/lock"),
            value.as_object().unwrap().len(),
            value["total_packages"].as_u64(),
        ),
        (true, 5, Some(1))
    );
}
