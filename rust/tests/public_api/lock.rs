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
