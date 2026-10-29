use std::fs;
use std::path::{Path, PathBuf};

use _pipdeptree::Execution;
use pyo3::ffi::c_str;
use pyo3::types::{PyAnyMethods as _, PyDict, PyDictMethods as _};
use rstest::{fixture, rstest};
use serde_json::{Value, json};
use tempfile::{TempDir, tempdir};

use super::common::{
    execute, execute_with_python, execute_with_runner, install_resolver, stdout, with_python,
};

#[test]
fn resolves_inline_requirements() {
    let directory = tempdir().unwrap();
    let capture = directory.path().join("capture.txt");

    let output = with_python(|python| {
        install_resolver(python, &capture).unwrap();
        execute_with_python(
            python,
            &[
                "--warn",
                "silence",
                "from-index",
                "parent>=1",
                "--index-url",
                "https://primary.example/simple",
                "--extra-index-url",
                "https://extra.example/simple",
            ],
        )
    });

    assert_eq!(
        (
            output.code,
            stdout(&output),
            output.stderr.as_str(),
            fs::read_to_string(capture).unwrap(),
        ),
        (
            0,
            "parent==1\n├── child [required: >=1, candidate: 2]\n└── external [required: Any, candidate: ?]\n",
            "",
            concat!(
                "[project]\n",
                "name = \"pipdeptree-from-index\"\n",
                "version = \"0\"\n",
                "dependencies = [\"parent>=1\"]\n",
                "\n",
                "[[tool.nab.indexes]]\n",
                "name = \"primary\"\n",
                "url = \"https://primary.example/simple\"\n",
                "\n",
                "[[tool.nab.indexes]]\n",
                "name = \"extra-1\"\n",
                "url = \"https://extra.example/simple\"\n",
                "\n",
                "--- indexes ---\n",
                "[('primary', 'https://primary.example/simple'), ",
                "('extra-1', 'https://extra.example/simple')]",
            )
            .to_string(),
        )
    );
}

#[rstest]
#[case::default(None, None)]
#[case::nab(Some("nab"), None)]
#[case::xdg(None, Some("xdg"))]
#[case::nab_precedes_xdg(Some("nab"), Some("xdg"))]
#[case::relative_xdg(None, Some("relative"))]
fn passes_cache_path_to_nab(#[case] nab: Option<&str>, #[case] xdg: Option<&str>) {
    let directory = tempdir().unwrap();
    with_python(|python| {
        install_resolver(python, &directory.path().join("capture.txt")).unwrap();
        let nab_path = directory.path().join("nab");
        let xdg_path = directory.path().join("xdg");
        let output = temp_env::with_vars(
            [
                ("NAB_CACHE_DIR", nab.map(|_| nab_path.to_str().unwrap())),
                (
                    "XDG_CACHE_HOME",
                    xdg.map(|value| {
                        if value == "relative" {
                            value
                        } else {
                            xdg_path.to_str().unwrap()
                        }
                    }),
                ),
            ],
            || execute_with_python(python, &["from-index", "parent"]),
        );
        let actual = python
            .import("nab_project.resolve")
            .unwrap()
            .getattr("last_cache_dir")
            .unwrap()
            .extract::<std::path::PathBuf>()
            .unwrap();
        let expected = if nab.is_some() {
            nab_path
        } else if xdg == Some("xdg") {
            xdg_path.join("nab")
        } else {
            python
                .import("pathlib")
                .unwrap()
                .getattr("Path")
                .unwrap()
                .call_method0("home")
                .unwrap()
                .extract::<std::path::PathBuf>()
                .unwrap()
                .join(".cache/nab")
        };
        assert_eq!((output.code, actual), (0, expected));
    });
}

#[test]
fn rejects_empty_nab_cache_dir() {
    let output = with_python(|python| {
        temp_env::with_var("NAB_CACHE_DIR", Some(""), || {
            execute_with_python(python, &["from-index", "parent"])
        })
    });

    assert_eq!(
        (output.code, output.stderr.as_str()),
        (1, "ValueError: NAB_CACHE_DIR must be a non-empty path\n")
    );
}

#[test]
fn preserves_active_declarations_in_json() {
    let output = resolved_output(&[
        "--warn",
        "silence",
        "--json",
        "from-index",
        "parent[feature]",
    ]);
    let entries: Value = serde_json::from_slice(&output.stdout).unwrap();
    let parent = entries
        .as_array()
        .unwrap()
        .iter()
        .find(|entry| entry["package"]["key"] == "parent")
        .unwrap();
    let children = parent["dependencies"].as_array().unwrap();

    assert_eq!(
        children
            .iter()
            .filter(|entry| entry["key"] == "child")
            .map(|entry| (&entry["required_version"], &entry["declaration"]))
            .collect::<Vec<_>>(),
        vec![
            (
                &json!(">=1"),
                &json!({
                    "requirement_text": "child>=1",
                    "dependency_specifier": ">=1",
                    "requirement_condition": null,
                    "dependency_extras": [],
                    "required_for_parent_extras": [],
                    "required_without_parent_extras": true,
                }),
            ),
            (
                &json!("<3"),
                &json!({
                    "requirement_text": "child[socks]<3; extra == \"feature\"",
                    "dependency_specifier": "<3",
                    "requirement_condition": "extra == \"feature\"",
                    "dependency_extras": ["socks"],
                    "required_for_parent_extras": ["feature"],
                    "required_without_parent_extras": false,
                }),
            ),
        ]
    );
}

#[test]
fn leaves_unrecorded_edges_without_a_required_version() {
    let output = resolved_output(&["--warn", "silence", "--json", "from-index", "parent[empty]"]);
    let entries: Value = serde_json::from_slice(&output.stdout).unwrap();
    let parent = entries
        .as_array()
        .unwrap()
        .iter()
        .find(|entry| entry["package"]["key"] == "parent")
        .unwrap();

    assert_eq!(
        parent["dependencies"][1],
        json!({
            "key": "external",
            "package_name": "external",
            "candidate_version": "?",
        })
    );
}

