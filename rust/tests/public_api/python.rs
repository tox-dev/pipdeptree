use _pipdeptree::install_python_module;
use pyo3::types::{PyAnyMethods as _, PyDict, PyDictMethods as _, PyList, PyModule};
use pyo3::{Bound, PyResult, Python};

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
        let (rendered, warnings, code) = module
            .getattr("render")
            .unwrap()
            .call1((args,))
            .unwrap()
            .extract::<(String, String, i32)>()
            .unwrap();
        assert_eq!(
            (rendered, warnings, code),
            ("\n".to_string(), String::new(), 0)
        );
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
        let (rendered, warnings, code) = module
            .getattr("render")
            .unwrap()
            .call1((args,))
            .unwrap()
            .extract::<(String, String, i32)>()
            .unwrap();

        assert_eq!(
            (
                rendered.contains("child [required: >=2, installed: 1]"),
                warnings.contains("dependency problems found"),
                code,
            ),
            (true, true, 1)
        );
    });
}

#[test]
fn renders_text_and_mermaid_in_one_run() {
    let site = PackageSite::new();
    site.write(
        "root-1.dist-info",
        "Name: root\nVersion: 1\nRequires-Dist: child\n",
    );
    site.write("child-1.dist-info", "Name: child\nVersion: 1\n");

    with_python(|python| {
        let module = extension(python);
        let render = module.getattr("render_with_mermaid").unwrap();
        let args = PyList::new(
            python,
            ["--path", site.path().to_str().unwrap(), "--warn", "silence"],
        )
        .unwrap();
        let (text, mermaid, _, _) = render
            .call1((args,))
            .unwrap()
            .extract::<(String, String, String, i32)>()
            .unwrap();
        let unmatched_args = PyList::new(
            python,
            [
                "--path",
                site.path().to_str().unwrap(),
                "--packages",
                "nope",
            ],
        )
        .unwrap();
        let unmatched = render
            .call1((unmatched_args,))
            .unwrap()
            .extract::<(String, String, String, i32)>()
            .unwrap();
        let invalid = PyList::new(python, ["--output", "invalid"]).unwrap();

        assert_eq!(
            (
                text.contains("root==1"),
                mermaid.contains("flowchart TD"),
                unmatched,
                render.call1((invalid,)).is_err(),
            ),
            (
                true,
                true,
                (String::new(), String::new(), String::new(), 0),
                true
            )
        );
    });
}

#[test]
fn rejects_binary_python_render_output() {
    let site = PackageSite::new();
    site.write("demo-1.dist-info", "Name: demo\nVersion: 1\n");

    with_python(|python| {
        let module = extension(python);
        let args = PyList::new(
            python,
            [
                "--path",
                site.path().to_str().unwrap(),
                "--graph-output",
                "png",
            ],
        )
        .unwrap();
        let error = module
            .getattr("render")
            .unwrap()
            .call1((args,))
            .unwrap_err();

        assert!(error.to_string().contains("binary graphviz output"));
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
                .extract::<(String, String, i32)>()
                .unwrap(),
            (String::new(), String::new(), 0)
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

#[test]
fn format_flags_translate_render_output_formats() {
    with_python(|python| {
        let module = extension(python);
        let flags = module.getattr("format_flags").unwrap();
        let call = |fmt: &str, summary: bool| -> PyResult<Vec<String>> {
            flags
                .call1((fmt, summary))
                .and_then(|value| value.extract::<Vec<String>>())
        };

        assert_eq!(call("text", false).unwrap(), Vec::<String>::new());
        assert_eq!(call("json", false).unwrap(), ["--json"]);
        assert_eq!(call("json-tree", false).unwrap(), ["--json-tree"]);
        assert_eq!(call("mermaid", false).unwrap(), ["--mermaid"]);
        assert_eq!(call("dot", false).unwrap(), ["--graph-output", "dot"]);
        assert_eq!(
            call("rich", true).unwrap(),
            ["--summary", "--output", "rich"]
        );
        assert_eq!(
            call("json", true).unwrap(),
            ["--summary", "--output", "json"]
        );
        assert_eq!(
            call("text", true).unwrap(),
            ["--summary", "--output", "text"]
        );
        assert!(
            call("png", false)
                .unwrap_err()
                .to_string()
                .contains("binary Graphviz formats")
        );
        assert!(
            call("xml", false)
                .unwrap_err()
                .to_string()
                .contains("unknown output_format")
        );
        assert!(
            call("mermaid", true)
                .unwrap_err()
                .to_string()
                .contains("summary output_format")
        );
    });
}

fn extension(python: Python<'_>) -> Bound<'_, PyModule> {
    let module = PyModule::new(python, "_rust").unwrap();
    install_python_module(&module).unwrap();
    module
}
