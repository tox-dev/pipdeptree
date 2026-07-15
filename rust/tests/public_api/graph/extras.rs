use super::super::common::{PackageSite, execute, execute_in, stdout};
use super::{
    ActiveExtraGraph, active_extra_site, branch_contains, collect_tree_names, complex_site,
    extra_chain_site, scoped_extra_site, visible_names,
};
use rstest::rstest;
use serde_json::Value;

#[rstest]
#[case::explicit(
    &["--packages", "top", "--extras", "explicit", "--json"],
    &["child", "leaf", "nested", "plain", "root", "top"]
)]
#[case::none(
    &["--packages", "top", "--extras", "none", "--json"],
    &["child", "plain", "root", "top"]
)]
#[case::active(
    &["--packages", "root", "--extras", "active", "--json"],
    &["child", "leaf", "nested", "plain", "root"]
)]
#[case::command_line(
    &["--packages", "root[feature]", "--extras", "none", "--json"],
    &["child", "leaf", "nested", "plain", "root"]
)]
#[case::normalized_extra(
    &["--packages", "root[FEATURE]", "--extras", "none", "--json"],
    &["child", "leaf", "nested", "plain", "root"]
)]
#[case::multiple(
    &["--packages", "root[feature,broken]", "--extras", "none", "--json"],
    &["child", "leaf", "nested", "plain", "root"]
)]
#[case::wildcard(
    &["--packages", "to*", "--extras", "explicit", "--json"],
    &["child", "leaf", "nested", "plain", "root", "top"]
)]
#[case::unknown_extra(
    &["--packages", "root[unknown]", "--extras", "none", "--json"],
    &["child", "plain", "root"]
)]
#[case::empty_extra(
    &["--packages", "root[],,", "--extras", "none", "--json"],
    &["child", "plain", "root"]
)]
fn selects_extras(complex_site: PackageSite, #[case] args: &[&str], #[case] expected: &[&str]) {
    let output = execute_in(&complex_site, args);
    let expected = expected.iter().map(ToString::to_string).collect::<Vec<_>>();

    assert_eq!(
        (output.code, visible_names(&output), output.stderr.as_str()),
        (0, expected, "")
    );
}

#[test]
fn activates_extras_without_provides_extra() {
    let site = PackageSite::new();
    site.write(
        "root-1.dist-info",
        "Name: root\nVersion: 1\nRequires-Dist: optional; extra == 'test'\n",
    );
    site.write("optional-1.dist-info", "Name: optional\nVersion: 1\n");

    let output = execute_in(&site, &["--packages", "root[test]", "--json"]);

    assert_eq!(
        (output.code, visible_names(&output)),
        (0, vec!["optional".to_string(), "root".to_string()])
    );
}

#[test]
fn rejects_unbalanced_package_extras() {
    let site = PackageSite::new();
    site.write("demo-1.dist-info", "Name: demo\nVersion: 1\n");

    let output = execute(&[
        "--path",
        site.path().to_str().unwrap(),
        "--packages",
        "demo[socks",
    ]);

    assert_eq!(
        (
            output.code,
            output.stdout.is_empty(),
            output.stderr.contains("No packages matched")
        ),
        (0, true, true)
    );
}

#[test]
fn normalizes_extra_separators() {
    let site = PackageSite::new();
    site.write(
        "root-1.dist-info",
        concat!(
            "Name: root\n",
            "Version: 1\n",
            "Requires-Dist: optional; extra == 'dev-tools'\n",
            "Provides-Extra: dev-tools\n",
        ),
    );
    site.write("optional-1.dist-info", "Name: optional\nVersion: 1\n");

    let output = execute_in(
        &site,
        &[
            "--packages",
            "root[dev_tools]",
            "--extras",
            "none",
            "--json",
        ],
    );

    assert_eq!(
        (output.code, visible_names(&output), output.stderr.as_str()),
        (0, vec!["optional".to_string(), "root".to_string()], "")
    );
}

#[test]
fn keeps_mandatory_and_extra_edges_for_the_same_package() {
    let site = PackageSite::new();
    site.write(
        "root-1.dist-info",
        concat!(
            "Name: root\n",
            "Version: 1\n",
            "Requires-Dist: child\n",
            "Requires-Dist: child; extra == 'feature'\n",
            "Provides-Extra: feature\n",
        ),
    );
    site.write("child-1.dist-info", "Name: child\nVersion: 1\n");

    let output = execute_in(
        &site,
        &[
            "--packages",
            "root[feature]",
            "--extras",
            "none",
            "--output",
            "rich",
        ],
    );

    assert_eq!(
        (output.code, stdout(&output).matches("child").count()),
        (0, 2)
    );
}

#[rstest]
#[case::requested(
    &["--packages", "final", "--reverse", "--json-tree"],
    &["final", "leaf", "nested", "root", "top-a", "top-z"]
)]
#[case::global(
    &["--packages", "final,nested[leaf]", "--reverse", "--json-tree"],
    &["final", "leaf", "nested", "root", "top-a", "top-z"]
)]
fn follows_reverse_extra_chains(#[case] args: &[&str], #[case] expected: &[&str]) {
    let site = extra_chain_site();
    let output = execute_in(&site, args);
    let value: Value = serde_json::from_slice(&output.stdout).unwrap();
    let mut names = Vec::new();
    collect_tree_names(&value, &mut names);
    names.sort_unstable();
    names.dedup();

    assert_eq!(
        (output.code, names, output.stderr.as_str()),
        (
            0,
            expected.iter().map(ToString::to_string).collect::<Vec<_>>(),
            "",
        )
    );
}