#[rstest]
#[case::suppress("suppress", concat!(
    "Warning: the resolver reported:\n",
    "Skipping logs==2: d[x\u{fffd}]0;t\u{fffd}]\n",
    "    ~~^\n",
    "------------------------------------------------------------------------\n",
    "Warning: dependency problems found:\n",
    "* parent==1\n",
    "  - external [required: Any, installed: ?]\n",
    "------------------------------------------------------------------------\n\n",
))]
#[case::silence("silence", "")]
fn reports_resolver_logs_as_warnings(#[case] warn: &str, #[case] expected: &str) {
    let output = resolved_output(&["--warn", warn, "-o", "freeze", "from-index", "logs"]);

    assert_eq!(
        (output.code, stdout(&output), output.stderr.as_str()),
        (0, "parent==1\n  child==2\n  external\n", expected)
    );
}

#[rstest]
#[case::suppress("suppress", concat!(
    "Warning: the resolver reported:\n",
    "Skipping logs==2: d[x\u{fffd}]0;t\u{fffd}]\n",
    "    ~~^\n",
    "------------------------------------------------------------------------\n",
    "ValueError: no version of \u{fffd}[2Jraises\n",
))]
#[case::silence("silence", "ValueError: no version of \u{fffd}[2Jraises\n")]
fn reports_resolver_logs_before_a_resolver_error(#[case] warn: &str, #[case] expected: &str) {
    let output = resolved_output(&["--warn", warn, "from-index", "logs", "raises"]);

    assert_eq!(
        (
            output.code,
            output.stdout.is_empty(),
            output.stderr.as_str()
        ),
        (1, true, expected)
    );
}

#[rstest]
#[case::name("long-name", "package 'name' is longer than 255 bytes\n")]
#[case::version("long-version", "package 'version' is longer than 255 bytes\n")]
fn rejects_pins_longer_than_the_identity_limit(#[case] requirement: &str, #[case] expected: &str) {
    let output = resolved_output(&["from-index", requirement]);

    assert_eq!(
        (
            output.code,
            output.stdout.is_empty(),
            output.stderr.as_str()
        ),
        (1, true, expected)
    );
}

#[rstest]
#[case::root(&[])]
#[case::filtered(&["--packages", "parent[feature]"])]
fn renders_parent_and_child_extras(#[case] flags: &[&str]) {
    let output = resolved_output(
        &["--warn", "silence"]
            .iter()
            .copied()
            .chain(flags.iter().copied())
            .chain(["from-index", "parent[feature]"])
            .collect::<Vec<_>>(),
    );

    assert_eq!(
        stdout(&output),
        concat!(
            "parent==1\n",
            "├── child [required: >=1, candidate: 2]\n",
            "├── child[socks] [required: <3, candidate: 2, extra: feature]\n",
            "└── external [required: Any, candidate: ?]\n",
        )
    );
}

#[test]
fn renders_declarations_in_colored_rich_text() {
    let directory = tempdir().unwrap();
    let output = with_python(|python| {
        install_resolver(python, &directory.path().join("capture.txt")).unwrap();
        execute_with_runner(
            &_pipdeptree::SystemProcessRunner,
            python,
            &[
                "--warn",
                "silence",
                "--output",
                "rich",
                "from-index",
                "parent[feature]",
            ],
            true,
        )
    });

    assert!(stdout(&output).contains("required:"));
    assert!(stdout(&output).contains("candidate:"));
    assert!(stdout(&output).contains("child[socks]"));
}

#[test]
fn renders_declarations_in_reverse_text() {
    let output = resolved_output(&[
        "--warn",
        "silence",
        "--reverse",
        "--packages",
        "child",
        "from-index",
        "parent[feature]",
    ]);

    assert!(stdout(&output).contains("[requires: child[socks]<3, extra: feature]"));
}

#[rstest]
#[case::mermaid(&["--mermaid"], "parent -- \"[feature] <3\" --> child")]
#[case::graphviz(&["--graph-output", "dot"], "parent -> child [label=\"[feature] <3\"]")]
fn renders_declarations_in_graph_edges(#[case] args: &[&str], #[case] expected: &str) {
    let output = resolved_output(
        &args
            .iter()
            .copied()
            .chain(["from-index", "parent[feature]"])
            .collect::<Vec<_>>(),
    );

    assert!(stdout(&output).contains(expected));
}

#[rstest]
#[case::forward_tree(&["--json-tree"], false)]
#[case::reverse_flat(&["--json", "--reverse", "--packages", "child"], true)]
#[case::reverse_tree(&["--json-tree", "--reverse", "--packages", "child"], true)]
fn retains_declarations_in_json(#[case] flags: &[&str], #[case] reverse: bool) {
    let output = resolved_output(
        &["--warn", "silence"]
            .iter()
            .copied()
            .chain(flags.iter().copied())
            .chain(["from-index", "parent[feature]"])
            .collect::<Vec<_>>(),
    );
    let entries: Value = serde_json::from_slice(&output.stdout).unwrap();

    assert_eq!(
        entries[0]["dependencies"]
            .as_array()
            .unwrap()
            .iter()
            .filter(|entry| reverse || entry["key"] == "child")
            .map(|entry| (
                &entry["required_version"],
                &entry["declaration"]["requirement_text"]
            ))
            .collect::<Vec<_>>(),
        vec![
            (&json!(">=1"), &json!("child>=1")),
            (&json!("<3"), &json!("child[socks]<3; extra == \"feature\"")),
        ]
    );
}

