use std::fs;

use rstest::rstest;
use tempfile::tempdir;

use super::common::{execute, stdout};

#[rstest]
#[case::long("from-lock")]
#[case::alias("l")]
fn renders_pep_751_lock(#[case] command: &str) {
    let directory = tempdir().unwrap();
    let lock = directory.path().join("pylock.toml");
    fs::write(
        &lock,
        concat!(
            "[[packages]]\n",
            "name = \"Root.Name\"\n",
            "version = \"1\"\n",
            "dependencies = [{name = \"Child_Name\"}, {name = \"external\"}, {name = \"missing\"}]\n",
            "\n",
            "[[packages]]\n",
            "name = \"child-name\"\n",
            "version = \"2\"\n",
            "\n",
            "[[packages]]\n",
            "name = \"external\"\n",
        ),
    )
    .unwrap();

    let output = execute(&["--warn", "silence", command, lock.to_str().unwrap()]);

    assert_eq!(
        (output.code, stdout(&output), output.stderr.as_str()),
        (
            0,
            concat!(
                "Root.Name==1\n",
                "├── child-name [candidate: 2]\n",
                "├── external [candidate: ]\n",
                "└── missing [candidate: ?]\n"
            ),
            "",
        )
    );
}

#[rstest]
#[case::malformed("not = toml", "malformed TOML")]
#[case::missing_packages("name = \"demo\"", "missing 'packages' array")]
#[case::non_array("packages = {}", "missing 'packages' array")]
#[case::missing_name("[[packages]]\nversion = \"1\"", "package is missing 'name'")]
#[case::invalid_package("[[packages]]\nname = 1", "malformed TOML")]
#[case::invalid_dependency("[[packages]]\nname = \"demo\"\ndependencies = [{}]", "malformed TOML")]
fn rejects_invalid_locks(#[case] content: &str, #[case] expected: &str) {
    let directory = tempdir().unwrap();
    let lock = directory.path().join("pylock.toml");
    fs::write(&lock, content).unwrap();

    let output = execute(&["from-lock", lock.to_str().unwrap()]);

    assert_eq!(
        (
            output.code,
            output.stdout.is_empty(),
            output.stderr.contains(expected),
        ),
        (1, true, true)
    );
}

#[rstest]
#[case::first_line(
    "TOKEN=secret\0HOME=/root",
    "malformed TOML at line 1, column 18: unexpected key or value, expected newline, `#`\n"
)]
#[case::invalid_type(
    "lock-version = 1\n[[packages]]\nname = \"demo\"",
    "malformed TOML at line 1, column 16: invalid type: integer `1`, expected a string\n"
)]
#[case::later_line(
    "[[packages]]\nname = \"démo\" TOKEN=secret",
    "malformed TOML at line 2, column 15: unexpected key or value, expected newline, `#`\n"
)]
fn reports_parse_errors_without_the_source_line(#[case] content: &str, #[case] expected: &str) {
    let directory = tempdir().unwrap();
    let lock = directory.path().join("pylock.toml");
    fs::write(&lock, content).unwrap();

    let output = execute(&["from-lock", lock.to_str().unwrap()]);

    assert_eq!((output.code, output.stderr.as_str()), (1, expected));
}

#[rstest]
#[case::name_at_limit(255, 1, 0, "")]
#[case::version_at_limit(1, 255, 0, "")]
#[case::name_over_limit(256, 1, 1, "package 'name' is longer than 255 bytes\n")]
#[case::version_over_limit(1, 256, 1, "package 'version' is longer than 255 bytes\n")]
fn limits_lock_name_and_version_length(
    #[case] name: usize,
    #[case] version: usize,
    #[case] code: i32,
    #[case] expected: &str,
) {
    let directory = tempdir().unwrap();
    let lock = directory.path().join("pylock.toml");
    fs::write(
        &lock,
        format!(
            "[[packages]]\nname = \"{}\"\nversion = \"{}\"\n",
            "p".repeat(name),
            "1".repeat(version)
        ),
    )
    .unwrap();

    let output = execute(&["from-lock", lock.to_str().unwrap()]);

    assert_eq!(
        (
            output.code,
            output.stdout.is_empty(),
            output.stderr.as_str()
        ),
        (code, code == 1, expected)
    );
}

#[test]
fn freezes_resolved_packages() {
    let directory = tempdir().unwrap();
    let lock = directory.path().join("pylock.toml");
    fs::write(&lock, "[[packages]]\nname = \"locked\"\nversion = \"1\"\n").unwrap();

    let output = execute(&["--freeze", "from-lock", lock.to_str().unwrap()]);

    assert_eq!(
        (output.code, stdout(&output), output.stderr.as_str()),
        (0, "locked==1\n", "")
    );
}

#[rstest]
#[case::line_break_in_version(
    "aaa",
    "1.0\\n--index-url file:///x",
    "aaa===1.0?--index-url?file????x\n"
)]
#[case::option_as_name("--index-url=file:///x", "1", "?-index-url?file????x==1\n")]
#[case::comment_as_name("# coding: utf-7", "1", "??coding??utf-7==1\n")]
fn freezes_lock_values_on_one_line(
    #[case] name: &str,
    #[case] version: &str,
    #[case] expected: &str,
) {
    let directory = tempdir().unwrap();
    let lock = directory.path().join("pylock.toml");
    fs::write(
        &lock,
        format!("[[packages]]\nname = \"{name}\"\nversion = \"{version}\"\n"),
    )
    .unwrap();

    let output = execute(&["--freeze", "from-lock", lock.to_str().unwrap()]);

    assert_eq!(
        (output.code, stdout(&output), output.stderr.as_str()),
        (0, expected, "")
    );
}

#[test]
fn selects_lock_entries_by_marker() {
    let directory = tempdir().unwrap();
    let lock = directory.path().join("pylock.toml");
    fs::write(
        &lock,
        concat!(
            "lock-version = \"1.0\"\n",
            "[[packages]]\nname = \"root\"\nversion = \"1\"\n",
            "dependencies = [{name = \"beta\"}]\n",
            "[[packages]]\nname = \"beta\"\nversion = \"2\"\n",
            "marker = \"sys_platform == 'never-a-platform'\"\n",
            "[[packages]]\nname = \"beta\"\nversion = \"3\"\n",
        ),
    )
    .unwrap();

    let output = execute(&["from-lock", lock.to_str().unwrap()]);

    assert_eq!(
        (
            output.code,
            stdout(&output).contains("beta [candidate: 3]"),
            stdout(&output).contains("beta==2"),
        ),
        (0, true, false)
    );
}

#[test]
fn rejects_unsupported_lock_versions() {
    let directory = tempdir().unwrap();
    let lock = directory.path().join("pylock.toml");
    fs::write(
        &lock,
        "lock-version = \"2.0\"\n[[packages]]\nname = \"root\"\nversion = \"1\"\n",
    )
    .unwrap();

    let output = execute(&["from-lock", lock.to_str().unwrap()]);

    assert_eq!(
        (
            output.code,
            output.stderr.contains("unsupported lock-version")
        ),
        (1, true)
    );
}
