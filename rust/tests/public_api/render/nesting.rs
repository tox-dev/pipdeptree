use std::fmt::Write as _;

use rstest::rstest;

use super::super::common::execute;
use super::{lock_file, path};

const LIMIT_MESSAGE: &str = "dependency tree nests deeper than 200 levels";

// Each package requires the next one; the last requires `tail` when given.
fn chain_lock(packages: usize, tail: Option<&str>) -> String {
    let mut content = String::from("lock-version = '1.0'\n");
    for position in 0..packages {
        write!(
            content,
            "[[packages]]\nname = 'p{position:05}'\nversion = '1'\n"
        )
        .unwrap();
        if let Some(next) = (position + 1 < packages)
            .then(|| format!("p{:05}", position + 1))
            .or_else(|| tail.map(str::to_string))
        {
            writeln!(content, "dependencies = [{{ name = '{next}' }}]").unwrap();
        }
    }
    content
}

#[rstest]
#[case::text(&[])]
#[case::ascii(&["--encoding", "ascii"])]
#[case::rich(&["--output", "rich"])]
#[case::freeze(&["--freeze"])]
#[case::json_tree(&["--json-tree"])]
#[case::reverse_text(&["--reverse"])]
#[case::reverse_freeze(&["--freeze", "--reverse"])]
#[case::reverse_json_tree(&["--json-tree", "--reverse"])]
fn bounds_tree_nesting(
    #[case] args: &[&str],
    #[values((201, 0), (202, 1))] (packages, code): (usize, i32),
) {
    let (_directory, lock) = lock_file(&chain_lock(packages, None));

    let output = execute(
        &args
            .iter()
            .copied()
            .chain(["--warn", "silence", "from-lock", path(&lock)])
            .collect::<Vec<_>>(),
    );

    assert_eq!(
        (output.code, output.stderr.contains(LIMIT_MESSAGE)),
        (code, code == 1)
    );
}

#[rstest]
#[case::text(&["--reverse"])]
#[case::json_tree(&["--json-tree", "--reverse"])]
fn bounds_tree_nesting_below_missing_roots(
    #[case] args: &[&str],
    #[values((200, 0), (201, 1))] (packages, code): (usize, i32),
) {
    let (_directory, lock) = lock_file(&chain_lock(packages, Some("ghost")));

    let output = execute(
        &args
            .iter()
            .copied()
            .chain(["--warn", "silence", "from-lock", path(&lock)])
            .collect::<Vec<_>>(),
    );

    assert_eq!(
        (output.code, output.stderr.contains(LIMIT_MESSAGE)),
        (code, code == 1)
    );
}

#[test]
fn renders_deep_chains_within_requested_depth() {
    let (_directory, lock) = lock_file(&chain_lock(2_000, None));

    let output = execute(&["--depth", "2", "from-lock", path(&lock)]);

    assert_eq!(
        std::str::from_utf8(&output.stdout).unwrap(),
        concat!(
            "p00000==1\n",
            "└── p00001 [candidate: 1]\n",
            "    └── p00002 [candidate: 1]\n",
        )
    );
}

#[test]
fn reports_cycles_spanning_every_package() {
    let (_directory, lock) = lock_file(&chain_lock(50_000, Some("p00000")));

    let output = execute(&["--depth", "0", "from-lock", path(&lock)]);

    assert!(
        output
            .stderr
            .contains("Cyclic dependencies found:\n  p00000 => p00001 => p00002")
    );
}