#[test]
fn reverse_follows_parent_extras_from_nab() {
    let output = resolved_output(&[
        "--warn",
        "silence",
        "--json-tree",
        "--reverse",
        "--packages",
        "child",
        "from-index",
        "chain",
        "other",
        "plain",
    ]);
    let entries: Value = serde_json::from_slice(&output.stdout).unwrap();

    assert_eq!(
        entries[0]["dependencies"]
            .as_array()
            .unwrap()
            .iter()
            .map(|entry| json!({
                "extra": entry["declaration"]["required_for_parent_extras"],
                "parents": entry["dependencies"]
                    .as_array()
                    .unwrap()
                    .iter()
                    .map(|parent| &parent["key"])
                    .collect::<Vec<_>>(),
            }))
            .collect::<Vec<_>>(),
        vec![
            json!({"extra": [], "parents": ["chain", "other", "plain"]}),
            json!({"extra": ["feature", "other"], "parents": ["chain", "other"]}),
        ]
    );
}

#[test]
fn parses_requirement_sources() {
    let directory = tempdir().unwrap();
    let sources = write_requirement_sources(directory.path());
    let capture = directory.path().join("capture.txt");

    let output = with_python(|python| {
        install_resolver(python, &capture).unwrap();
        temp_env::with_vars(
            [
                ("PIP_INDEX_URL", None::<&str>),
                ("UV_INDEX_URL", None),
                ("PIP_EXTRA_INDEX_URL", None),
                ("UV_EXTRA_INDEX_URL", None),
            ],
            || {
                execute_with_python(
                    python,
                    &[
                        "--warn",
                        "silence",
                        "from-index",
                        "vcs-package @ git+https://example.com/repo.git@0123456789abcdef0123456789abcdef01234567",
                        sources.absolute.to_str().unwrap(),
                        &sources.file_requirement,
                        "--requirements",
                        sources.requirements.to_str().unwrap(),
                        "--pyproject",
                        sources.project.to_str().unwrap(),
                        "--pyproject",
                        sources.no_project.to_str().unwrap(),
                    ],
                )
            },
        )
    });

    assert_eq!(
        (
            output.code,
            stdout(&output),
            output.stderr.as_str(),
            fs::read_to_string(capture).unwrap(),
        ),
        (
            0,
            "parent==1\n├── child [required: >=1, candidate: 2]\n└── external [required: Any, candidate: ?]\n",
            "",
            expected_requirement_sources(&sources),
        )
    );
}

#[test]
fn parses_pip_requirement_file_syntax() {
    let directory = tempdir().unwrap();
    fs::write(directory.path().join("nested.txt"), "nested-package\n").unwrap();
    fs::write(
        directory.path().join("requirements.txt"),
        "-rnested.txt\nparent\t# tab comment\n",
    )
    .unwrap();
    let capture = directory.path().join("capture.txt");

    let output = with_python(|python| {
        install_resolver(python, &capture).unwrap();
        execute_with_python(
            python,
            &[
                "--warn",
                "silence",
                "from-index",
                "--requirements",
                directory.path().join("requirements.txt").to_str().unwrap(),
            ],
        )
    });
    let pyproject = fs::read_to_string(capture).unwrap();

    assert_eq!(
        (
            output.code,
            output.stderr.as_str(),
            pyproject.contains("\"nested-package\""),
            pyproject.contains("\"parent\""),
        ),
        (0, "", true, true)
    );
}

#[rstest]
#[case::short("-i https://private.example/simple", "-i", "--index-url")]
#[case::short_attached("-ihttps://private.example/simple", "-i", "--index-url")]
#[case::long(
    "--index-url https://private.example/simple",
    "--index-url",
    "--index-url"
)]
#[case::long_equals(
    "--index-url=https://private.example/simple",
    "--index-url",
    "--index-url"
)]
#[case::extra(
    "--extra-index-url https://private.example/simple",
    "--extra-index-url",
    "--extra-index-url"
)]
fn warns_about_an_index_option_in_a_requirements_file(
    #[case] line: &str,
    #[case] option: &str,
    #[case] flag: &str,
) {
    let directory = tempdir().unwrap();
    let requirements = directory.path().join("requirements.txt");
    fs::write(&requirements, format!("parent\n{line}\n")).unwrap();

    let output = resolved_output(&[
        "from-index",
        "--requirements",
        requirements.to_str().unwrap(),
    ]);

    assert_eq!(
        (output.code, output.stderr.lines().next().unwrap()),
        (
            0,
            format!(
                "Warning: {}:2: from-index ignores {option} in requirements files; pass {flag} on the command line",
                requirements.canonicalize().unwrap().display()
            )
            .as_str()
        )
    );
}

#[test]
fn warns_about_an_index_option_before_a_failed_resolve() {
    let directory = tempdir().unwrap();
    let requirements = directory.path().join("requirements.txt");
    fs::write(&requirements, "-i https://private.example/simple\nparent\n").unwrap();

    let output = with_python(|python| {
        temp_env::with_var("NAB_CACHE_DIR", Some(""), || {
            execute_with_python(
                python,
                &[
                    "from-index",
                    "--requirements",
                    requirements.to_str().unwrap(),
                ],
            )
        })
    });

    assert_eq!(
        (output.code, output.stderr),
        (
            1,
            format!(
                "Warning: {}:1: from-index ignores -i in requirements files; pass --index-url on the command line\n\
                 ValueError: NAB_CACHE_DIR must be a non-empty path\n",
                requirements.canonicalize().unwrap().display()
            )
        )
    );
}

#[test]
fn reports_index_option_warnings_before_resolver_logs() {
    let directory = tempdir().unwrap();
    let requirements = directory.path().join("requirements.txt");
    fs::write(&requirements, "-i https://private.example/simple\nlogs\n").unwrap();

    let output = resolved_output(&[
        "-o",
        "freeze",
        "from-index",
        "--requirements",
        requirements.to_str().unwrap(),
    ]);

    assert_eq!(
        (output.code, stdout(&output), output.stderr.as_str()),
        (
            0,
            "parent==1\n  child==2\n  external\n",
            format!(
                "Warning: {}:1: from-index ignores -i in requirements files; pass --index-url on the command line\n\
                 Warning: the resolver reported:\n\
                 Skipping logs==2: d[x\u{fffd}]0;t\u{fffd}]\n    ~~^\n\
                 ------------------------------------------------------------------------\n\
                 Warning: dependency problems found:\n\
                 * parent==1\n  - external [required: Any, installed: ?]\n\
                 ------------------------------------------------------------------------\n\n",
                requirements.canonicalize().unwrap().display()
            )
            .as_str()
        )
    );
}

