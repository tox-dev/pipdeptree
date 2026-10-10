use std::ffi::{CStr, OsString};
use std::fs;
use std::path::{Path, PathBuf};
use std::sync::{Mutex, MutexGuard, Once, PoisonError};

use _pipdeptree::{
    Application, Execution, ProcessError, ProcessOutput, ProcessRequest, ProcessRunner,
};
use pyo3::PyResult;
use pyo3::Python;
use pyo3::ffi::c_str;
use pyo3::types::{PyAnyMethods as _, PyDict, PyDictMethods as _};
use rstest::fixture;
use tempfile::{TempDir, tempdir};

static PYTHON_LOCK: Mutex<()> = Mutex::new(());
static RESOLVER: Once = Once::new();

pub const VERSION: &str = env!("PIPDEPTREE_VERSION");

mockall::mock! {
    pub Processes {}

    impl ProcessRunner for Processes {
        fn run(&self, request: &ProcessRequest) -> Result<ProcessOutput, ProcessError>;
    }
}

#[fixture]
pub fn package_site() -> PackageSite {
    let site = PackageSite::new();
    site.write(
        "root-1.dist-info",
        concat!(
            "Name: root\n",
            "Version: 1\n",
            "Requires-Dist: child>=1\n",
            "Requires-Dist: optional; extra == 'feature'\n",
            "Provides-Extra: feature\n",
            "License-Expression: MIT\n",
            "Requires-Python: >=3.10\n",
        ),
    );
    site.write(
        "child-1.dist-info",
        "Name: child\nVersion: 1\nLicense: BSD-3-Clause\n",
    );
    site.write("optional-1.dist-info", "Name: optional\nVersion: 1\n");
    site.write("orphan-1.dist-info", "Name: orphan\nVersion: 1\n");
    site
}

pub fn execute(args: &[&str]) -> Execution {
    with_python(|python| execute_with_python(python, args))
}

pub fn execute_in(site: &PackageSite, args: &[&str]) -> Execution {
    execute(
        &["--path", site.path().to_str().unwrap(), "--warn", "silence"]
            .into_iter()
            .chain(args.iter().copied())
            .collect::<Vec<_>>(),
    )
}

pub fn stdout(output: &Execution) -> &str {
    std::str::from_utf8(&output.stdout).unwrap()
}

pub fn process_output(stdout: impl Into<Vec<u8>>) -> ProcessOutput {
    ProcessOutput {
        success: true,
        stdout: stdout.into(),
        stderr: Vec::new(),
    }
}

pub fn expect_process(
    processes: &mut MockProcesses,
    program: &str,
    args: &[&str],
    result: Result<ProcessOutput, ProcessError>,
) {
    let program = OsString::from(program);
    let args = args.iter().map(OsString::from).collect::<Vec<_>>();
    processes
        .expect_run()
        .withf(move |request| request.program == program && request.args == args)
        .times(1)
        .return_once(move |_| result);
}

pub fn execute_with_python(python: Python<'_>, args: &[&str]) -> Execution {
    Application::new(&_pipdeptree::SystemProcessRunner).run(
        python,
        &args.iter().map(ToString::to_string).collect::<Vec<_>>(),
        false,
        false,
    )
}

pub fn execute_with_runner(
    processes: &dyn ProcessRunner,
    python: Python<'_>,
    args: &[&str],
    color: bool,
) -> Execution {
    Application::new(processes).run(
        python,
        &args.iter().map(ToString::to_string).collect::<Vec<_>>(),
        color,
        false,
    )
}

pub fn install_resolver(python: Python<'_>, capture: &Path) -> PyResult<()> {
    // create_autospec has to see the real function, so the patch happens once per process; each
    // test then re-points the capture file the stub writes the generated project to.
    let mut installed = Ok(());
    RESOLVER.call_once(|| installed = patch_resolver(python));
    installed?;
    let locals = PyDict::new(python);
    locals.set_item("capture", capture)?;
    python.run(
        c_str!("import nab_project.resolve\nnab_project.resolve.capture = capture\n"),
        Some(&locals),
        Some(&locals),
    )
}

fn patch_resolver(python: Python<'_>) -> PyResult<()> {
    python.run(RESOLVER_STUB, None, None)
}

