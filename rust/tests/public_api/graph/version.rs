use std::fs;

use pyo3::types::PyAnyMethods as _;
use rstest::rstest;

use super::super::common::{PackageSite, execute, execute_with_python, stdout, with_python};

#[rstest]
fn reports_unknown_versions_without_distribution_metadata(
    #[values(
        "text",
        "rich",
        "freeze",
        "json",
        "json-tree",
        "cyclonedx-json",
        "mermaid",
        "graphviz-dot"
    )]
    format: &str,
    #[values(false, true)] package: bool,
) {
    let site = PackageSite::new();
    site.write(
        "root-1.dist-info",
        "Name: root\nVersion: 1\nRequires-Dist: fallbackdemo>=2\n",
    );
    let marker = site.path().join("imported");
    let source = format!(
        "from pathlib import Path\nPath({:?}).write_text('imported')\n__version__ = '2.0'\n",
        marker.to_str().unwrap(),
    );
    let module = if package {
        let directory = site.path().join("fallbackdemo");
        fs::create_dir(&directory).unwrap();
        directory.join("__init__.py")
    } else {
        site.path().join("fallbackdemo.py")
    };
    fs::write(module, source).unwrap();

    let output = execute(&[
        "--path",
        site.path().to_str().unwrap(),
        "--warn",
        "silence",
        "--output",
        format,
    ]);

    assert_eq!(output.code, 0, "{}", output.stderr);
    assert!(
        !marker.exists(),
        "module version lookup should use distribution metadata"
    );
    assert!(!stdout(&output).contains("2.0"));
    if format == "text" || format == "rich" {
        assert!(stdout(&output).contains("installed: ?"));
        let warned = execute(&["--path", site.path().to_str().unwrap(), "--warn", "fail"]);
        assert_eq!(warned.code, 1);
        assert!(warned.stderr.contains("fallbackdemo"));
        assert!(!marker.exists());
    }
}

#[test]
fn lock_dependencies_ignore_module_versions() {
    let site = PackageSite::new();
    let marker = site.path().join("imported");
    site.write_file(
        "lockfallbackdemo.py",
        &format!(
            "from pathlib import Path\nPath({:?}).write_text('imported')\n__version__ = '2.0'\n",
            marker.to_str().unwrap(),
        ),
    );
    let lock = site.path().join("pylock.toml");
    fs::write(
        &lock,
        "[[packages]]\nname = 'root'\nversion = '1'\ndependencies = [{name = 'lockfallbackdemo'}]\n",
    )
    .unwrap();

    let output = with_python(|python| {
        let path = python.import("sys").unwrap().getattr("path").unwrap();
        path.call_method1("insert", (0, site.path().to_str().unwrap()))
            .unwrap();
        let output = execute_with_python(
            python,
            &[
                "--warn",
                "silence",
                "--json",
                "from-lock",
                lock.to_str().unwrap(),
            ],
        );
        path.call_method1("remove", (site.path().to_str().unwrap(),))
            .unwrap();
        output
    });

    assert_eq!(output.code, 0, "{}", output.stderr);
    assert!(!marker.exists());
    assert!(stdout(&output).contains("lockfallbackdemo"));
    assert!(!stdout(&output).contains("2.0"));
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
