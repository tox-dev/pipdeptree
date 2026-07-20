use std::ffi::OsStr;
use std::fs;
use std::path::Path;

use _pipdeptree::{Application, ProcessError, ProcessOutput};
use pyo3::ffi::c_str;
use pyo3::prelude::PyModule;
use pyo3::types::PyAnyMethods as _;
use rstest::rstest;

use super::common::{
    MockProcesses, PackageSite, execute_with_runner, process_output, stdout, with_python,
};

#[test]
fn queries_selected_interpreters() {
    let site = PackageSite::new();
    site.write("demo-1.dist-info", "Name: demo\nVersion: 1\n");
    let interpreter = site.path().join("python");
    let mut processes = MockProcesses::new();
    let info = interpreter_info(
        &[site.path()],
        &interpreter,
        site.path(),
        site.path(),
        site.path(),
    );
    processes
        .expect_run()
        .withf(move |request| request.program == interpreter.as_os_str())
        .return_once(move |_| Ok(process_output(info)));

    with_python(|python| {
        let output = Application::new(&processes).run(
            python,
            &[
                "--python",
                site.path().join("python").to_str().unwrap(),
                "--json",
            ]
            .map(ToString::to_string),
            false,
            true,
        );

        assert_eq!(
            (
                output.code,
                stdout(&output).contains("\"package_name\": \"demo\""),
                output.stderr.contains("(resolved python:"),
            ),
            (0, true, false)
        );
    });
}

#[cfg(unix)]
#[test]
fn queries_interpreters_reached_through_symlinks() {
    let site = PackageSite::new();
    site.write("demo-1.dist-info", "Name: demo\nVersion: 1\n");
    let interpreter = site.path().join("python");
    let info = interpreter_info(
        &[site.path()],
        &interpreter,
        site.path(),
        site.path(),
        site.path(),
    );
    let mut processes = MockProcesses::new();
    let program = interpreter.clone();
    processes
        .expect_run()
        .withf(move |request| request.program == program.as_os_str())
        .times(1)
        .return_once(move |_| Ok(process_output(info)));

    with_python(|python| {
        let executable: String = python
            .import("sys")
            .unwrap()
            .getattr("executable")
            .unwrap()
            .extract()
            .unwrap();
        std::os::unix::fs::symlink(executable, &interpreter).unwrap();

        let output = execute_with_runner(
            &processes,
            python,
            &["--python", interpreter.to_str().unwrap(), "--json"],
            false,
        );

        assert_eq!(
            (
                output.code,
                stdout(&output).contains("\"package_name\": \"demo\""),
                output.stderr.as_str(),
            ),
            (0, true, "")
        );
    });
}

#[test]
fn reports_invalid_current_interpreter_data() {
    with_python(|python| {
        let json = PyModule::import(python, "json").unwrap();
        let original = json.getattr("dumps").unwrap().unbind();
        let invalid = python
            .eval(c_str!("lambda value: '{'"), None, None)
            .unwrap();
        json.setattr("dumps", invalid).unwrap();

        let output = execute_with_runner(
            &_pipdeptree::SystemProcessRunner,
            python,
            &[
                "--path",
                tempfile::tempdir().unwrap().path().to_str().unwrap(),
            ],
            false,
        );

        json.setattr("dumps", original).unwrap();
        assert_eq!(
            (output.code, output.stderr.contains("EOF while parsing")),
            (1, true)
        );
    });
}

#[rstest]
#[case::process(ProcessError::NotFound, "command not found")]
#[case::timeout(ProcessError::TimedOut, "command timed out")]
fn reports_interpreter_process_errors(#[case] error: ProcessError, #[case] expected: &str) {
    let directory = tempfile::tempdir().unwrap();
    let interpreter = directory.path().join("python");
    let mut processes = MockProcesses::new();
    processes.expect_run().return_once(move |_| Err(error));

    with_python(|python| {
        let output = execute_with_runner(
            &processes,
            python,
            &["--python", interpreter.to_str().unwrap()],
            false,
        );

        assert_eq!(
            (output.code, output.stderr),
            (
                1,
                format!("Failed to query custom interpreter: {expected}\n"),
            )
        );
    });
}

#[rstest]
#[case::status(
    Ok(ProcessOutput {
        success: false,
        stdout: Vec::new(),
        stderr: Vec::new(),
    }),
    "Failed to query custom interpreter\n"
)]
#[case::json(
    Ok(process_output("{")),
    "EOF while parsing an object at line 1 column 1\n"
)]
fn reports_invalid_interpreter_output(
    #[case] result: Result<ProcessOutput, ProcessError>,
    #[case] expected: &str,
) {
    let directory = tempfile::tempdir().unwrap();
    let interpreter = directory.path().join("python");
    let mut processes = MockProcesses::new();
    processes.expect_run().return_once(move |_| result);

    with_python(|python| {
        let output = execute_with_runner(
            &processes,
            python,
            &["--python", interpreter.to_str().unwrap()],
            false,
        );

        assert_eq!((output.code, output.stderr.as_str()), (1, expected));
    });
}

