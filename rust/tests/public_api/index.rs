use std::fs;
use std::path::{Path, PathBuf};

use pyo3::types::{PyAnyMethods as _, PyDict, PyDictMethods as _};
use rstest::rstest;
use tempfile::tempdir;

use super::common::{execute, execute_with_python, install_resolver, stdout, with_python};

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
            "parent==1\n├── child [candidate: 2]\n└── external [candidate: ?]\n",
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

#[test]
fn parses_requirement_sources() {
    let directory = tempdir().unwrap();
    let sources = write_requirement_sources(directory.path());
    let capture = directory.path().join("capture.txt");

    let output = with_python(|python| {
        install_resolver(python, &capture).unwrap();
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
            "parent==1\n├── child [candidate: 2]\n└── external [candidate: ?]\n",
            "",
            expected_requirement_sources(&sources),
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
            "parent==1\n├── child [candidate: 2]\n└── external [candidate: ?]\n",
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
            "The from-index subcommand requires nab-index and nab-python\n",
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
#[case::constraint_extras(InvalidSource::ConstraintExtras, "cannot constrain extras")]
#[case::missing_local(InvalidSource::MissingLocal, "No such file or directory")]
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

#[test]
fn rejects_invalid_trailing_logical_requirement() {
    let directory = tempdir().unwrap();
    let requirements = directory.path().join("requirements.txt");
    fs::write(&requirements, "not a valid requirement !!! \\").unwrap();

    let output = execute(&[
        "from-index",
        "--requirements",
        requirements.to_str().unwrap(),
    ]);

    assert_eq!(
        (
            output.code,
            output.stdout.is_empty(),
            output.stderr.contains("Expected"),
        ),
        (1, true, true)
    );
}

#[derive(Clone, Copy)]
enum InvalidSource {
    Recursive,
    ConstraintSource,
    ConstraintPath,
    ConstraintExtras,
    MissingLocal,
    LocalWithoutPyproject,
    LocalWithoutName,
    MalformedLocal,
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
            "build-policy = \"build-remote\"\n",
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
            "--- indexes ---\n",
            "[('pypi', 'https://pypi.org/simple/')]",
        ),
        sources.local.canonicalize().unwrap().display(),
        sources.absolute.canonicalize().unwrap().display(),
        sources.file_source.canonicalize().unwrap().display(),
        "0123456789abcdef0123456789abcdef01234567",
    )
}
