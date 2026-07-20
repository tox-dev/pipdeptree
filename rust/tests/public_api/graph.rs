use rstest::{fixture, rstest};
use serde_json::Value;

use super::common::{PackageSite, execute, execute_in, execute_with_runner, stdout, with_python};

mod extras;
mod filter;
mod version;

#[test]
fn names_the_distribution_with_an_invalid_requirement() {
    let site = PackageSite::new();
    site.write(
        "broken-1.dist-info",
        "Name: broken\nVersion: 1\nRequires-Dist: not a requirement !!!\n",
    );

    let output = execute(&["--path", site.path().to_str().unwrap()]);

    assert!(
        output
            .stderr
            .contains("Invalid requirement found in broken: not a requirement !!!"),
        "unexpected warning: {}",
        output.stderr
    );
}

#[test]
fn judges_unique_dependencies_on_the_full_environment() {
    let site = PackageSite::new();
    site.write(
        "foo-1.dist-info",
        "Name: foo\nVersion: 1\nRequires-Dist: shared\n",
    );
    site.write(
        "boto-1.dist-info",
        "Name: boto\nVersion: 1\nRequires-Dist: shared\n",
    );
    site.write("shared-1.dist-info", "Name: shared\nVersion: 1\n");

    let output = execute_in(
        &site,
        &[
            "--packages",
            "foo",
            "--computed",
            "unique-deps-count",
            "--json",
        ],
    );

    assert_eq!(
        (
            output.code,
            stdout(&output).contains("\"unique_deps_count\": 0"),
            stdout(&output).contains("\"unique_deps_count\": 1"),
        ),
        (0, true, false)
    );
}

#[test]
fn reports_cycle_chains() {
    let site = PackageSite::new();
    site.write(
        "aa-1.dist-info",
        "Name: aa\nVersion: 1\nRequires-Dist: bb\n",
    );
    site.write(
        "bb-1.dist-info",
        "Name: bb\nVersion: 1\nRequires-Dist: cc\nRequires-Dist: dd\n",
    );
    site.write(
        "cc-1.dist-info",
        "Name: cc\nVersion: 1\nRequires-Dist: bb\n",
    );
    site.write(
        "dd-1.dist-info",
        "Name: dd\nVersion: 1\nRequires-Dist: aa\n",
    );

    let output = execute(&["--path", site.path().to_str().unwrap()]);

    assert_eq!(
        (
            output.code,
            output
                .stderr
                .contains("Cyclic dependencies found:\n  aa => bb => dd => aa"),
        ),
        (0, true)
    );
}

#[test]
fn keeps_duplicate_requirement_edges() {
    let site = PackageSite::new();
    site.write(
        "root-1.dist-info",
        "Name: root\nVersion: 1\nRequires-Dist: child==0.5\nRequires-Dist: child>=2\n",
    );
    site.write("child-1.dist-info", "Name: child\nVersion: 1\n");

    let output = execute(&["--path", site.path().to_str().unwrap(), "--warn", "fail"]);

    assert_eq!(
        (
            output.code,
            stdout(&output).contains("child [required: ==0.5, installed: 1]"),
            stdout(&output).contains("child [required: >=2, installed: 1]"),
        ),
        (1, true, true)
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
        (0, Some(2), Some(1), Some(1), Some(3), "")
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

#[derive(Clone, Copy, Debug)]
pub(super) enum ActiveExtraGraph {
    Cyclic,
    Convergent,
    Independent,
    EmptySubExtra,
}

#[fixture]
pub(super) fn complex_site() -> PackageSite {
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

pub(super) fn active_extra_site(graph: ActiveExtraGraph) -> PackageSite {
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

pub(super) fn scoped_extra_site() -> PackageSite {
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

pub(super) fn branch_contains(value: &Value, root: &str, parent: &str, child: &str) -> bool {
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

pub(super) fn visible_names(output: &_pipdeptree::Execution) -> Vec<String> {
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

pub(super) fn extra_chain_site() -> PackageSite {
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

pub(super) fn collect_tree_names(value: &Value, names: &mut Vec<String>) {
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