#[test]
fn reports_missing_automatic_environment() {
    let mut processes = MockProcesses::new();
    processes
        .expect_run()
        .withf(|request| request.program == OsStr::new("poetry"))
        .return_once(|_| Err(ProcessError::NotFound));

    temp_env::with_vars(
        [
            ("VIRTUAL_ENV", None::<&str>),
            ("CONDA_PREFIX", None::<&str>),
        ],
        || {
            with_python(|python| {
                let output = execute_with_runner(&processes, python, &["--python", "auto"], false);

                assert_eq!(
                    (output.code, output.stderr.as_str()),
                    (1, "Unable to detect virtual environment.\n")
                );
            });
        },
    );
}

#[test]
fn ignores_environment_without_an_interpreter() {
    let directory = tempfile::tempdir().unwrap();
    let mut processes = MockProcesses::new();
    processes
        .expect_run()
        .withf(|request| request.program == OsStr::new("poetry"))
        .return_once(|_| Err(ProcessError::NotFound));

    temp_env::with_vars(
        [
            ("VIRTUAL_ENV", Some(directory.path())),
            ("CONDA_PREFIX", None::<&Path>),
        ],
        || {
            with_python(|python| {
                let output = execute_with_runner(&processes, python, &["--python", "auto"], false);

                assert_eq!(
                    (output.code, output.stderr.as_str()),
                    (1, "Unable to detect virtual environment.\n")
                );
            });
        },
    );
}

#[test]
fn detects_pypy_virtual_environments() {
    let site = PackageSite::new();
    site.write("demo-1.dist-info", "Name: demo\nVersion: 1\n");
    let executable = site
        .path()
        .join(if cfg!(windows) { "Scripts" } else { "bin" })
        .join(format!("pypy{}", std::env::consts::EXE_SUFFIX));
    fs::create_dir_all(executable.parent().unwrap()).unwrap();
    fs::write(&executable, "").unwrap();
    let info = interpreter_info(
        &[site.path()],
        &executable,
        site.path(),
        site.path(),
        site.path(),
    );
    let mut processes = MockProcesses::new();
    processes
        .expect_run()
        .withf(move |request| request.program == executable.as_os_str())
        .return_once(move |_| Ok(process_output(info)));

    temp_env::with_vars(
        [
            ("VIRTUAL_ENV", Some(site.path())),
            ("CONDA_PREFIX", None::<&Path>),
        ],
        || {
            with_python(|python| {
                let sys = python.import("sys").unwrap();
                let implementation = sys.getattr("implementation").unwrap();
                let original_name = implementation.getattr("name").unwrap();
                implementation.setattr("name", "pypy").unwrap();

                let output = execute_with_runner(&processes, python, &["--python", "auto"], false);

                implementation.setattr("name", original_name).unwrap();
                assert_eq!(
                    (
                        output.code,
                        stdout(&output).contains("demo==1"),
                        output.stderr.as_str(),
                    ),
                    (0, true, "")
                );
            });
        },
    );
}

#[test]
fn detects_poetry_environment() {
    let site = PackageSite::new();
    site.write("demo-1.dist-info", "Name: demo\nVersion: 1\n");
    let site_path = site.path().to_str().unwrap();
    let mut processes = MockProcesses::new();

    temp_env::with_vars(
        [
            ("VIRTUAL_ENV", None::<&str>),
            ("CONDA_PREFIX", None::<&str>),
        ],
        || {
            with_python(|python| {
                let path = python.import("sys").unwrap().getattr("path").unwrap();
                path.call_method1("insert", (0, site_path)).unwrap();
                let executable: String = python
                    .import("sys")
                    .unwrap()
                    .getattr("executable")
                    .unwrap()
                    .extract()
                    .unwrap();
                processes
                    .expect_run()
                    .withf(|request| request.program == OsStr::new("poetry"))
                    .return_once(move |_| Ok(process_output(format!("{executable}\n"))));

                let output = execute_with_runner(&processes, python, &["--json"], false);

                path.call_method1("remove", (site_path,)).unwrap();
                assert_eq!(
                    (
                        output.code,
                        stdout(&output).contains("\"package_name\": \"demo\""),
                    ),
                    (0, true)
                );
            });
        },
    );
}

#[rstest]
#[case::virtual_environment("VIRTUAL_ENV")]
#[case::conda("CONDA_PREFIX")]
fn detects_environment_variables(#[case] variable: &str) {
    let site = PackageSite::new();
    site.write("demo-1.dist-info", "Name: demo\nVersion: 1\n");
    let executable = site
        .path()
        .join(if cfg!(windows) && variable == "VIRTUAL_ENV" {
            "Scripts"
        } else if cfg!(unix) {
            "bin"
        } else {
            ""
        })
        .join(format!("python{}", std::env::consts::EXE_SUFFIX));
    fs::create_dir_all(executable.parent().unwrap()).unwrap();
    fs::write(&executable, "").unwrap();
    let info = interpreter_info(
        &[site.path()],
        &executable,
        site.path(),
        site.path(),
        site.path(),
    );
    let mut processes = MockProcesses::new();
    processes
        .expect_run()
        .withf(move |request| request.program == executable.as_os_str())
        .return_once(move |_| Ok(process_output(info)));

    temp_env::with_vars(
        [
            ("VIRTUAL_ENV", None::<&Path>),
            ("CONDA_PREFIX", None::<&Path>),
            (variable, Some(site.path())),
        ],
        || {
            with_python(|python| {
                let output = Application::new(&processes).run(
                    python,
                    &["--python", "auto", "--json"].map(ToString::to_string),
                    false,
                    true,
                );

                assert_eq!(
                    (
                        output.code,
                        stdout(&output).contains("\"package_name\": \"demo\""),
                        output.stderr.contains("(resolved python:"),
                    ),
                    (0, true, true)
                );
            });
        },
    );
}