const RESOLVER_STUB: &CStr = c_str!(
    r#"
from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from unittest.mock import create_autospec

from packaging.version import Version
from nab_index.transport import AsyncHttpTransport
from nab_project.declarations import DependencyDeclaration
from nab_project.inputs import ResolveInputs
from nab_project.lockfile import TargetLock
from nab_project.resolve import ResolveResult, TargetResult
from nab_provider.target import ResolveTarget
import nab_project.resolve as resolve_module

def resolved(
    path: Path,
    transport: AsyncHttpTransport,
    *,
    targets: Sequence[ResolveTarget],
    inputs: ResolveInputs,
    include_dependency_requirements: bool,
    cache_dir: Path,
) -> ResolveResult:
    assert include_dependency_requirements
    assert isinstance(cache_dir, Path)
    resolve_module.last_cache_dir = cache_dir
    source = path.read_text()
    chain = '"chain"' in source
    child_requirements = (
        DependencyDeclaration(
            requirement_text="child>=1",
            dependency_specifier=">=1",
            parent_name="parent",
            dependency_name="child",
        ),
    )
    if '"parent[feature]"' in source or chain:
        condition = 'extra == "feature" or extra == "other"' if chain else 'extra == "feature"'
        child_requirements += (
            DependencyDeclaration(
                requirement_text=f"child[socks]<3; {condition}",
                dependency_specifier="<3",
                parent_name="parent",
                dependency_name="child",
                dependency_extras=("socks",),
                requirement_condition=condition,
                required_for_parent_extras=("feature", "other") if chain else ("feature",),
            ),
        )
    indexes = [(index.name, index.url) for index in inputs.indexes]
    text = source + "\n--- indexes ---\n" + repr(indexes)
    Path(resolve_module.capture).write_text(text)
    target = targets[0]
    pins = {"parent": Version("1"), "child": Version("2")}
    dependencies = {"parent": ("child", "external")}
    declarations = {
        "parent": {
            "child": child_requirements,
            "external": () if '"parent[empty]"' in source else (
                DependencyDeclaration(
                    requirement_text="external",
                    dependency_specifier="",
                    parent_name="parent",
                    dependency_name="external",
                ),
            ),
        },
    }
    if chain:
        pins.update(chain=Version("1"), other=Version("1"), plain=Version("1"))
        dependencies.update(chain=("parent",), other=("parent",), plain=("parent",))
        declarations.update(
            chain={
                "parent": (
                    DependencyDeclaration(
                        requirement_text="parent[feature]",
                        dependency_specifier="",
                        parent_name="chain",
                        dependency_name="parent",
                        dependency_extras=("feature",),
                    ),
                ),
            },
            other={
                "parent": (
                    DependencyDeclaration(
                        requirement_text="parent[other]",
                        dependency_specifier="",
                        parent_name="other",
                        dependency_name="parent",
                        dependency_extras=("other",),
                    ),
                ),
            },
            plain={
                "parent": (
                    DependencyDeclaration(
                        requirement_text="parent",
                        dependency_specifier="",
                        parent_name="plain",
                        dependency_name="parent",
                    ),
                ),
            },
        )
    return ResolveResult(
        targets=(target,),
        target_results=[
            TargetResult(
                target=target,
                success=True,
                pins=pins,
                lock=TargetLock(
                    target=target,
                    pins={},
                    dependencies=dependencies,
                    dependency_requirements=declarations,
                ),
            )
        ],
    )

resolve_module.resolve_for_targets = create_autospec(
    resolve_module.resolve_for_targets,
    side_effect=resolved,
)
"#
);

pub fn with_python<Result>(test: impl FnOnce(Python<'_>) -> Result) -> Result {
    let _guard = python_lock();
    Python::initialize();
    Python::attach(|python| {
        if let Some(packages) = python_packages() {
            let packages = packages.to_str().unwrap();
            let path = python.import("sys").unwrap().getattr("path").unwrap();
            if !path.contains(packages).unwrap() {
                path.call_method1("insert", (0, packages)).unwrap();
            }
        }
        test(python)
    })
}

fn python_lock() -> MutexGuard<'static, ()> {
    PYTHON_LOCK.lock().unwrap_or_else(PoisonError::into_inner)
}

fn python_packages() -> Option<PathBuf> {
    let root = Path::new(env!("CARGO_MANIFEST_DIR"));
    for path in [
        root.join(".tox/rust/site-packages"),
        root.join(".tox/3.14/Lib/site-packages"),
    ] {
        if path.is_dir() {
            return Some(path);
        }
    }
    fs::read_dir(root.join(".tox/3.14/lib"))
        .ok()?
        .filter_map(Result::ok)
        .map(|entry| entry.path().join("site-packages"))
        .find(|path| path.is_dir())
}

pub struct PackageSite {
    directory: TempDir,
}

impl PackageSite {
    pub fn new() -> Self {
        Self {
            directory: tempdir().unwrap(),
        }
    }

    pub fn path(&self) -> &Path {
        self.directory.path()
    }

    pub fn write(&self, directory: &str, metadata: &str) -> PathBuf {
        let path = self.path().join(directory);
        fs::create_dir(&path).unwrap();
        fs::write(path.join("METADATA"), metadata).unwrap();
        path
    }

    pub fn write_file(&self, path: impl AsRef<Path>, content: &str) {
        fs::write(self.path().join(path), content).unwrap();
    }
}