#[test]
fn inherits_constraint_flag_for_nested_requirement_files() {
    let directory = tempdir().unwrap();
    fs::write(directory.path().join("nested.txt"), "pinned<3\n").unwrap();
    fs::write(directory.path().join("constraints.txt"), "-r nested.txt\n").unwrap();
    fs::write(
        directory.path().join("requirements.txt"),
        "-c constraints.txt\nparent\n",
    )
    .unwrap();
    let capture = directory.path().join("capture.txt");

    let output = with_python(|python| {
        install_resolver(python, &capture).unwrap();
        execute_with_python(
            python,
            &[
                "--warn",
                "silence",
                "from-index",
                "--requirements",
                directory.path().join("requirements.txt").to_str().unwrap(),
            ],
        )
    });
    let pyproject = fs::read_to_string(capture).unwrap();

    assert_eq!(
        (
            output.code,
            output.stderr.as_str(),
            pyproject.contains("dependencies = [\"parent\"]"),
            pyproject.contains("constraints = [\"pinned<3\"]"),
        ),
        (0, "", true, true)
    );
}

#[rstest]
#[case::same_role(
    "-r nested.txt\n-r nested.txt\n",
    "dependencies = [\"nested-package\"]"
)]
#[case::requirement_and_constraint(
    "-r nested.txt\n-c nested.txt\n",
    "dependencies = [\"nested-package\"]\n\n[tool.nab]\nconstraints = [\"nested-package\"]"
)]
fn parses_a_repeated_include_once_per_role(#[case] requirements: &str, #[case] expected: &str) {
    let directory = tempdir().unwrap();
    fs::write(directory.path().join("nested.txt"), "nested-package\n").unwrap();
    fs::write(directory.path().join("requirements.txt"), requirements).unwrap();
    let capture = directory.path().join("capture.txt");

    let output = with_python(|python| {
        install_resolver(python, &capture).unwrap();
        execute_with_python(
            python,
            &[
                "--warn",
                "silence",
                "from-index",
                "--requirements",
                directory.path().join("requirements.txt").to_str().unwrap(),
            ],
        )
    });
    let pyproject = fs::read_to_string(capture).unwrap();

    assert_eq!(
        (
            output.code,
            output.stderr.as_str(),
            pyproject.split_once("\n\n--- indexes ---").unwrap().0,
        ),
        (
            0,
            "",
            format!("[project]\nname = \"pipdeptree-from-index\"\nversion = \"0\"\n{expected}")
                .as_str()
        )
    );
}

#[test]
fn maps_editable_vcs_requirements_to_sources() {
    let directory = tempdir().unwrap();
    let capture = directory.path().join("capture.txt");
    let url = "git+https://example.com/repo.git@0123456789abcdef0123456789abcdef01234567#egg=edit-package";

    let output = with_python(|python| {
        install_resolver(python, &capture).unwrap();
        fs::write(
            directory.path().join("requirements.txt"),
            format!("-e {url}\n"),
        )
        .unwrap();
        execute_with_python(
            python,
            &[
                "--warn",
                "silence",
                "from-index",
                "--requirements",
                directory.path().join("requirements.txt").to_str().unwrap(),
            ],
        )
    });
    let pyproject = fs::read_to_string(capture).unwrap();

    assert_eq!(
        (
            output.code,
            output.stderr.as_str(),
            pyproject.contains("name = \"edit-package\""),
        ),
        (0, "", true)
    );
}

#[test]
fn reports_real_resolver_import_failures() {
    with_python(|python| {
        python
            .run(
                c_str!(
                    r#"
import importlib.abc
import sys


class _PipdeptreeBoom(importlib.abc.MetaPathFinder):
    def find_spec(self, name, path=None, target=None):
        if name == "nab_index.multi_index":
            raise RuntimeError("resolver import exploded")


sys.modules.pop("nab_index.multi_index", None)
sys.meta_path.insert(0, _PipdeptreeBoom())
"#
                ),
                None,
                None,
            )
            .unwrap();
        let output = execute_with_python(python, &["--warn", "silence", "from-index", "parent"]);
        python
            .run(c_str!("import sys\nsys.meta_path.pop(0)"), None, None)
            .unwrap();

        assert_eq!(
            (
                output.code,
                output.stderr.contains("resolver import exploded"),
            ),
            (1, true)
        );
    });
}

#[test]
fn accepts_egg_fragment_vcs_requirements() {
    let directory = tempdir().unwrap();
    let capture = directory.path().join("capture.txt");
    let url =
        "git+https://example.com/repo.git@0123456789abcdef0123456789abcdef01234567#egg=egg-package";

    let output = with_python(|python| {
        install_resolver(python, &capture).unwrap();
        fs::write(
            directory.path().join("requirements.txt"),
            format!("{url}\n"),
        )
        .unwrap();
        execute_with_python(
            python,
            &[
                "--warn",
                "silence",
                "from-index",
                "--requirements",
                directory.path().join("requirements.txt").to_str().unwrap(),
            ],
        )
    });
    let pyproject = fs::read_to_string(capture).unwrap();

    assert_eq!(
        (
            output.code,
            output.stderr.as_str(),
            pyproject.contains("name = \"egg-package\""),
            pyproject.contains(&format!("url = \"{url}\"")),
        ),
        (0, "", true, true)
    );
}

