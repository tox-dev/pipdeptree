use std::fmt::{Display, Write as _};
use std::fs;
use std::path::{Path, PathBuf};

use _pipdeptree::{Execution, ProcessRunner, SystemProcessRunner};

use super::common::{PackageSite, execute_with_runner, with_python};

mod freeze;
mod graphviz;
mod json;
mod json_tree;
mod mermaid;
mod nesting;
mod rich_text;
mod sbom;
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

fn write_requiring(site: &PackageSite, name: &str, requires: &[impl Display]) {
    let mut metadata = format!("Name: {name}\nVersion: 1\n");
    for child in requires {
        writeln!(metadata, "Requires-Dist: {child}").unwrap();
    }
    site.write(&format!("{name}-1.dist-info"), &metadata);
}

// Each package requires every later one, so the graph has count * (count - 1) / 2 edges and
// 2^(count - 1) paths from the first package to the last.
fn layered_site(count: usize) -> PackageSite {
    let site = PackageSite::new();
    let names = (0..count)
        .map(|index| format!("p{index:02}"))
        .collect::<Vec<_>>();
    for (index, name) in names.iter().enumerate() {
        write_requiring(&site, name, &names[index + 1..]);
    }
    site
}

// a requires x and y, x requires y, and y requires w and x: the first walk into y meets x on
// the path, so the edge y -> x only shows when y is reached through a.
fn crossed_cycle_site() -> PackageSite {
    let site = PackageSite::new();
    write_requiring(&site, "a", &["x", "y"]);
    write_requiring(&site, "w", &[] as &[&str]);
    write_requiring(&site, "x", &["y"]);
    write_requiring(&site, "y", &["w", "x"]);
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
