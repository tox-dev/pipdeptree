use std::time::{Duration, Instant};

use _pipdeptree::SystemProcessRunner;

use super::{
    crossed_cycle_site, execute, layered_site, lock_file, path, render_site, text, write_requiring,
};
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
fn marks_unique_conflicts_and_reverse_cycles() {
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
        (text(&rich).contains("⚠ ⭐ second"), text(&reverse),),
        (
            true,
            concat!(
                "first==1\n",
                "└── second==1 [requires: first]\n",
                "    └── first==1 [requires: second>=2] (*)\n",
                "second==1\n",
                "└── first==1 [requires: second>=2]\n",
                "    └── second==1 [requires: first] (*)\n",
            )
        )
    );
}

#[rstest]
#[case::text(&[] as &[&str])]
#[case::rich(&["--output", "rich"])]
#[case::freeze(&["--freeze"])]
#[case::reverse(&["--reverse"])]
#[case::reverse_freeze(&["--reverse", "--freeze"])]
fn prints_each_edge_of_a_root_once(#[case] args: &[&str]) {
    let site = layered_site(20);
    let output = execute(&site, args);

    assert_eq!(text(&output).lines().count(), 1 + 20 * 19 / 2);
}

#[rstest]
#[case::text(
    &[] as &[&str],
    concat!(
        "a==1\n",
        "├── x [required: Any, installed: 1]\n",
        "│   └── y [required: Any, installed: 1]\n",
        "│       ├── w [required: Any, installed: 1]\n",
        "│       └── x [required: Any, installed: 1] (*)\n",
        "└── y [required: Any, installed: 1] (*)\n",
    )
)]
#[case::freeze(
    &["--freeze"],
    "a==1\n  x==1\n    y==1\n      w==1\n      x==1\n  y==1\n"
)]
#[case::reverse(
    &["--reverse", "--packages", "w"],
    concat!(
        "w==1\n",
        "└── y==1 [requires: w]\n",
        "    ├── a==1 [requires: y]\n",
        "    └── x==1 [requires: y]\n",
        "        ├── a==1 [requires: x]\n",
        "        └── y==1 [requires: x] (*)\n",
    )
)]
fn keeps_every_edge_of_a_cycle(#[case] args: &[&str], #[case] expected: &str) {
    let site = crossed_cycle_site();
    let output = execute(&site, args);

    assert_eq!(text(&output), expected);
}

#[test]
fn expands_a_repeated_subtree_again_where_depth_leaves_more_levels() {
    let site = super::PackageSite::new();
    write_requiring(&site, "a", &["b", "c"]);
    write_requiring(&site, "b", &["c"]);
    write_requiring(&site, "c", &["d"]);
    write_requiring(&site, "d", &["e"]);
    write_requiring(&site, "e", &[] as &[&str]);

    let output = execute(&site, &["--depth", "3", "--encoding", "ascii"]);

    assert_eq!(
        text(&output),
        concat!(
            "a==1\n",
            "  - b [required: Any, installed: 1]\n",
            "    - c [required: Any, installed: 1]\n",
            "      - d [required: Any, installed: 1]\n",
            "  - c [required: Any, installed: 1]\n",
            "    - d [required: Any, installed: 1]\n",
            "      - e [required: Any, installed: 1]\n",
        )
    );
}

// A package appears on a line for every edge that reaches it, so building its metadata suffix
// on every line costs the edges times the stored value's length, blanks included.
#[rstest]
#[case::forward(&[])]
#[case::reverse(&["--reverse"])]
#[case::rich(&["--output", "rich"])]
fn builds_padded_metadata_suffix_once_per_package(#[case] args: &[&str]) {
    let license = format!("License-Expression: a{}b\n", " ".repeat(500_000));
    let requires = (0..1000)
        .map(|number| format!("Requires-Dist: leaf!={number}\n"))
        .collect::<Vec<_>>()
        .concat();
    let site = super::PackageSite::new();
    site.write(
        "app-1.dist-info",
        &format!("Name: app\nVersion: 1\n{license}{requires}"),
    );
    site.write(
        "leaf-1.dist-info",
        &format!("Name: leaf\nVersion: 1\n{license}"),
    );

    let args = [
        &["--path", super::path(site.path()), "--metadata", "license"],
        args,
    ]
    .concat();
    let (output, elapsed) = super::with_python(|python| {
        let start = Instant::now();
        let output = super::execute_with_runner(&SystemProcessRunner, python, &args, false);
        (output, start.elapsed())
    });

    assert_eq!(
        (
            text(&output).matches(" (a b License)").count(),
            elapsed < Duration::from_secs(3),
        ),
        (1 + 1000, true),
        "took {elapsed:?}"
    );
}
