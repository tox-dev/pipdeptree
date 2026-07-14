use _pipdeptree::install_python_module;
use pyo3::types::{PyAnyMethods as _, PyDict, PyDictMethods as _, PyList, PyModule};
use pyo3::{Bound, Python};

use super::common::{PackageSite, with_python};

#[test]
fn reports_python_extension_metadata() {
    with_python(|python| {
        let module = extension(python);

        assert_eq!(
            (
                module
                    .getattr("engine")
                    .unwrap()
                    .call0()
                    .unwrap()
                    .extract::<String>()
                    .unwrap(),
                module
                    .getattr("version")
                    .unwrap()
                    .call0()
                    .unwrap()
                    .extract::<String>()
                    .unwrap(),
            ),
            ("rust".to_string(), "4.0.0".to_string())
        );
    });
}

#[test]
fn executes_through_python_extension() {
    let directory = tempfile::tempdir().unwrap();

    with_python(|python| {
        let module = extension(python);
        let args = PyList::new(
            python,
            [
                "--path",
                directory.path().to_str().unwrap(),
                "--warn",
                "silence",
                "--freeze",
            ],
        )
        .unwrap();
        let kwargs = PyDict::new(python);
        kwargs.set_item("color", false).unwrap();
        kwargs.set_item("log_resolved", false).unwrap();
        let execution = module
            .getattr("execute")
            .unwrap()
            .call((args,), Some(&kwargs))
            .unwrap()
            .extract::<(i32, Vec<u8>, String, Option<String>)>()
            .unwrap();

        assert_eq!(execution, (0, b"\n".to_vec(), String::new(), None));
    });
}

#[test]
fn renders_through_python_extension() {
    let directory = tempfile::tempdir().unwrap();

    with_python(|python| {
        let module = extension(python);
        let args = PyList::new(
            python,
            [
                "--path",
                directory.path().to_str().unwrap(),
                "--warn",
                "silence",
                "--freeze",
            ],
        )
        .unwrap();
        let rendered = module
            .getattr("render")
            .unwrap()
            .call1((args,))
            .unwrap()
            .extract::<String>()
            .unwrap();
        assert_eq!(rendered, "\n");
    });
}

#[test]
fn returns_python_render_output_despite_fail_warnings() {
    let site = PackageSite::new();
    site.write(
        "root-1.dist-info",
        "Name: root\nVersion: 1\nRequires-Dist: child>=2\n",
    );
    site.write("child-1.dist-info", "Name: child\nVersion: 1\n");

    with_python(|python| {
        let module = extension(python);
        let args = PyList::new(
            python,
            ["--path", site.path().to_str().unwrap(), "--warn", "fail"],
        )
        .unwrap();
        let rendered = module
            .getattr("render")
            .unwrap()
            .call1((args,))
            .unwrap()
            .extract::<String>()
            .unwrap();

        assert!(rendered.contains("child [required: >=2, installed: 1]"));
    });
}

#[test]
fn reports_python_render_errors() {
    with_python(|python| {
        let module = extension(python);
        let invalid = PyList::new(python, ["--output", "invalid"]).unwrap();

        assert!(
            module
                .getattr("render")
                .unwrap()
                .call1((invalid,))
                .unwrap_err()
                .is_instance_of::<pyo3::exceptions::PyValueError>(python)
        );
    });
}

#[test]
fn returns_empty_python_render_for_unmatched_packages() {
    let directory = tempfile::tempdir().unwrap();

    with_python(|python| {
        let module = extension(python);
        let args = PyList::new(
            python,
            [
                "--path",
                directory.path().to_str().unwrap(),
                "--packages",
                "missing",
            ],
        )
        .unwrap();

        assert_eq!(
            module
                .getattr("render")
                .unwrap()
                .call1((args,))
                .unwrap()
                .extract::<String>()
                .unwrap(),
            ""
        );
    });
}

#[test]
fn rejects_non_string_python_arguments() {
    with_python(|python| {
        let module = extension(python);
        let wrong_type = PyList::new(python, [1]).unwrap();

        assert!(
            module
                .getattr("execute")
                .unwrap()
                .call1((wrong_type,))
                .is_err()
        );
    });
}

fn extension(python: Python<'_>) -> Bound<'_, PyModule> {
    let module = PyModule::new(python, "_rust").unwrap();
    install_python_module(&module).unwrap();
    module
}