#[test]
fn rejects_invalid_marker_environment() {
    let site = PackageSite::new();
    let interpreter = site.path().join("python");
    let mut info = serde_json::from_slice::<serde_json::Value>(&interpreter_info(
        &[site.path()],
        &interpreter,
        site.path(),
        site.path(),
        site.path(),
    ))
    .unwrap();
    info["marker"]["python_version"] = "invalid".into();
    let mut processes = MockProcesses::new();
    processes
        .expect_run()
        .return_once(move |_| Ok(process_output(serde_json::to_vec(&info).unwrap())));

    with_python(|python| {
        let output = execute_with_runner(
            &processes,
            python,
            &["--python", interpreter.to_str().unwrap()],
            false,
        );

        assert_eq!((output.code, output.stderr.is_empty()), (1, false));
    });
}

#[rstest]
#[case::local("--local-only", "local", "base")]
#[case::user("--user-only", "user", "local")]
fn filters_interpreter_paths(#[case] flag: &str, #[case] included: &str, #[case] excluded: &str) {
    let directory = tempfile::tempdir().unwrap();
    let local = directory.path().join("local");
    let base = directory.path().join("base");
    let user = directory.path().join("user");
    for (path, name) in [(&local, "local"), (&base, "base"), (&user, "user")] {
        fs::create_dir(path).unwrap();
        write_package(path, name);
    }
    let interpreter = directory.path().join("python");
    let info = interpreter_info(
        &[local.as_path(), base.as_path(), user.as_path()],
        &interpreter,
        &local,
        &base,
        &user,
    );
    let mut processes = MockProcesses::new();
    processes
        .expect_run()
        .return_once(move |_| Ok(process_output(info)));

    with_python(|python| {
        let output = execute_with_runner(
            &processes,
            python,
            &["--python", interpreter.to_str().unwrap(), flag, "--freeze"],
            false,
        );

        assert_eq!(
            (
                stdout(&output).contains(&format!("{included}==1")),
                stdout(&output).contains(&format!("{excluded}==1")),
            ),
            (true, false)
        );
    });
}

#[test]
fn filters_non_venv_interpreter_paths() {
    let directory = tempfile::tempdir().unwrap();
    let local = directory.path().join("local");
    let user = directory.path().join("user");
    for (path, name) in [(&local, "local"), (&user, "user")] {
        fs::create_dir(path).unwrap();
        write_package(path, name);
    }
    let interpreter = directory.path().join("python");
    let info = interpreter_info(
        &[local.as_path(), user.as_path()],
        &interpreter,
        &local,
        &local,
        &user,
    );
    let mut processes = MockProcesses::new();
    processes
        .expect_run()
        .return_once(move |_| Ok(process_output(info)));

    with_python(|python| {
        let output = execute_with_runner(
            &processes,
            python,
            &[
                "--python",
                interpreter.to_str().unwrap(),
                "--local-only",
                "--freeze",
            ],
            false,
        );

        assert_eq!(
            (
                stdout(&output).contains("local==1"),
                stdout(&output).contains("user==1"),
            ),
            (true, false)
        );
    });
}

fn write_package(path: &Path, name: &str) {
    let metadata = path.join(format!("{name}-1.dist-info"));
    fs::create_dir(metadata).unwrap();
    fs::write(
        path.join(format!("{name}-1.dist-info/METADATA")),
        format!("Name: {name}\nVersion: 1\n"),
    )
    .unwrap();
}

fn interpreter_info(
    paths: &[&Path],
    executable: &Path,
    prefix: &Path,
    base_prefix: &Path,
    user_site: &Path,
) -> Vec<u8> {
    serde_json::to_vec(&serde_json::json!({
        "paths": paths,
        "executable": executable,
        "prefix": prefix,
        "base_prefix": base_prefix,
        "user_site": user_site,
        "marker": {
            "implementation_name": "cpython",
            "implementation_version": "3.14.0",
            "os_name": "posix",
            "platform_machine": "arm64",
            "platform_python_implementation": "CPython",
            "platform_release": "1",
            "platform_system": "Darwin",
            "platform_version": "1",
            "python_full_version": "3.14.0",
            "python_version": "3.14",
            "sys_platform": "darwin",
        },
    }))
    .unwrap()
}