#[rstest]
#[case::own(
    "[[tool.nab.indexes]]\nname = \"own\"\nurl = \"https://own.example/simple\"\n",
    &[],
    "[('own', 'https://own.example/simple')]"
)]
#[case::explicit_override(
    "[[tool.nab.indexes]]\nname = \"own\"\nurl = \"https://own.example/simple\"\n",
    &["--index-url", "https://override.example/simple"],
    "[('primary', 'https://override.example/simple')]"
)]
#[case::pypi(
    "",
    &["--index-url", "https://pypi.org/simple"],
    "[('pypi', 'https://pypi.org/simple')]"
)]
#[case::credentials(
    "",
    &["--index-url", "https://user:secret@override.example/simple"],
    "[('primary', 'https://override.example/simple')]"
)]
fn resolves_pyproject_indexes(
    #[case] tool_config: &str,
    #[case] index_args: &[&str],
    #[case] expected: &str,
) {
    let directory = tempdir().unwrap();
    let pyproject = directory.path().join("pyproject.toml");
    fs::write(
        &pyproject,
        format!("[project]\nname = \"demo\"\nversion = \"1\"\ndependencies = []\n{tool_config}"),
    )
    .unwrap();
    let capture = directory.path().join("capture.txt");

    let output = with_python(|python| {
        install_resolver(python, &capture).unwrap();
        temp_env::with_vars(
            [
                ("PIP_INDEX_URL", None::<&str>),
                ("UV_INDEX_URL", None),
                ("PIP_EXTRA_INDEX_URL", None),
                ("UV_EXTRA_INDEX_URL", None),
            ],
            || {
                execute_with_python(
                    python,
                    &[
                        "--warn",
                        "silence",
                        "i",
                        "--pyproject",
                        pyproject.to_str().unwrap(),
                    ]
                    .into_iter()
                    .chain(index_args.iter().copied())
                    .collect::<Vec<_>>(),
                )
            },
        )
    });

    assert_eq!(
        (
            output.code,
            stdout(&output),
            output.stderr.as_str(),
            fs::read_to_string(capture).unwrap().ends_with(expected),
        ),
        (
            0,
            "parent==1\n├── child [required: >=1, candidate: 2]\n└── external [required: Any, candidate: ?]\n",
            "",
            true,
        )
    );
}

#[rstest]
#[case::default(
    &[],
    &[],
    "[('pypi', 'https://pypi.org/simple/')]"
)]
#[case::pip_primary(
    &[],
    &[("PIP_INDEX_URL", Some("https://pip.example/simple"))],
    "[('primary', 'https://pip.example/simple')]"
)]
#[case::uv_primary(
    &[],
    &[("UV_INDEX_URL", Some("https://uv.example/simple"))],
    "[('primary', 'https://uv.example/simple')]"
)]
#[case::pip_precedes_uv(
    &[],
    &[
        ("PIP_INDEX_URL", Some("https://pip.example/simple")),
        ("UV_INDEX_URL", Some("https://uv.example/simple")),
    ],
    "[('primary', 'https://pip.example/simple')]"
)]
#[case::flag_precedes_environment(
    &["--index-url", "https://flag.example/simple"],
    &[("PIP_INDEX_URL", Some("https://pip.example/simple"))],
    "[('primary', 'https://flag.example/simple')]"
)]
#[case::empty_environment_falls_back(
    &[],
    &[("PIP_INDEX_URL", Some(""))],
    "[('pypi', 'https://pypi.org/simple/')]"
)]
#[case::pip_extras(
    &[],
    &[(
        "PIP_EXTRA_INDEX_URL",
        Some("https://one.example/simple https://two.example/simple"),
    )],
    concat!(
        "[('pypi', 'https://pypi.org/simple'), ",
        "('extra-1', 'https://one.example/simple'), ('extra-2', 'https://two.example/simple')]"
    )
)]
#[case::uv_extras(
    &[],
    &[("UV_EXTRA_INDEX_URL", Some("https://uv.example/simple"))],
    "[('pypi', 'https://pypi.org/simple'), ('extra-1', 'https://uv.example/simple')]"
)]
#[case::empty_pip_extras_fall_back(
    &[],
    &[
        ("PIP_EXTRA_INDEX_URL", Some("")),
        ("UV_EXTRA_INDEX_URL", Some("https://uv.example/simple")),
    ],
    "[('pypi', 'https://pypi.org/simple'), ('extra-1', 'https://uv.example/simple')]"
)]
#[case::pip_credentials(
    &[],
    &[("PIP_INDEX_URL", Some("https://user:secret@pip.example/simple"))],
    "[('primary', 'https://pip.example/simple')]"
)]
#[case::flag_token(
    &["--index-url", "https://token@flag.example/simple"],
    &[],
    "[('primary', 'https://flag.example/simple')]"
)]
#[case::pypi_credentials(
    &["--index-url", "https://user:secret@pypi.org/simple"],
    &[],
    "[('pypi', 'https://pypi.org/simple')]"
)]
#[case::extra_credentials(
    &[],
    &[(
        "PIP_EXTRA_INDEX_URL",
        Some("https://user:p%40ss@one.example/simple https://two.example/simple"),
    )],
    concat!(
        "[('pypi', 'https://pypi.org/simple'), ",
        "('extra-1', 'https://one.example/simple'), ('extra-2', 'https://two.example/simple')]"
    )
)]
#[case::flag_extras_precede_environment(
    &["--extra-index-url", "https://flag.example/simple"],
    &[("PIP_EXTRA_INDEX_URL", Some("https://env.example/simple"))],
    "[('pypi', 'https://pypi.org/simple'), ('extra-1', 'https://flag.example/simple')]"
)]
fn resolves_environment_indexes(
    #[case] index_args: &[&str],
    #[case] environment: &[(&str, Option<&str>)],
    #[case] expected: &str,
) {
    let directory = tempdir().unwrap();
    let capture = directory.path().join("capture.txt");

    let output = with_python(|python| {
        install_resolver(python, &capture).unwrap();
        temp_env::with_vars(
            [
                ("PIP_INDEX_URL", None::<&str>),
                ("UV_INDEX_URL", None),
                ("PIP_EXTRA_INDEX_URL", None),
                ("UV_EXTRA_INDEX_URL", None),
            ],
            || {
                temp_env::with_vars(environment, || {
                    execute_with_python(
                        python,
                        &["--warn", "silence", "from-index", "parent"]
                            .into_iter()
                            .chain(index_args.iter().copied())
                            .collect::<Vec<_>>(),
                    )
                })
            },
        )
    });

    assert_eq!(
        (
            output.code,
            output.stderr.as_str(),
            fs::read_to_string(capture).unwrap().ends_with(expected),
        ),
        (0, "", true)
    );
}

