use std::fs;
use std::path::{Path, PathBuf};

use _pipdeptree::{Execution, ProcessRunner, SystemProcessRunner};

use super::common::{PackageSite, execute_with_runner, with_python};

mod graphs;
mod json;
mod summary;
mod text;

fn render_site() -> PackageSite {
    let site = PackageSite::new();
    site.write(
        "root-1.dist-info",
        concat!(
            "Name: root\n",
            "Version: 1\n",
            "Requires-Dist: child>=2\n",
            "Requires-Dist: unique[feature]\n",
            "Requires-Dist: missing\n",
            "Classifier: first\n",
            "Classifier: second\n",
            "License-Expression: GPL-3.0\n",
            "Requires-Python: >=3.11,<4\n",
        ),
    );
    site.write(
        "unique-1.dist-info",
        concat!(
            "Name: unique\n",
            "Version: 1\n",
            "Requires-Dist: leaf; extra == 'feature'\n",
            "Provides-Extra: feature\n",
        ),
    );
    site.write("leaf-1.dist-info", "Name: leaf\nVersion: 1\n");
    site.write("child-1.dist-info", "Name: child\nVersion: 1\n");
    site.write(
        "other-1.dist-info",
        "Name: other\nVersion: 1\nRequires-Dist: child\n",
    );
    site.write("graph-1.dist-info", "Name: graph\nVersion: 1\n");
    site
}

fn execute(site: &PackageSite, args: &[&str]) -> Execution {
    execute_with(&SystemProcessRunner, site, args, false)
}

fn execute_with(
    processes: &dyn ProcessRunner,
    site: &PackageSite,
    args: &[&str],
    color: bool,
) -> Execution {
    with_python(|python| {
        execute_with_runner(
            processes,
            python,
            &["--path", site.path().to_str().unwrap(), "--warn", "silence"]
                .into_iter()
                .chain(args.iter().copied())
                .collect::<Vec<_>>(),
            color,
        )
    })
}

fn lock_file(content: &str) -> (tempfile::TempDir, PathBuf) {
    let directory = tempfile::tempdir().unwrap();
    let path = directory.path().join("pylock.toml");
    fs::write(&path, content).unwrap();
    (directory, path)
}

fn sized_site(bytes: u64) -> PackageSite {
    let site = PackageSite::new();
    let metadata = site.write("demo-1.dist-info", "Name: demo\nVersion: 1\n");
    let data = site.path().join("data.bin");
    fs::File::create(&data).unwrap().set_len(bytes).unwrap();
    fs::write(metadata.join("RECORD"), "data.bin,,\n").unwrap();
    site
}

fn text(output: &Execution) -> &str {
    std::str::from_utf8(&output.stdout).unwrap()
}

fn path(path: &Path) -> &str {
    path.to_str().unwrap()
}
