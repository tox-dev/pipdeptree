use std::fs;

use pyo3::ffi::c_str;
use pyo3::prelude::PyModule;
use pyo3::types::PyAnyMethods as _;
use rstest::rstest;

use super::common::{PackageSite, execute, execute_with_python, stdout, with_python};

#[test]
fn resolves_versions_without_distribution_metadata() {
    let module = tempfile::tempdir().unwrap();
    fs::write(module.path().join("fallbackdemo.py"), "__version__ = '2'\n").unwrap();
    let site = PackageSite::new();
    site.write(
        "root-1.dist-info",
        "Name: root\nVersion: 1\nRequires-Dist: fallbackdemo>=2\n",
    );

    let output = execute(&[
        "--path",
        site.path().to_str().unwrap(),
        "--path",
        module.path().to_str().unwrap(),
        "--warn",
        "fail",
        "--output",
        "rich",
    ]);

    assert_eq!(
        (
            output.code,
            stdout(&output).contains("fallbackdemo required: >=2 installed: 2"),
            output.stderr.as_str(),
        ),
        (0, true, "")
    );
}

#[test]
fn ignores_versions_outside_the_inspected_environment() {
    let module = tempfile::tempdir().unwrap();
    fs::write(module.path().join("hostonlydemo.py"), "__version__ = '9'\n").unwrap();
    let site = PackageSite::new();
    site.write(
        "root-1.dist-info",
        "Name: root\nVersion: 1\nRequires-Dist: hostonlydemo\n",
    );

    let output = with_python(|python| {
        let path = python.import("sys").unwrap().getattr("path").unwrap();
        path.call_method1("insert", (0, module.path().to_str().unwrap()))
            .unwrap();
        let output = execute_with_python(
            python,
            &["--path", site.path().to_str().unwrap(), "--warn", "silence"],
        );
        path.call_method1("remove", (module.path().to_str().unwrap(),))
            .unwrap();
        output
    });

    assert!(
        stdout(&output).contains("hostonlydemo [required: Any, installed: ?]"),
        "host module leaked into the inspected environment: {}",
        stdout(&output)
    );
}

#[test]
fn skips_version_resolution_for_inactive_extras() {
    let module = tempfile::tempdir().unwrap();
    fs::write(
        module.path().join("sideeffectdemo.py"),
        "raise RuntimeError('imported')\n",
    )
    .unwrap();
    let site = PackageSite::new();
    site.write(
        "root-1.dist-info",
        concat!(
            "Name: root\n",
            "Version: 1\n",
            "Requires-Dist: sideeffectdemo; extra == 'feature'\n",
            "Provides-Extra: feature\n",
        ),
    );

    let output = execute(&[
        "--path",
        site.path().to_str().unwrap(),
        "--path",
        module.path().to_str().unwrap(),
        "--warn",
        "silence",
    ]);

    assert_eq!(
        (
            output.code,
            stdout(&output).contains("sideeffectdemo"),
            output.stderr.as_str(),
        ),
        (0, false, "")
    );
}

#[test]
fn resolves_versions_from_distribution_metadata() {
    let module = tempfile::tempdir().unwrap();
    let metadata = module.path().join("indexed-3.dist-info");
    fs::create_dir(&metadata).unwrap();
    fs::write(metadata.join("METADATA"), "Name: indexed\nVersion: 3\n").unwrap();
    let site = PackageSite::new();
    site.write(
        "root-1.dist-info",
        "Name: root\nVersion: 1\nRequires-Dist: indexed>=3\n",
    );

    let output = execute(&[
        "--path",
        site.path().to_str().unwrap(),
        "--path",
        metadata.parent().unwrap().to_str().unwrap(),
        "--warn",
        "fail",
        "--output",
        "rich",
    ]);

    assert_eq!(
        (
            output.code,
            stdout(&output).contains("indexed required: >=3 installed: 3"),
        ),
        (0, true)
    );
}