#[test]
fn rejects_active_extra_with_unknown_nested_extra() {
    let site = PackageSite::new();
    site.write(
        "root-1.dist-info",
        concat!(
            "Name: root\n",
            "Version: 1\n",
            "Requires-Dist: target[unknown]; extra == 'broken'\n",
            "Provides-Extra: broken\n",
        ),
    );
    site.write("target-1.dist-info", "Name: target\nVersion: 1\n");

    let output = execute_in(
        &site,
        &["--packages", "root", "--extras", "active", "--json"],
    );

    assert_eq!(
        (output.code, visible_names(&output), output.stderr.as_str()),
        (0, vec!["root".to_string()], "")
    );
}

#[test]
fn resolves_active_extras_beyond_python_recursion_depth() {
    let site = PackageSite::new();
    for index in 0..1_500 {
        site.write(
            &format!("l{index}-1.dist-info"),
            &format!(
                "Name: l{index}\nVersion: 1\nRequires-Dist: l{}[x]; extra == 'x'\nProvides-Extra: x\n",
                index + 1
            ),
        );
    }
    site.write(
        "l1500-1.dist-info",
        "Name: l1500\nVersion: 1\nRequires-Dist: leaf; extra == 'x'\nProvides-Extra: x\n",
    );
    site.write("leaf-1.dist-info", "Name: leaf\nVersion: 1\n");

    let output = execute_in(&site, &["--packages", "l0", "--extras", "active", "--json"]);
    let value: Value = serde_json::from_slice(&output.stdout).unwrap();
    let root = value
        .as_array()
        .unwrap()
        .iter()
        .find(|entry| entry["package"]["package_name"] == "l0")
        .unwrap();

    assert_eq!(
        (
            output.code,
            &root["dependencies"][0]["package_name"],
            output.stderr.as_str(),
        ),
        (0, &Value::String("l1".to_string()), "")
    );
}

#[rstest]
#[case::cyclic(ActiveExtraGraph::Cyclic, "a", &["a", "b", "c"])]
#[case::convergent(ActiveExtraGraph::Convergent, "a", &["a", "b", "c"])]
#[case::independent(
    ActiveExtraGraph::Independent,
    "alpha,beta",
    &["alpha", "beta", "shared"]
)]
#[case::empty_sub_extra(ActiveExtraGraph::EmptySubExtra, "parent", &["parent"])]
fn resolves_active_extra_graphs(
    #[case] graph: ActiveExtraGraph,
    #[case] packages: &str,
    #[case] expected: &[&str],
) {
    let site = active_extra_site(graph);
    let output = execute_in(
        &site,
        &["--packages", packages, "--extras", "active", "--json"],
    );

    assert_eq!(
        (output.code, visible_names(&output), output.stderr.as_str()),
        (
            0,
            expected.iter().map(ToString::to_string).collect::<Vec<_>>(),
            "",
        )
    );
}

#[test]
fn preserves_unresolved_extra_requirements() {
    let site = PackageSite::new();
    site.write(
        "parent-1.dist-info",
        "Name: parent\nVersion: 1\nRequires-Dist: nonexistent[feature]\n",
    );

    let output = execute_in(
        &site,
        &["--packages", "parent", "--extras", "active", "--json"],
    );
    let value: Value = serde_json::from_slice(&output.stdout).unwrap();

    assert_eq!(
        (
            output.code,
            &value[0]["dependencies"][0]["package_name"],
            &value[0]["dependencies"][0]["installed_version"],
            output.stderr.as_str(),
        ),
        (
            0,
            &Value::String("nonexistent".to_string()),
            &Value::String("?".to_string()),
            ""
        )
    );
}

#[test]
fn deduplicates_active_extra_dependencies() {
    let site = PackageSite::new();
    site.write(
        "parent-1.dist-info",
        "Name: parent\nVersion: 1\nRequires-Dist: child[feature]\n",
    );
    site.write(
        "child-1.dist-info",
        concat!(
            "Name: child\n",
            "Version: 1\n",
            "Requires-Dist: leaf; extra == 'feature'\n",
            "Requires-Dist: leaf; extra == 'feature'\n",
            "Provides-Extra: feature\n",
        ),
    );
    site.write("leaf-1.dist-info", "Name: leaf\nVersion: 1\n");

    let output = execute_in(
        &site,
        &["--packages", "parent", "--extras", "active", "--json"],
    );
    let value: Value = serde_json::from_slice(&output.stdout).unwrap();
    let child = value
        .as_array()
        .unwrap()
        .iter()
        .find(|entry| entry["package"]["package_name"] == "child")
        .unwrap();
    let leaf_count = child["dependencies"]
        .as_array()
        .unwrap()
        .iter()
        .filter(|entry| entry["package_name"] == "leaf")
        .count();

    assert_eq!(
        (output.code, leaf_count, output.stderr.as_str()),
        (0, 1, "")
    );
}

#[rstest]
#[case::explicit("explicit", false)]
#[case::active("active", true)]
fn scopes_extras_to_requesting_edges(#[case] extras: &str, #[case] requests_socks: bool) {
    let site = scoped_extra_site();
    let output = execute_in(&site, &["--extras", extras, "--json-tree"]);
    let value: Value = serde_json::from_slice(&output.stdout).unwrap();

    assert_eq!(
        (
            output.code,
            branch_contains(&value, "selenium", "urllib3", "pysocks"),
            branch_contains(&value, "requests", "urllib3", "pysocks"),
            output.stderr.as_str(),
        ),
        (0, true, requests_socks, "")
    );
}

#[test]
fn reverses_only_requesting_extra_edges() {
    let site = scoped_extra_site();
    let output = execute_in(
        &site,
        &[
            "--packages",
            "pysocks",
            "--extras",
            "explicit",
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
        (
            0,
            ["pysocks", "selenium", "urllib3"]
                .map(str::to_string)
                .to_vec(),
            "",
        )
    );
}
