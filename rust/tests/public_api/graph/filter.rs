use super::super::common::{PackageSite, execute, execute_in, stdout};
use super::{collect_tree_names, complex_site, visible_names};
use rstest::rstest;
use serde_json::Value;

#[test]
fn selects_missing_requirements_in_reverse_filters() {
    let site = PackageSite::new();
    site.write(
        "holder-1.dist-info",
        "Name: holder\nVersion: 1\nRequires-Dist: ghost\n",
    );
    site.write("other-1.dist-info", "Name: other\nVersion: 1\n");

    let output = execute_in(&site, &["--reverse", "--packages", "ghost"]);

    assert_eq!(
        (
            output.code,
            stdout(&output).contains("ghost==?"),
            stdout(&output).contains("holder==1"),
            stdout(&output).contains("other"),
        ),
        (0, true, true, false)
    );
}

#[test]
fn keeps_shared_dependencies_of_excluded_packages() {
    let site = PackageSite::new();
    site.write(
        "doomed-1.dist-info",
        "Name: doomed\nVersion: 1\nRequires-Dist: shared\nRequires-Dist: lonely\n",
    );
    site.write(
        "keeper-1.dist-info",
        "Name: keeper\nVersion: 1\nRequires-Dist: shared\n",
    );
    site.write("shared-1.dist-info", "Name: shared\nVersion: 1\n");
    site.write("lonely-1.dist-info", "Name: lonely\nVersion: 1\n");

    let output = execute_in(
        &site,
        &["--exclude", "doomed", "--exclude-dependencies", "--json"],
    );

    assert_eq!(
        (output.code, visible_names(&output), output.stderr.as_str()),
        (0, vec!["keeper".to_string(), "shared".to_string()], "")
    );
}

#[test]
fn keeps_separator_boundaries_in_patterns() {
    let site = PackageSite::new();
    site.write("pytest-1.dist-info", "Name: pytest\nVersion: 1\n");
    site.write("py-demo-1.dist-info", "Name: py.demo\nVersion: 1\n");

    let output = execute_in(&site, &["--packages", "py.*", "--exclude", "x_", "--json"]);

    assert_eq!(
        (output.code, visible_names(&output), output.stderr.as_str()),
        (0, vec!["py.demo".to_string()], "")
    );
}

#[rstest]
#[case::exclude(&["--exclude", "root", "--json"], &["child", "cycle-a", "cycle-b", "leaf", "nested", "plain", "top"])]
#[case::exclude_dependencies(
    &["--exclude", "root", "--exclude-dependencies", "--json"],
    &["cycle-a", "cycle-b", "top"]
)]
#[case::include(
    &["--packages", "root", "--json"],
    &["child", "leaf", "nested", "plain", "root"]
)]
#[case::reverse(
    &["--packages", "child", "--reverse", "--json"],
    &["child", "root", "top", "missing"]
)]
#[case::reverse_exclude(
    &["--exclude", "root", "--exclude-dependencies", "--reverse", "--json"],
    &["child", "cycle-a", "cycle-b", "leaf", "nested", "plain"]
)]
fn filters_packages(complex_site: PackageSite, #[case] args: &[&str], #[case] expected: &[&str]) {
    let output = execute_in(&complex_site, args);
    let expected = expected.iter().map(ToString::to_string).collect::<Vec<_>>();

    assert_eq!(
        (output.code, visible_names(&output), output.stderr.as_str()),
        (0, expected, "")
    );
}

#[rstest]
fn allows_wildcard_include_with_specific_exclude(complex_site: PackageSite) {
    let output = execute_in(
        &complex_site,
        &["--packages", "*", "--exclude", "root", "--json"],
    );

    assert_eq!(
        (
            output.code,
            visible_names(&output).contains(&"root".to_string()),
            output.stderr.as_str(),
        ),
        (0, false, "")
    );
}

#[rstest]
fn omits_hidden_reverse_parents(complex_site: PackageSite) {
    let output = execute_in(
        &complex_site,
        &[
            "--packages",
            "child",
            "--exclude",
            "root",
            "--reverse",
            "--json-tree",
        ],
    );
    let value: Value = serde_json::from_slice(&output.stdout).unwrap();
    let mut names = Vec::new();
    collect_tree_names(&value, &mut names);
    names.sort_unstable();

    assert_eq!(
        (output.code, names, output.stderr.as_str()),
        (0, vec!["child".to_string(), "top".to_string()], "")
    );
}

#[rstest]
fn rejects_literal_filter_overlap(complex_site: PackageSite) {
    let output = execute_in(&complex_site, &["--packages", "root", "--exclude", "root"]);

    assert_eq!(
        (
            output.code,
            output.stdout.is_empty(),
            output.stderr.contains("--packages and --exclude"),
        ),
        (1, true, true)
    );
}

#[rstest]
#[case::missing("absent", "suppress", 0, true)]
#[case::partial("root,absent", "suppress", 0, true)]
#[case::invalid_glob("a**b", "suppress", 0, true)]
#[case::silence("absent", "silence", 0, false)]
#[case::fail("absent", "fail", 1, true)]
fn reports_unmatched_filters(
    complex_site: PackageSite,
    #[case] packages: &str,
    #[case] warning: &str,
    #[case] code: i32,
    #[case] reported: bool,
) {
    let output = execute(&[
        "--path",
        complex_site.path().to_str().unwrap(),
        "--packages",
        packages,
        "--warn",
        warning,
    ]);

    assert_eq!(
        (
            output.code,
            output.stdout.is_empty(),
            output.stderr.contains("No packages matched"),
        ),
        (code, true, reported)
    );
}

#[rstest]
#[case::json(&["--json"])]
#[case::json_tree(&["--json-tree"])]
#[case::mermaid(&["--mermaid"])]
#[case::graphviz(&["--graph-output", "dot"])]
fn silences_warnings_for_non_text_output(complex_site: PackageSite, #[case] format: &[&str]) {
    let output = execute(
        &[
            "--path",
            complex_site.path().to_str().unwrap(),
            "--warn",
            "fail",
            "--packages",
            "root",
        ]
        .into_iter()
        .chain(format.iter().copied())
        .collect::<Vec<_>>(),
    );

    assert_eq!(
        (
            output.code,
            output.stdout.is_empty(),
            output.stderr.as_str()
        ),
        (0, false, "")
    );
}

#[test]
fn filters_diamond_dependencies_once() {
    let site = PackageSite::new();
    site.write(
        "root-1.dist-info",
        "Name: root\nVersion: 1\nRequires-Dist: left\nRequires-Dist: right\n",
    );
    site.write(
        "left-1.dist-info",
        "Name: left\nVersion: 1\nRequires-Dist: leaf\n",
    );
    site.write(
        "right-1.dist-info",
        "Name: right\nVersion: 1\nRequires-Dist: leaf\n",
    );
    site.write("leaf-1.dist-info", "Name: leaf\nVersion: 1\n");

    let output = execute_in(&site, &["--packages", "root", "--json"]);

    assert_eq!(
        (output.code, visible_names(&output), output.stderr.as_str()),
        (
            0,
            ["leaf", "left", "right", "root"]
                .map(str::to_string)
                .to_vec(),
            "",
        )
    );
}