#[rstest]
#[case::missing_attribute("fallbackmissing", "", None, 0, "installed: ?")]
#[case::import_error(
    "fallbackimporterror",
    "raise RuntimeError('import failed')\n",
    None,
    1,
    "import failed"
)]
#[case::attribute_error(
    "fallbackattributeerror",
    "def __getattr__(name):\n    raise RuntimeError('attribute failed')\n",
    None,
    1,
    "attribute failed"
)]
#[case::non_string(
    "fallbacknonstring",
    "__version__ = object()\n",
    None,
    0,
    "installed: ?"
)]
#[case::nested(
    "fallbacknested",
    "import fallbacknestedvalue\n__version__ = fallbacknestedvalue\n",
    Some(("fallbacknestedvalue", "__version__ = '4'\n")),
    0,
    "installed: 4"
)]
#[case::nested_missing(
    "fallbacknestedmissing",
    "import fallbacknestedmissingvalue\n__version__ = fallbacknestedmissingvalue\n",
    Some(("fallbacknestedmissingvalue", "")),
    0,
    "installed: ?"
)]
#[case::nested_error(
    "fallbacknestederror",
    "import fallbacknestederrorvalue\n__version__ = fallbacknestederrorvalue\n",
    Some((
        "fallbacknestederrorvalue",
        "def __getattr__(name):\n    raise RuntimeError('nested attribute failed')\n"
    )),
    1,
    "nested attribute failed"
)]
fn handles_module_version_fallbacks(
    #[case] name: &str,
    #[case] content: &str,
    #[case] nested: Option<(&str, &str)>,
    #[case] code: i32,
    #[case] expected: &str,
) {
    let module = tempfile::tempdir().unwrap();
    fs::write(module.path().join(format!("{name}.py")), content).unwrap();
    if let Some((nested_name, nested_content)) = nested {
        fs::write(
            module.path().join(format!("{nested_name}.py")),
            nested_content,
        )
        .unwrap();
    }
    let site = PackageSite::new();
    site.write(
        "root-1.dist-info",
        &format!("Name: root\nVersion: 1\nRequires-Dist: {name}\n"),
    );

    let output = with_python(|python| {
        // Nested imports resolve through sys.path, so the fallback module needs both entries.
        let path = python.import("sys").unwrap().getattr("path").unwrap();
        path.call_method1("insert", (0, module.path().to_str().unwrap()))
            .unwrap();
        let output = execute_with_python(
            python,
            &[
                "--path",
                site.path().to_str().unwrap(),
                "--path",
                module.path().to_str().unwrap(),
                "--warn",
                "silence",
                "--output",
                "rich",
            ],
        );
        path.call_method1("remove", (module.path().to_str().unwrap(),))
            .unwrap();
        output
    });

    assert_eq!(
        (
            output.code,
            stdout(&output).contains(expected) || output.stderr.contains(expected),
        ),
        (code, true)
    );
}

#[test]
fn reports_distribution_version_errors() {
    let site = PackageSite::new();
    site.write(
        "root-1.dist-info",
        "Name: root\nVersion: 1\nRequires-Dist: broken_version\n",
    );

    let output = with_python(|python| {
        let machinery = PyModule::import(python, "importlib.machinery").unwrap();
        let finder = machinery.getattr("PathFinder").unwrap();
        let original = finder.getattr("find_spec").unwrap().unbind();
        let failing = python
            .eval(
                c_str!(
                    "lambda *args, **kwargs: (_ for _ in ()).throw(ValueError('version failed'))"
                ),
                None,
                None,
            )
            .unwrap();
        finder.setattr("find_spec", failing).unwrap();
        let output = execute_with_python(python, &["--path", site.path().to_str().unwrap()]);
        finder.setattr("find_spec", original).unwrap();
        output
    });

    assert_eq!(
        (output.code, output.stderr.contains("version failed")),
        (1, true)
    );
}