#[test]
fn reports_missing_resolver_module() {
    let output = with_python(|python| {
        let module = python.import("nab_index.multi_index").unwrap();
        let modules = python
            .import("sys")
            .unwrap()
            .getattr("modules")
            .unwrap()
            .cast_into::<PyDict>()
            .unwrap();
        modules
            .set_item("nab_index.multi_index", python.None())
            .unwrap();

        let output = execute_with_python(python, &["from-index", "demo"]);

        modules.set_item("nab_index.multi_index", module).unwrap();
        output
    });

    assert_eq!(
        (output.code, output.stderr.as_str()),
        (
            1,
            "The from-index subcommand requires nab, nab-index and nab-project\n",
        )
    );
}

#[rstest]
#[case::missing_requirements(
    &["from-index", "--requirements", "missing.txt"],
    "source file does not exist"
)]
#[case::missing_pyproject(
    &["from-index", "--pyproject", "missing.toml"],
    "source file does not exist"
)]
#[case::unsupported_url(
    &["from-index", "demo @ https://example.com/demo.whl"],
    "URL requirements are not supported"
)]
#[case::unnamed_vcs(
    &["from-index", "git+https://example.com/demo.git"],
    "VCS requirement needs an explicit name"
)]
#[case::unpinned_vcs(
    &["from-index", "demo @ git+https://example.com/demo.git"],
    "VCS requirement must be pinned"
)]
#[case::short_vcs_pin(
    &["from-index", "demo @ git+https://example.com/demo.git@abc"],
    "VCS requirement must be pinned"
)]
#[case::invalid_vcs_pin(
    &["from-index", "demo @ git+https://example.com/demo.git@zzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzz"],
    "VCS requirement must be pinned"
)]
#[case::invalid_file_url(
    &["from-index", "demo @ file://example.com/demo"],
    "invalid local file URL"
)]
#[case::invalid_bare_file_url(
    &["from-index", "file://example.com/demo"],
    "invalid local file URL: file://example.com/demo"
)]
#[case::undecodable_bare_file_url(&["from-index", "file:%FF"], "invalid local file URL: file:%FF")]
#[case::malformed_named_source(
    &["from-index", "demo @ file://[invalid"],
    "invalid IPv6"
)]
fn rejects_invalid_index_arguments(#[case] args: &[&str], #[case] expected: &str) {
    let output = execute(args);

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
#[case::recursive(InvalidSource::Recursive, "recursive requirements include")]
#[case::constraint_source(
    InvalidSource::ConstraintSource,
    "source requirements cannot be constraints"
)]
#[case::constraint_path(
    InvalidSource::ConstraintPath,
    "source requirements cannot be constraints"
)]
#[case::constraint_editable(
    InvalidSource::ConstraintEditable,
    "source requirements cannot be constraints"
)]
#[case::constraint_editable_vcs(
    InvalidSource::ConstraintEditableVcs,
    "source requirements cannot be constraints"
)]
#[case::constraint_extras(InvalidSource::ConstraintExtras, "cannot constrain extras")]
#[case::missing_local(InvalidSource::MissingLocal, "/./missing: No such file or directory")]
#[case::local_without_pyproject(
    InvalidSource::LocalWithoutPyproject,
    "must be a directory with a pyproject.toml"
)]
#[case::local_without_name(InvalidSource::LocalWithoutName, "has no [project].name")]
#[case::malformed_local(InvalidSource::MalformedLocal, "TOML parse error")]
fn rejects_invalid_requirement_files(#[case] source: InvalidSource, #[case] expected: &str) {
    let directory = tempdir().unwrap();
    let requirements = directory.path().join("requirements.txt");
    let constraints = directory.path().join("constraints.txt");
    let local = directory.path().join("local");
    let requirement = match source {
        InvalidSource::Recursive => "-r requirements.txt",
        InvalidSource::ConstraintSource => {
            fs::write(&constraints, "demo @ https://example.com/demo.whl").unwrap();
            "-c constraints.txt"
        }
        InvalidSource::ConstraintPath => {
            fs::write(&constraints, "./missing").unwrap();
            "-c constraints.txt"
        }
        InvalidSource::ConstraintEditable => {
            fs::create_dir(&local).unwrap();
            fs::write(
                local.join("pyproject.toml"),
                "[project]\nname = \"local\"\n",
            )
            .unwrap();
            fs::write(&constraints, "-e ./local").unwrap();
            "-c constraints.txt"
        }
        InvalidSource::ConstraintEditableVcs => {
            fs::write(
                &constraints,
                "-e git+https://example.com/demo.git@0123456789abcdef0123456789abcdef01234567#egg=demo",
            )
            .unwrap();
            "-c constraints.txt"
        }
        InvalidSource::ConstraintExtras => {
            fs::write(&constraints, "demo[extra]>=1").unwrap();
            "-c constraints.txt"
        }
        InvalidSource::MissingLocal => "./missing",
        InvalidSource::LocalWithoutPyproject => {
            fs::create_dir(&local).unwrap();
            "./local"
        }
        InvalidSource::LocalWithoutName => {
            fs::create_dir(&local).unwrap();
            fs::write(local.join("pyproject.toml"), "[project]").unwrap();
            "./local"
        }
        InvalidSource::MalformedLocal => {
            fs::create_dir(&local).unwrap();
            fs::write(local.join("pyproject.toml"), "not =").unwrap();
            "./local"
        }
    };
    fs::write(&requirements, requirement).unwrap();

    let output = execute(&[
        "from-index",
        "--requirements",
        requirements.to_str().unwrap(),
    ]);

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
#[case::relative("file:pkg")]
#[case::dot_relative("file:./pkg")]
#[case::percent_encoded("file:p%6Bg")]
#[case::fragment("file:pkg#egg=local")]
#[case::named_relative("local @ file:pkg")]
#[case::named_dot_relative("local @ file:./pkg")]
#[case::single_slash("file:{abs}")]
#[case::absolute("file://{abs}")]
#[case::localhost("file://localhost{abs}")]
#[case::named_single_slash("local @ file:{abs}")]
#[case::named_absolute("local @ file://{abs}")]
#[case::named_localhost("local @ file://localhost{abs}")]
fn resolves_a_file_url_argument_like_pip(
    file_url_projects: FileUrlProjects,
    #[case] template: &str,
) {
    let source = file_url_projects.source(template);

    let output = file_url_projects.resolve(&source);

    assert_eq!(
        file_url_projects.resolved(&output, false),
        (0, "", true, false)
    );
}

#[rstest]
#[case::relative("file:pkg", false)]
#[case::dot_relative("file:./pkg", false)]
#[case::editable_relative("-e file:pkg", true)]
#[case::editable_dot_relative("-e file:./pkg", true)]
#[case::named_relative("local @ file:pkg", false)]
#[case::named_dot_relative("local @ file:./pkg", false)]
#[case::single_slash("file:{abs}", false)]
#[case::absolute("file://{abs}", false)]
#[case::localhost("file://localhost{abs}", false)]
#[case::editable_single_slash("-e file:{abs}", true)]
#[case::editable_absolute("-e file://{abs}", true)]
#[case::editable_localhost("-e file://localhost{abs}", true)]
#[case::named_single_slash("local @ file:{abs}", false)]
#[case::named_absolute("local @ file://{abs}", false)]
#[case::named_localhost("local @ file://localhost{abs}", false)]
fn resolves_a_file_url_requirement_like_pip(
    file_url_projects: FileUrlProjects,
    #[case] template: &str,
    #[case] editable: bool,
) {
    let requirements = file_url_projects.write_requirements(template);
    let output = file_url_projects.resolve(&requirements);

    assert_eq!(
        file_url_projects.resolved(&output, editable),
        (0, "", true, false)
    );
}

#[rstest]
#[case::bare("file://example.com{abs}")]
#[case::editable("-e file://example.com{abs}")]
#[case::named("local @ file://example.com{abs}")]
fn rejects_a_non_local_file_url_requirement(
    file_url_projects: FileUrlProjects,
    #[case] template: &str,
) {
    let requirements = file_url_projects.write_requirements(template);
    let output = file_url_projects.resolve(&requirements);

    assert_eq!(
        (
            output.code,
            output.stderr.contains(&format!(
                "invalid local file URL: {}",
                file_url_projects.source("file://example.com{abs}")
            )),
        ),
        (1, true)
    );
}

// pip resolves a relative file: URL against the working directory, never the requirements file's
// directory, so the decoy project next to the requirements file must not be picked up.
#[fixture]
fn file_url_projects() -> FileUrlProjects {
    let projects = FileUrlProjects {
        working: tempdir().unwrap(),
        elsewhere: tempdir().unwrap(),
    };
    write_named_project(projects.working.path(), "local");
    write_named_project(projects.elsewhere.path(), "decoy");
    projects
}

fn write_named_project(directory: &Path, name: &str) {
    let project = directory.join("pkg");
    fs::create_dir(&project).unwrap();
    fs::write(
        project.join("pyproject.toml"),
        format!("[project]\nname = \"{name}\"\n"),
    )
    .unwrap();
}

struct FileUrlProjects {
    working: TempDir,
    elsewhere: TempDir,
}

impl FileUrlProjects {
    fn source(&self, template: &str) -> String {
        let local = self.working.path().join("pkg");
        template.replace("{abs}", url::Url::from_file_path(local).unwrap().path())
    }

    fn resolve(&self, argument: &str) -> Execution {
        with_python(|python| {
            install_resolver(python, &self.capture()).unwrap();
            let current = std::env::current_dir().unwrap();
            std::env::set_current_dir(self.working.path()).unwrap();
            let output =
                execute_with_python(python, &["--warn", "silence", "from-index", argument]);
            std::env::set_current_dir(current).unwrap();
            output
        })
    }

    fn capture(&self) -> PathBuf {
        self.elsewhere.path().join("capture.txt")
    }

    fn resolved<'output>(
        &self,
        output: &'output Execution,
        editable: bool,
    ) -> (i32, &'output str, bool, bool) {
        let project = fs::read_to_string(self.capture()).unwrap();
        let local = self.working.path().join("pkg").canonicalize().unwrap();
        (
            output.code,
            output.stderr.as_str(),
            project.contains(&format!(
                "[[tool.nab.local-sources]]\nname = \"local\"\npath = \"{}\"\neditable = {editable}\n",
                local.display()
            )),
            project.contains("decoy"),
        )
    }

    fn write_requirements(&self, template: &str) -> String {
        let requirements = self.elsewhere.path().join("requirements.txt");
        fs::write(&requirements, format!("{}\n", self.source(template))).unwrap();
        format!("--requirements={}", requirements.display())
    }
}

