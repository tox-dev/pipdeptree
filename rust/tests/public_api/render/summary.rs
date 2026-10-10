use std::collections::BTreeSet;

use rstest::{fixture, rstest};
use serde_json::Value;
use textwrap::core::display_width;

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

#[rstest]
#[case::unicode(60, "utf-8", false)]
#[case::ascii(60, "ascii", false)]
#[case::color(60, "utf-8", true)]
#[case::minimum(33, "utf-8", false)]
fn fits_summary_to_terminal_width(
    licensed_site: PackageSite,
    #[case] width: usize,
    #[case] encoding: &str,
    #[case] color: bool,
) {
    let output = execute_at_width(&licensed_site, width, encoding, color);

    assert_eq!(
        text(&output)
            .lines()
            .map(display_width)
            .collect::<BTreeSet<_>>(),
        BTreeSet::from([width])
    );
}

#[rstest]
#[case::words("MIT OR Apache-2.0 OR BSD-3-Clause")]
#[case::long_word("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ")]
#[case::wide_characters("许可证许可证许可证许可证许可证许可证")]
#[case::combining_characters("Cafe\u{301} Cafe\u{301} Cafe\u{301} Cafe\u{301} Cafe\u{301}")]
fn preserves_wrapped_summary_licenses(
    #[case] license: &str,
    #[with(license)] licensed_site: PackageSite,
) {
    let output = execute_at_width(&licensed_site, 40, "utf-8", false);
    let values = text(&output)
        .lines()
        .skip_while(|line| !line.contains("licenses"))
        .take_while(|line| !line.contains("unknown licenses"))
        .map(|line| line.split('┃').nth(2).unwrap().trim())
        .collect::<String>();

    assert_eq!(
        values.replace(' ', ""),
        format!("({license}):1").replace(' ', "")
    );
}

#[rstest]
fn aligns_unicode_summary_borders(
    #[with("许可证许可证许可证许可证许可证")] licensed_site: PackageSite,
) {
    let output = execute_at_width(&licensed_site, 40, "utf-8", false);

    assert_eq!(
        text(&output)
            .lines()
            .map(display_width)
            .collect::<BTreeSet<_>>(),
        BTreeSet::from([40])
    );
}

#[rstest]
#[case::zero(0)]
#[case::narrow(20)]
#[case::below_minimum(32)]
fn falls_back_to_text_for_narrow_terminals(#[case] width: usize) {
    let site = render_site();

    assert_eq!(
        execute_at_width(&site, width, "utf-8", false).stdout,
        execute(&site, &["--summary", "--output", "text"]).stdout
    );
}

#[test]
fn keeps_small_summary_tables_compact() {
    let site = PackageSite::new();

    assert_eq!(
        execute_at_width(&site, 200, "utf-8", false).stdout,
        execute(&site, &["--summary", "--output", "rich"]).stdout
    );
}

#[fixture]
fn licensed_site(#[default("MIT OR Apache-2.0 OR BSD-3-Clause")] license: &str) -> PackageSite {
    let site = PackageSite::new();
    site.write(
        "demo-1.dist-info",
        &format!("Name: demo\nVersion: 1\nLicense-Expression: {license}\n"),
    );
    site
}

fn execute_at_width(
    site: &PackageSite,
    width: usize,
    encoding: &str,
    color: bool,
) -> _pipdeptree::Execution {
    super::super::common::with_python(|python| {
        _pipdeptree::Application::new(&_pipdeptree::SystemProcessRunner)
            .with_terminal_width(Some(width))
            .run(
                python,
                &[
                    "--path",
                    site.path().to_str().unwrap(),
                    "--warn",
                    "silence",
                    "--summary",
                    "--output",
                    "rich",
                    "--encoding",
                    encoding,
                ]
                .map(ToString::to_string),
                color,
                false,
            )
    })
}

#[test]
fn measures_depth_of_a_deep_chain() {
    let site = PackageSite::new();
    let depth: u64 = 400;
    for level in 0..depth {
        let requires = if level + 1 < depth {
            format!("Requires-Dist: pkg{:04}\n", level + 1)
        } else {
            String::new()
        };
        site.write(
            &format!("pkg{level:04}-1.dist-info"),
            &format!("Name: pkg{level:04}\nVersion: 1\n{requires}"),
        );
    }

    let output = execute(&site, &["--summary", "--output", "json"]);
    let value: Value = serde_json::from_slice(&output.stdout).unwrap();

    assert_eq!(value["max_depth"].as_u64(), Some(depth));
}

#[test]
fn measures_depth_through_reachable_cycles() {
    let site = PackageSite::new();
    site.write(
        "root-1.dist-info",
        "Name: root\nVersion: 1\nRequires-Dist: loop-a\n",
    );
    site.write(
        "loop-a-1.dist-info",
        "Name: loop-a\nVersion: 1\nRequires-Dist: loop-b\n",
    );
    site.write(
        "loop-b-1.dist-info",
        "Name: loop-b\nVersion: 1\nRequires-Dist: loop-a\n",
    );

    let output = execute(&site, &["--summary", "--output", "json"]);
    let value: Value = serde_json::from_slice(&output.stdout).unwrap();

    assert_eq!(
        (
            value["max_depth"].as_u64(),
            value["cyclic_dependencies"].as_u64()
        ),
        (Some(3), Some(2))
    );
}

#[test]
fn renders_summary_rich_ascii_for_non_unicode_encodings() {
    let site = render_site();
    let output = execute(
        &site,
        &["--summary", "--output", "rich", "--encoding", "ascii"],
    );

    assert_eq!(
        (text(&output).is_ascii(), text(&output).contains("+--")),
        (true, true)
    );
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
