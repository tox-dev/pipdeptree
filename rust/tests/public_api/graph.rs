use rstest::{fixture, rstest};
use serde_json::Value;

use super::common::{PackageSite, execute, execute_in, execute_with_runner, stdout, with_python};

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
    &["child", "nested", "plain", "root"]
)]
#[case::normalized_extra(
    &["--packages", "root[FEATURE]", "--extras", "none", "--json"],
    &["child", "nested", "plain", "root"]
)]
#[case::multiple(
    &["--packages", "root[feature,broken]", "--extras", "none", "--json"],
    &["child", "nested", "plain", "root"]
)]
#[case::wildcard(
    &["--packages", "to_*", "--extras", "explicit", "--json"],
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
    &["child", "root", "top"]
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
#[case::silence("silence", 0, false)]
#[case::suppress("suppress", 0, true)]
#[case::fail("fail", 1, true)]
fn reports_graph_warnings(
    complex_site: PackageSite,
    #[case] warning: &str,
    #[case] code: i32,
    #[case] reported: bool,
) {
    let output = execute(&[
        "--path",
        complex_site.path().to_str().unwrap(),
        "--warn",
        warning,
        "--packages",
        "root",
        "--depth",
        "0",
    ]);

    assert_eq!(
        (
            output.code,
            stdout(&output),
            output.stderr.contains("Invalid requirement found"),
            output.stderr.contains("installed: ?"),
            output.stderr.contains("installed: 1"),
        ),
        (code, "root==1\n", reported, reported, reported)
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
fn colors_warning_headings(complex_site: PackageSite) {
    let output = with_python(|python| {
        execute_with_runner(
            &_pipdeptree::SystemProcessRunner,
            python,
            &[
                "--path",
                complex_site.path().to_str().unwrap(),
                "--packages",
                "root",
                "--depth",
                "0",
            ],
            true,
        )
    });
    let warning = anstyle::AnsiColor::Yellow.on_default().bold();

    assert_eq!(
        (
            output.code,
            output
                .stderr
                .contains(&format!("{warning}Warning:{warning:#}")),
        ),
        (0, true)
    );
}

#[rstest]
fn reports_cycles_in_summary(complex_site: PackageSite) {
    let output = execute_in(&complex_site, &["--summary", "--output", "json"]);
    let summary: Value = serde_json::from_slice(&output.stdout).unwrap();

    assert_eq!(
        (
            output.code,
            summary["cyclic_dependencies"].as_u64(),
            summary["missing_dependencies"].as_u64(),
            summary["conflicting_dependencies"]["packages"].as_u64(),
            summary["conflicting_dependencies"]["edges"].as_u64(),
            output.stderr.as_str(),
        ),
        (0, Some(2), Some(1), Some(1), Some(2), "")
    );
}

#[rstest]
fn marks_rich_dependency_status(complex_site: PackageSite) {
    let output = execute_in(
        &complex_site,
        &["--packages", "root", "--output", "rich", "--depth", "1"],
    );

    assert_eq!(
        (
            output.code,
            stdout(&output).contains("⚠ child required: >=2 installed: 1"),
            stdout(&output).contains("✗ missing required: Any installed: ?"),
            stdout(&output).contains("✓ plain required: Any installed: 1"),
            output.stderr.as_str(),
        ),
        (0, true, true, true, "")
    );
}

#[test]
fn renders_cycle_roots() {
    let site = PackageSite::new();
    site.write(
        "cycle-a-1.dist-info",
        "Name: cycle-a\nVersion: 1\nRequires-Dist: cycle-b\n",
    );
    site.write(
        "cycle-b-1.dist-info",
        "Name: cycle-b\nVersion: 1\nRequires-Dist: cycle-a\n",
    );

    let output = execute_in(&site, &["--packages", "cycle-a"]);

    assert_eq!(
        (
            output.code,
            stdout(&output).starts_with("cycle-a==1\n"),
            stdout(&output).contains("cycle-b==1\n"),
            output.stderr.as_str(),
        ),
        (0, true, true, "")
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

#[derive(Clone, Copy, Debug)]
enum ActiveExtraGraph {
    Cyclic,
    Convergent,
    Independent,
    EmptySubExtra,
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

#[fixture]
fn complex_site() -> PackageSite {
    let site = PackageSite::new();
    site.write(
        "top-1.dist-info",
        "Name: top\nVersion: 1\nRequires-Dist: root[feature]\n",
    );
    site.write(
        "root-1.dist-info",
        concat!(
            "Name: root\n",
            "Version: 1\n",
            "Requires-Dist: child>=2\n",
            "Requires-Dist: child>=3\n",
            "Requires-Dist: plain\n",
            "Requires-Dist: plain\n",
            "Requires-Dist: missing\n",
            "Requires-Dist: nested[leaf]; extra == 'feature'\n",
            "Requires-Dist: absent; extra == 'broken'\n",
            "Requires-Dist: ignored; sys_platform == 'never'\n",
            "Requires-Dist: not a requirement !!!\n",
            "Provides-Extra: feature\n",
            "Provides-Extra: broken\n",
            "Provides-Extra: bad extra\n",
        ),
    );
    site.write("child-1.dist-info", "Name: child\nVersion: 1\n");
    site.write("plain-1.dist-info", "Name: plain\nVersion: 1\n");
    site.write(
        "nested-1.dist-info",
        concat!(
            "Name: nested\n",
            "Version: 1\n",
            "Requires-Dist: leaf; extra == 'leaf'\n",
            "Provides-Extra: leaf\n",
        ),
    );
    site.write("leaf-1.dist-info", "Name: leaf\nVersion: 1\n");
    site.write(
        "cycle-a-1.dist-info",
        "Name: cycle-a\nVersion: 1\nRequires-Dist: cycle-b\n",
    );
    site.write(
        "cycle-b-1.dist-info",
        "Name: cycle-b\nVersion: 1\nRequires-Dist: cycle-a\n",
    );
    site
}

fn active_extra_site(graph: ActiveExtraGraph) -> PackageSite {
    let site = PackageSite::new();
    let packages: &[(&str, &str)] = match graph {
        ActiveExtraGraph::Cyclic => &[
            (
                "a-1.dist-info",
                "Name: a\nVersion: 1\nRequires-Dist: b[x]\n",
            ),
            (
                "b-1.dist-info",
                "Name: b\nVersion: 1\nRequires-Dist: c[y]; extra == 'x'\nProvides-Extra: x\n",
            ),
            (
                "c-1.dist-info",
                "Name: c\nVersion: 1\nRequires-Dist: b[x]; extra == 'y'\nProvides-Extra: y\n",
            ),
        ],
        ActiveExtraGraph::Convergent => &[
            (
                "a-1.dist-info",
                concat!(
                    "Name: a\nVersion: 1\n",
                    "Requires-Dist: b[y]; extra == 'x'\n",
                    "Requires-Dist: c[y]; extra == 'x'\n",
                    "Provides-Extra: x\n",
                ),
            ),
            (
                "b-1.dist-info",
                "Name: b\nVersion: 1\nRequires-Dist: a[x]; extra == 'y'\nProvides-Extra: y\n",
            ),
            (
                "c-1.dist-info",
                "Name: c\nVersion: 1\nRequires-Dist: b[y]; extra == 'y'\nProvides-Extra: y\n",
            ),
        ],
        ActiveExtraGraph::Independent => &[
            (
                "alpha-1.dist-info",
                "Name: alpha\nVersion: 1\nRequires-Dist: shared; extra == 'a'\nProvides-Extra: a\n",
            ),
            (
                "beta-1.dist-info",
                "Name: beta\nVersion: 1\nRequires-Dist: shared; extra == 'b'\nProvides-Extra: b\n",
            ),
            ("shared-1.dist-info", "Name: shared\nVersion: 1\n"),
        ],
        ActiveExtraGraph::EmptySubExtra => &[
            (
                "parent-1.dist-info",
                "Name: parent\nVersion: 1\nRequires-Dist: child[empty]; extra == 'feature'\nProvides-Extra: feature\n",
            ),
            (
                "child-1.dist-info",
                "Name: child\nVersion: 1\nProvides-Extra: empty\n",
            ),
        ],
    };
    for (path, metadata) in packages {
        site.write(path, metadata);
    }
    site
}

fn scoped_extra_site() -> PackageSite {
    let site = PackageSite::new();
    site.write(
        "selenium-1.dist-info",
        "Name: selenium\nVersion: 1\nRequires-Dist: urllib3[socks]\n",
    );
    site.write(
        "requests-1.dist-info",
        "Name: requests\nVersion: 1\nRequires-Dist: urllib3\n",
    );
    site.write(
        "urllib3-1.dist-info",
        concat!(
            "Name: urllib3\n",
            "Version: 1\n",
            "Requires-Dist: pysocks; extra == 'socks'\n",
            "Provides-Extra: socks\n",
        ),
    );
    site.write("pysocks-1.dist-info", "Name: pysocks\nVersion: 1\n");
    site
}

fn branch_contains(value: &Value, root: &str, parent: &str, child: &str) -> bool {
    value
        .as_array()
        .unwrap()
        .iter()
        .find(|entry| entry["package_name"] == root)
        .unwrap()["dependencies"]
        .as_array()
        .unwrap()
        .iter()
        .find(|entry| entry["package_name"] == parent)
        .unwrap()["dependencies"]
        .as_array()
        .unwrap()
        .iter()
        .any(|entry| entry["package_name"] == child)
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

fn extra_chain_site() -> PackageSite {
    let site = PackageSite::new();
    for parent in ["top-a", "top-z"] {
        site.write(
            &format!("{parent}-1.dist-info"),
            &format!("Name: {parent}\nVersion: 1\nRequires-Dist: root[feature]\n"),
        );
    }
    site.write(
        "root-1.dist-info",
        concat!(
            "Name: root\n",
            "Version: 1\n",
            "Requires-Dist: nested[leaf]; extra == 'feature'\n",
            "Requires-Dist: missing; extra == 'feature'\n",
            "Provides-Extra: feature\n",
        ),
    );
    site.write(
        "nested-1.dist-info",
        concat!(
            "Name: nested\n",
            "Version: 1\n",
            "Requires-Dist: leaf[next]; extra == 'leaf'\n",
            "Provides-Extra: leaf\n",
        ),
    );
    site.write(
        "leaf-1.dist-info",
        concat!(
            "Name: leaf\n",
            "Version: 1\n",
            "Requires-Dist: final; extra == 'next'\n",
            "Provides-Extra: next\n",
        ),
    );
    site.write("final-1.dist-info", "Name: final\nVersion: 1\n");
    site
}

fn collect_tree_names(value: &Value, names: &mut Vec<String>) {
    if let Some(package) = value.get("package_name").and_then(Value::as_str) {
        names.push(package.to_string());
    }
    for dependency in value
        .get("dependencies")
        .and_then(Value::as_array)
        .into_iter()
        .flatten()
    {
        collect_tree_names(dependency, names);
    }
    if let Some(roots) = value.as_array() {
        for root in roots {
            collect_tree_names(root, names);
        }
    }
}