#[test]
fn rejects_requirements_includes_nested_past_the_limit() {
    let directory = tempdir().unwrap();
    for level in 0..=100 {
        fs::write(
            directory.path().join(format!("r{level}.txt")),
            format!("-r r{}.txt\n", level + 1),
        )
        .unwrap();
    }
    fs::write(directory.path().join("r101.txt"), "demo\n").unwrap();

    let output = resolved_output(&[
        "from-index",
        "--requirements",
        directory.path().join("r0.txt").to_str().unwrap(),
    ]);

    assert_eq!(
        (output.code, output.stdout.is_empty(), output.stderr),
        (
            1,
            true,
            format!(
                "requirements include nested deeper than 100 levels: {}\n",
                directory
                    .path()
                    .canonicalize()
                    .unwrap()
                    .join("r100.txt")
                    .display()
            )
        )
    );
}

#[rstest]
#[case::included("-r netrc\n", "netrc", 2)]
#[case::continued("parent>=1\nnot a valid \\\n  requirement\n", "requirements.txt", 2)]
#[case::trailing("not a valid requirement !!! \\", "requirements.txt", 1)]
fn locates_an_invalid_requirement_without_quoting_it(
    #[case] requirements: &str,
    #[case] invalid_file: &str,
    #[case] line: usize,
) {
    let directory = tempdir().unwrap();
    fs::write(
        directory.path().join("netrc"),
        "# credentials\nmachine pypi.corp.example login ci password s3cr3t\n",
    )
    .unwrap();
    fs::write(directory.path().join("requirements.txt"), requirements).unwrap();

    let output = resolved_output(&[
        "from-index",
        "--requirements",
        directory.path().join("requirements.txt").to_str().unwrap(),
    ]);

    assert_eq!(
        (output.code, output.stdout.is_empty(), output.stderr),
        (
            1,
            true,
            format!(
                "{}:{line}: invalid requirement\n",
                directory
                    .path()
                    .canonicalize()
                    .unwrap()
                    .join(invalid_file)
                    .display()
            )
        )
    );
}

