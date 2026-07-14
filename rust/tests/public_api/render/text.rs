use rstest::rstest;

use super::{execute, lock_file, path, render_site, text};

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
        "graph==1\nleaf==1\n└── unique==1 [requires: leaf, extra: feature]\n"
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
fn renders_rich_ascii_for_non_unicode_encodings() {
    let site = render_site();
    let output = execute(
        &site,
        &[
            "--output",
            "rich",
            "--encoding",
            "ascii",
            "--computed",
            "unique-deps-count",
        ],
    );
    let rendered = text(&output);

    assert_eq!(
        (
            rendered.is_ascii(),
            rendered.contains("+-- "),
            rendered.contains("`-- "),
            rendered.contains("! child"),
            rendered.contains("x missing"),
            rendered.contains("v * unique"),
        ),
        (true, true, true, true, true, true)
    );
}

#[test]
fn renders_freeze_forward_and_reverse() {
    let site = render_site();

    let forward = execute(&site, &["--freeze", "--depth", "1"]);
    let reverse = execute(&site, &["--freeze", "--reverse", "--depth", "1"]);

    assert_eq!(
        (text(&forward), text(&reverse)),
        (
            concat!(
                "graph==1\n",
                "other==1\n",
                "  child==1\n",
                "root==1\n",
                "  child==1\n",
                "  missing\n",
                "  unique==1\n",
            ),
            concat!(
                "child==1\n",
                "  other==1\n",
                "  root==1\n",
                "graph==1\n",
                "leaf==1\n",
                "  unique==1\n",
            ),
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
fn renders_rich_color_and_computed_fields() {
    let site = render_site();
    site.write(
        "exact-1.dist-info",
        "Name: exact\nVersion: 1\nRequires-Dist: child==1\n",
    );
    let output = super::execute_with(
        &_pipdeptree::SystemProcessRunner,
        &site,
        &[
            "--output",
            "rich",
            "--metadata",
            "license",
            "--computed",
            "size,size-raw,unique-deps-count,unique-deps-names,unique-deps-size",
        ],
        true,
    );

    let name_style = anstyle::AnsiColor::Cyan.on_default().bold();
    let version_style = anstyle::AnsiColor::Green.on_default().bold();
    let constraint_style = anstyle::AnsiColor::BrightBlue.on_default();
    let label_style = anstyle::Style::new().dimmed();
    let conflict_style = anstyle::AnsiColor::Yellow.on_default().bold();
    let error_style = anstyle::AnsiColor::Red.on_default().bold();
    let extra_style = anstyle::AnsiColor::Magenta.on_default();
    assert_eq!(
        (
            text(&output).contains("\u{1b}["),
            text(&output).contains(&format!("{name_style}child{name_style:#}")),
            text(&output).contains(&format!("{version_style}1{version_style:#}")),
            text(&output).contains(&format!("{constraint_style}>=2{constraint_style:#}")),
            text(&output).contains(&format!("{constraint_style}==1{constraint_style:#}")),
            text(&output).contains(&format!("{label_style}installed:{label_style:#}")),
            text(&output).contains(&format!("{conflict_style}1{conflict_style:#}")),
            text(&output).contains(&format!("{conflict_style}⚠{conflict_style:#} ")),
            text(&output).contains(&format!("{error_style}✗{error_style:#} ")),
            text(&output).contains(&format!("{error_style}?{error_style:#}")),
            text(&output).contains(&format!("{extra_style} (GPL-3.0")),
            text(&output).contains("unique: leaf | unique"),
        ),
        (
            true, true, true, true, true, true, true, true, true, true, true, true
        )
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
        (true, 3)
    );
}
