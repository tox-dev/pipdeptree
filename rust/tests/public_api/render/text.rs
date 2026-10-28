use std::fmt::Write as _;
use std::time::{Duration, Instant};

use super::{execute, lock_file, path, render_site, text};
use rstest::rstest;

#[rstest]
#[case::unicode(&[], "├──")]
#[case::ascii(&["--encoding", "ascii"], "  - ")]
#[case::depth(
    &["--depth", "0", "--all"],
    "child==1\ngraph==1\nleaf==1\nother==1\nroot==1\nunique==1\n"
)]
#[case::reverse(
    &["--reverse", "--depth", "1"],
    concat!(
        "child==1\n├── other==1 [requires: child]\n└── root==1 [requires: child>=2]\n",
        "graph==1\nleaf==1\n└── unique==1 [requires: leaf, extra: feature]\n",
        "missing==?\n└── root==1 [requires: missing]\n"
    )
)]
fn renders_text_modes(#[case] args: &[&str], #[case] expected: &str) {
    let site = render_site();
    let output = execute(&site, args);

    if args.first() == Some(&"--depth") || args.first() == Some(&"--reverse") {
        assert_eq!(text(&output), expected);
    } else {
        assert!(text(&output).contains(expected));
    }
}

#[test]
fn interleaves_missing_reverse_roots_alphabetically() {
    let site = super::PackageSite::new();
    site.write(
        "alpha-1.dist-info",
        "Name: alpha\nVersion: 1\nRequires-Dist: aa-missing\n",
    );
    site.write(
        "beta-1.dist-info",
        "Name: beta\nVersion: 1\nRequires-Dist: aa-missing\n",
    );
    site.write("zz-1.dist-info", "Name: zz\nVersion: 1\n");

    let output = execute(&site, &["--reverse"]);

    assert_eq!(
        text(&output),
        concat!(
            "aa-missing==?\n",
            "├── alpha==1 [requires: aa-missing]\n",
            "└── beta==1 [requires: aa-missing]\n",
            "zz==1\n",
        )
    );
}

#[test]
fn renders_resolved_text_and_rich_color() {
    let (_directory, lock) = lock_file(concat!(
        "lock-version = '1.0'\n",
        "[[packages]]\nname = 'root'\nversion = '1'\n",
        "dependencies = [{ name = 'child' }]\n",
        "[[packages]]\nname = 'child'\nversion = '2'\n",
    ));

    let site = super::PackageSite::new();
    let output = super::execute_with(
        &_pipdeptree::SystemProcessRunner,
        &site,
        &["--output", "rich", "from-lock", path(&lock)],
        true,
    );
    let candidate = anstyle::AnsiColor::Green.on_default().bold();

    assert_eq!(
        (
            text(&output).contains("root"),
            text(&output).contains("candidate:"),
            text(&output).contains(&format!("{candidate}2{candidate:#}")),
        ),
        (true, true, true)
    );
}

#[test]
fn colors_reverse_requirements() {
    let site = render_site();
    let output = super::execute_with(
        &_pipdeptree::SystemProcessRunner,
        &site,
        &["--output", "rich", "--reverse", "--depth", "1"],
        true,
    );
    let constraint = anstyle::AnsiColor::BrightBlue.on_default();

    assert_eq!(
        (
            output.code,
            text(&output).contains("requires:"),
            text(&output).contains(&format!("{constraint}child{constraint:#}")),
        ),
        (0, true, true)
    );
}

#[test]
fn marks_unique_conflicts_and_stops_reverse_cycles() {
    let site = super::PackageSite::new();
    site.write(
        "first-1.dist-info",
        "Name: first\nVersion: 1\nRequires-Dist: second>=2\n",
    );
    site.write(
        "second-1.dist-info",
        "Name: second\nVersion: 1\nRequires-Dist: first\n",
    );

    let rich = execute(
        &site,
        &["--output", "rich", "--computed", "unique-deps-count"],
    );
    let reverse = execute(&site, &["--reverse"]);

    assert_eq!(
        (
            text(&rich).contains("⚠ ⭐ second"),
            text(&reverse).matches("first==1").count(),
        ),
        (true, 2)
    );
}

// Every requirement hub files under the extras it is asked for points back up the path, so
// none of them prints; rebuilding and scanning that list on each of the 27,000 visits to hub
// overruns the budget.
#[rstest]
#[case::text(&[], "required: <")]
#[case::rich(&["--output", "rich"], "required: <")]
#[case::json_tree(&["--output", "json-tree"], "\"required_version\": \"<")]
fn skips_unprinted_requirements_of_a_revisited_package(
    #[case] args: &[&str],
    #[case] dependency: &str,
) {
    let extras = (0..50)
        .map(|number| format!("x{number}"))
        .collect::<Vec<_>>();
    let marker = extras
        .iter()
        .map(|extra| format!("extra == '{extra}'"))
        .collect::<Vec<_>>()
        .join(" or ");
    let site = super::PackageSite::new();
    for (name, requires) in [
        ("r", requirements("a", 30, "")),
        ("a", requirements("b", 30, "")),
        (
            "b",
            requirements(&format!("hub[{}]", extras.join(",")), 30, ""),
        ),
        ("hub", requirements("a", 100, &format!("; {marker}"))),
    ] {
        site.write(
            &format!("{name}-1.dist-info"),
            &format!("Name: {name}\nVersion: 1\n{requires}"),
        );
    }
    let start = Instant::now();

    let output = execute(&site, args);

    assert_eq!(
        (
            text(&output).matches(dependency).count(),
            start.elapsed() < BUDGET
        ),
        (30 + 900 + 27000, true)
    );
}

// The conflict check walks every specifier against every segment of the installed version, and
// the rich tree prints the lib -> ghost edge once per path to lib.
#[test]
fn checks_each_rich_edge_for_conflicts_once() {
    let site = super::PackageSite::new();
    let local = vec!["1"; 2000].join(".");
    site.write(
        "app-1.dist-info",
        &format!("Name: app\nVersion: 1\n{}", requirements("lib", 1000, "")),
    );
    site.write(
        "lib-1.dist-info",
        &format!(
            "Name: lib\nVersion: 1\nRequires-Dist: ghost{}\n",
            (0..2000)
                .map(|number| format!("!=0.{number}"))
                .collect::<Vec<_>>()
                .join(",")
        ),
    );
    site.write(
        "ghost-1.dist-info",
        &format!("Name: ghost\nVersion: 1+{local}\n"),
    );
    let start = Instant::now();

    let output = execute(&site, &["--output", "rich"]);

    assert_eq!(
        (text(&output).lines().count(), start.elapsed() < BUDGET),
        (1 + 1000 + 1000, true)
    );
}

const BUDGET: Duration = Duration::from_secs(10);

fn requirements(name: &str, count: usize, marker: &str) -> String {
    (1..=count).fold(String::new(), |mut lines, number| {
        let _ = writeln!(lines, "Requires-Dist: {name}<{number}{marker}");
        lines
    })
}