#[derive(Clone, Copy)]
enum InvalidSource {
    Recursive,
    ConstraintSource,
    ConstraintPath,
    ConstraintEditable,
    ConstraintEditableVcs,
    ConstraintExtras,
    MissingLocal,
    LocalWithoutPyproject,
    LocalWithoutName,
    MalformedLocal,
}

fn resolved_output(args: &[&str]) -> Execution {
    let directory = tempdir().unwrap();
    with_python(|python| {
        install_resolver(python, &directory.path().join("capture.txt")).unwrap();
        execute_with_python(python, args)
    })
}

struct RequirementSources {
    local: PathBuf,
    absolute: PathBuf,
    file_source: PathBuf,
    project: PathBuf,
    no_project: PathBuf,
    requirements: PathBuf,
    file_requirement: String,
}

fn write_requirement_sources(directory: &Path) -> RequirementSources {
    let local = directory.join("local");
    fs::create_dir(&local).unwrap();
    fs::write(
        local.join("pyproject.toml"),
        "[project]\nname = \"local-package\"\n",
    )
    .unwrap();
    let absolute = directory.join("absolute");
    fs::create_dir(&absolute).unwrap();
    fs::write(
        absolute.join("pyproject.toml"),
        "[project]\nname = \"absolute-package\"\n",
    )
    .unwrap();
    let file_source = directory.join("file-source");
    fs::create_dir(&file_source).unwrap();
    fs::write(
        file_source.join("pyproject.toml"),
        "[project]\nname = \"file-package\"\n",
    )
    .unwrap();
    let project = directory.join("project.toml");
    fs::write(
        &project,
        "[project]\nname = \"project\"\ndependencies = [\"pyproject-dependency\"]\n",
    )
    .unwrap();
    let no_project = directory.join("no-project.toml");
    fs::write(&no_project, "[build-system]\nrequires = []\n").unwrap();
    fs::write(
        directory.join("nested.txt"),
        "nested>=1 --hash=sha256:abc # retained\n",
    )
    .unwrap();
    fs::write(directory.join("constraints.txt"), "constraint<3 \\").unwrap();
    let requirements = directory.join("requirements.txt");
    fs::write(
        &requirements,
        concat!(
            "# ignored\n",
            "--requirement=nested.txt\n",
            "--constraint constraints.txt\n",
            "--find-links https://example.com\n",
            "-e ./local\n",
            "parent>=1; \\\n",
            "  python_version >= '3.10'\n",
        ),
    )
    .unwrap();
    let file_requirement = format!(
        "file-package @ {}",
        url::Url::from_file_path(&file_source).unwrap()
    );
    RequirementSources {
        local,
        absolute,
        file_source,
        project,
        no_project,
        requirements,
        file_requirement,
    }
}

fn expected_requirement_sources(sources: &RequirementSources) -> String {
    format!(
        concat!(
            "[project]\n",
            "name = \"pipdeptree-from-index\"\n",
            "version = \"0\"\n",
            "dependencies = [\"pyproject-dependency\", \"nested>=1\", ",
            "\"parent>=1 ; python_full_version >= '3.10'\", ",
            "\"local-package\", \"absolute-package\", \"file-package\", ",
            "\"vcs-package\"]\n",
            "\n",
            "[tool.nab]\n",
            "constraints = [\"constraint<3\"]\n",
            "\n",
            "[tool.nab.vcs]\n",
            "policy = \"allow\"\n",
            "allowed-schemes = [\"git+https\", \"git+ssh\", \"git+http\", \"git+file\", \"git+git\"]\n",
            "\n",
            "[[tool.nab.local-sources]]\n",
            "name = \"local-package\"\n",
            "path = \"{}\"\n",
            "editable = true\n",
            "\n",
            "[[tool.nab.local-sources]]\n",
            "name = \"absolute-package\"\n",
            "path = \"{}\"\n",
            "editable = false\n",
            "\n",
            "[[tool.nab.local-sources]]\n",
            "name = \"file-package\"\n",
            "path = \"{}\"\n",
            "editable = false\n",
            "\n",
            "[[tool.nab.vcs-sources]]\n",
            "name = \"vcs-package\"\n",
            "url = \"git+https://example.com/repo.git@{}\"\n",
            "\n",
            "[[tool.nab.package-rules]]\n",
            "match = [\"vcs-package\"]\n",
            "build-policy = \"build-remote\"\n",
            "\n",
            "--- indexes ---\n",
            "[('pypi', 'https://pypi.org/simple/')]",
        ),
        sources.local.canonicalize().unwrap().display(),
        sources.absolute.canonicalize().unwrap().display(),
        sources.file_source.canonicalize().unwrap().display(),
        "0123456789abcdef0123456789abcdef01234567",
    )
}
