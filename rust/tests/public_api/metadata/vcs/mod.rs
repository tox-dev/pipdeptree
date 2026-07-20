use std::fs;
use std::path::Path;

use _pipdeptree::ProcessError;
use rstest::rstest;

use super::super::common::{
    MockProcesses, PackageSite, execute_with_runner, expect_process, process_output, stdout,
    with_python,
};

mod bzr;
mod git;
mod hg;
mod svn;

#[rstest]
#[case::hg(
    ".hg",
    "hg",
    &["showconfig", "paths.default"],
    "https://example.com/repo",
    &["parents", "--template={node}"],
    "abc",
    "-e hg+https://example.com/repo@abc#egg=demo"
)]
#[case::bzr(
    ".bzr",
    "bzr",
    &["info"],
    "  checkout of branch: https://example.com/repo\n",
    &["revno"],
    "first\n42\n",
    "-e bzr+https://example.com/repo@42#egg=demo"
)]
#[case::svn(
    ".svn",
    "svn",
    &["info", "--xml"],
    "<info><entry revision=\"7\"><url>https://example.com/a&amp;b</url></entry></info>",
    &[],
    "",
    "-e svn+https://example.com/a&b@7#egg=demo"
)]
fn freezes_marker_based_repositories(
    #[case] marker: &str,
    #[case] program: &str,
    #[case] first_args: &[&str],
    #[case] first_stdout: &str,
    #[case] second_args: &[&str],
    #[case] second_stdout: &str,
    #[case] expected: &str,
) {
    let repository = tempfile::tempdir().unwrap();
    fs::create_dir(repository.path().join(marker)).unwrap();
    let site = editable_site(repository.path());
    let mut processes = MockProcesses::new();
    expect_process(
        &mut processes,
        "git",
        &["rev-parse", "--show-toplevel"],
        Err(ProcessError::NotFound),
    );
    expect_process(
        &mut processes,
        program,
        first_args,
        Ok(process_output(first_stdout)),
    );
    if !second_args.is_empty() {
        expect_process(
            &mut processes,
            program,
            second_args,
            Ok(process_output(second_stdout)),
        );
    }

    assert_eq!(freeze(&site, &processes), format!("{expected}\n"));
}

#[test]
fn freezes_editables_without_version_control() {
    let repository = tempfile::tempdir().unwrap();
    let site = editable_site(repository.path());
    let mut processes = MockProcesses::new();
    expect_process(
        &mut processes,
        "git",
        &["rev-parse", "--show-toplevel"],
        Err(ProcessError::NotFound),
    );

    assert_eq!(
        freeze(&site, &processes),
        format!(
            "# Editable install with no version control (demo==1)\n-e {}/\n",
            repository.path().display()
        )
    );
}

#[test]
fn freezes_missing_editable_locations() {
    let directory = tempfile::tempdir().unwrap();
    let location = directory.path().join("missing");
    let site = editable_site(&location);
    let mut processes = MockProcesses::new();
    expect_no_git(&mut processes, &location);

    assert_eq!(
        freeze(&site, &processes),
        format!(
            "# Editable install with no version control (demo==1)\n-e {}/\n",
            location.display()
        )
    );
}

fn editable_site(location: &Path) -> PackageSite {
    let site = PackageSite::new();
    let metadata = site.write("demo-1.dist-info", "Name: demo\nVersion: 1\n");
    fs::write(
        metadata.join("direct_url.json"),
        serde_json::to_vec(&serde_json::json!({
            "url": url::Url::from_directory_path(location).unwrap(),
            "dir_info": {"editable": true},
        }))
        .unwrap(),
    )
    .unwrap();
    site
}

fn freeze(site: &PackageSite, processes: &MockProcesses) -> String {
    with_python(|python| {
        let output = execute_with_runner(
            processes,
            python,
            &[
                "--path",
                site.path().to_str().unwrap(),
                "--warn",
                "silence",
                "--freeze",
            ],
            false,
        );
        stdout(&output).to_string()
    })
}

fn expect_git_root(processes: &mut MockProcesses, repository: &Path) {
    expect_process(
        processes,
        "git",
        &["rev-parse", "--show-toplevel"],
        Ok(process_output(repository.to_string_lossy().into_owned())),
    );
}

fn expect_no_git(processes: &mut MockProcesses, location: &Path) {
    let location = location.to_path_buf();
    processes
        .expect_run()
        .withf(move |request| {
            request.program == "git"
                && request.args == ["rev-parse", "--show-toplevel"]
                && request.current_dir.as_ref() == Some(&location)
        })
        .times(1)
        .return_once(|_| Err(ProcessError::NotFound));
}
