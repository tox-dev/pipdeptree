use rstest::rstest;

use super::common::{
    PackageSite, execute, execute_in, execute_with_runner, package_site, stdout, with_python,
};

#[rstest]
#[case::freeze(&["--freeze"], "root==1\n")]
#[case::json_short(&["-j"], "\"package_name\": \"root\"")]
#[case::json(&["--json"], "\"package_name\": \"root\"")]
#[case::json_tree(&["--json-tree"], "\"dependencies\"")]
#[case::mermaid(&["--mermaid"], "flowchart TD")]
#[case::graphviz(&["--graph-output", "dot"], "digraph {")]
#[case::rich(&["--output", "rich"], "root==1")]
#[case::reverse(&["--reverse"], "child==1")]
#[case::summary(&["--summary"], "total packages:")]
#[case::summary_json(&["--summary", "--output", "json"], "\"total_packages\": 4")]
#[case::summary_rich(&["--summary", "--output", "rich"], "environment summary")]
#[case::all(&["--all", "--depth", "0"], "orphan==1")]
#[case::extras(
    &["--packages", "root[feature]", "--extras", "explicit"],
    "optional"
)]
#[case::metadata(
    &["--metadata", "license", "--computed", "size,size-raw", "--json"],
    "\"computed\""
)]
#[case::legacy_license(&["--license"], "MIT License")]
#[case::output_freeze(&["--output", "freeze"], "root==1\n")]
#[case::output_json(&["--output", "json"], "\"package_name\": \"root\"")]
#[case::output_json_tree(&["--output", "json-tree"], "\"dependencies\"")]
#[case::output_mermaid(&["--output", "mermaid"], "flowchart TD")]
#[case::output_graphviz(&["--output", "graphviz-dot"], "digraph {")]
#[case::short_extras(&["--packages", "root[feature]", "-x"], "optional")]
#[case::long_extras(&["--packages", "root[feature]", "--extras"], "optional")]
fn renders_cli_formats(package_site: PackageSite, #[case] args: &[&str], #[case] expected: &str) {
    let output = execute_in(&package_site, args);

    assert_eq!(
        (
            output.code,
            output.stderr.as_str(),
            stdout(&output).contains(expected)
        ),
        (0, "", true)
    );
}

#[rstest]
#[case::unknown_output(&["--output", "unknown"], "\"unknown\" is not a known output format")]
#[case::conflicting_formats(&["--json", "--freeze"], "render options are mutually exclusive")]
#[case::invalid_depth(&["--depth", "invalid"], "invalid value 'invalid'")]
#[case::missing_python(
    &["--python", "/path/that/does/not/exist"],
    "Failed to query custom interpreter"
)]
#[case::missing_lock(
    &["from-lock", "missing.pylock.toml"],
    "does not exist"
)]
#[case::invalid_requirement(
    &["from-index", "not a valid requirement !!!"],
    "Expected"
)]
#[case::invalid_summary_format(
    &["--summary", "--freeze"],
    "--summary supports only"
)]
#[case::exclude_dependencies_without_exclude(
    &["--exclude-dependencies"],
    "must use --exclude-dependencies with --exclude"
)]
#[case::path_with_environment_filter(
    &["--path", ".", "--local-only"],
    "cannot use --path with --user-only or --local-only"
)]
#[case::duplicate_license(
    &["--license", "--metadata", "license"],
    "cannot use --license with --metadata license"
)]
#[case::empty_index(&["from-index"], "from-index needs at least one")]
#[case::metadata_with_subcommand(
    &["--metadata", "license", "from-lock", "missing.toml"],
    "installed package metadata options cannot be used with a subcommand"
)]
#[case::license_with_subcommand(
    &["--license", "from-lock", "missing.toml"],
    "installed package metadata options cannot be used with a subcommand"
)]
#[case::computed_with_subcommand(
    &["--computed", "size", "from-lock", "missing.toml"],
    "installed package metadata options cannot be used with a subcommand"
)]
#[case::negative_depth(&["--depth", "-1"], "invalid value '-1'")]
#[case::invalid_warning(&["--warn", "unknown"], "invalid value 'unknown'")]
#[case::invalid_extras(&["--extras", "unknown"], "invalid value 'unknown'")]
#[case::invalid_computed(&["--computed", "unknown"], "invalid value 'unknown'")]
#[case::conflicting_environment_filters(
    &["--local-only", "--user-only"],
    "cannot be used with"
)]
#[case::path_with_user_filter(
    &["--path", ".", "--user-only"],
    "cannot use --path with --user-only or --local-only"
)]
#[case::summary_mermaid(&["--summary", "--mermaid"], "--summary supports only")]
#[case::summary_json_tree(&["--summary", "--json-tree"], "--summary supports only")]
#[case::summary_graphviz(
    &["--summary", "--graph-output", "png"],
    "--summary supports only"
)]
fn reports_cli_errors(#[case] args: &[&str], #[case] expected: &str) {
    let output = execute(args);

    assert_eq!(
        (
            output.code > 0,
            output.stdout.is_empty(),
            output.stderr.contains(expected),
        ),
        (true, true, true)
    );
}

#[rstest]
#[case::help("--help", "Usage: pipdeptree")]
#[case::version("--version", "pipdeptree 4.0.0\n")]
fn renders_informational_flags(#[case] flag: &str, #[case] expected: &str) {
    let output = execute(&[flag]);

    assert_eq!(
        (
            output.code,
            stdout(&output).contains(expected),
            output.stderr.as_str(),
        ),
        (0, true, "")
    );
}

#[test]
fn colors_help_for_terminals() {
    with_python(|python| {
        let output =
            execute_with_runner(&_pipdeptree::SystemProcessRunner, python, &["--help"], true);
        let heading = anstyle::AnsiColor::BrightBlue
            .on_default()
            .bold()
            .underline();
        let flag = anstyle::AnsiColor::Cyan.on_default().bold();

        assert_eq!(
            (
                output.code,
                stdout(&output).contains(&format!("{heading}Usage:{heading:#}")),
                stdout(&output).contains(&format!("{flag}--help{flag:#}")),
                stdout(&output).contains("[default: rich]"),
            ),
            (0, true, true, true)
        );
    });
}

#[test]
fn colors_terminal_errors_red() {
    with_python(|python| {
        let output = execute_with_runner(
            &_pipdeptree::SystemProcessRunner,
            python,
            &["--depth", "invalid"],
            true,
        );
        let red = anstyle::AnsiColor::Red.on_default().bold();

        assert_eq!(
            (
                output.code,
                output.stderr.contains(&format!("{red}error:{red:#}")),
            ),
            (2, true)
        );
    });
}

#[rstest]
fn defaults_to_rich_for_terminals(package_site: PackageSite) {
    with_python(|python| {
        let output = execute_with_runner(
            &_pipdeptree::SystemProcessRunner,
            python,
            &[
                "--path",
                package_site.path().to_str().unwrap(),
                "--warn",
                "silence",
            ],
            true,
        );

        assert_eq!(
            (
                output.code,
                stdout(&output).contains("\u{1b}["),
                stdout(&output).contains("┗━━"),
            ),
            (0, true, true)
        );
    });
}
