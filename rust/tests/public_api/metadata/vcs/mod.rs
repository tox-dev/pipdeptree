use std::fs;
use std::path::Path;

use _pipdeptree::{ProcessError, ProcessOutput};
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
#[case::bzr(
    ".bzr",
    "bzr",
    &["info"],
    "  checkout of branch: https://example.com/repo\n",
    &["revno"],
    "first\n42\n",
    "-e bzr+https://example.com/repo@42#egg=demo"
)]
#[case::bzr_credentials(
    ".bzr",
    "bzr",
    &["info"],
    "  checkout of branch: https://ci:token@example.com/repo\n",
    &["revno"],
    "42\n",
    "-e bzr+https://example.com/repo@42#egg=demo"
)]
#[case::bzr_line_break_and_escape(
    ".bzr",
    "bzr",
    &["info"],
    "  checkout of branch: https://example.com/re po\u{1b}[31m\u{2028}--index-url=https://evil\n",
    &["revno"],
    "42\n",
    "-e bzr+https://example.com/re%20po%1B[31m%E2%80%A8--index-url=https://evil@42#egg=demo"
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

#[rstest]
#[case::svn(".svn", "svn", &["info", "--xml"], "svn")]
#[case::bzr(".bzr", "bzr", &["info"], "bzr")]
#[case::hg(".hg", "hg", &["parents", "--template={node}"], "hg")]
fn reports_timed_out_marker_lookups(
    #[case] marker: &str,
    #[case] program: &str,
    #[case] args: &[&str],
    #[case] vcs: &str,
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
    expect_process(&mut processes, program, args, Err(ProcessError::TimedOut));

    assert_eq!(
        freeze(&site, &processes),
        format!(
            "# Editable {vcs} install whose lookup timed out (demo==1)\n-e {}/\n",
            repository.path().display()
        )
    );
}

#[test]
fn reports_timed_out_git_roots() {
    let repository = tempfile::tempdir().unwrap();
    let site = editable_site(repository.path());
    let mut processes = MockProcesses::new();
    expect_process(
        &mut processes,
        "git",
        &["rev-parse", "--show-toplevel"],
        Err(ProcessError::TimedOut),
    );

    assert_eq!(
        freeze(&site, &processes),
        format!(
            "# Editable VCS install whose lookup timed out (demo==1)\n-e {}/\n",
            repository.path().display()
        )
    );
}

#[test]
fn finds_marker_repositories_after_a_timed_out_git_root() {
    let repository = tempfile::tempdir().unwrap();
    fs::create_dir(repository.path().join(".bzr")).unwrap();
    let site = editable_site(repository.path());
    let mut processes = MockProcesses::new();
    expect_process(
        &mut processes,
        "git",
        &["rev-parse", "--show-toplevel"],
        Err(ProcessError::TimedOut),
    );
    expect_process(
        &mut processes,
        "bzr",
        &["info"],
        Ok(process_output(
            "  checkout of branch: https://example.com/repo\n",
        )),
    );
    expect_process(
        &mut processes,
        "bzr",
        &["revno"],
        Ok(process_output("42\n")),
    );

    assert_eq!(
        freeze(&site, &processes),
        "-e bzr+https://example.com/repo@42#egg=demo\n"
    );
}

#[test]
fn stops_vcs_lookups_after_two_timeouts() {
    let repositories = [(); 3].map(|()| tempfile::tempdir().unwrap());
    let site = PackageSite::new();
    for (index, repository) in repositories.iter().enumerate() {
        write_editable(&site, &format!("p{index}"), repository.path());
    }
    let mut processes = MockProcesses::new();
    processes
        .expect_run()
        .withf(|request| request.program == "git")
        .times(2)
        .returning(|_| Err(ProcessError::TimedOut));

    assert_eq!(
        freeze(&site, &processes),
        format!(
            concat!(
                "# Editable VCS install whose lookup timed out (p0==1)\n-e {}/\n",
                "# Editable VCS install whose lookup timed out (p1==1)\n-e {}/\n",
                "# Editable VCS install whose lookup timed out (p2==1)\n-e {}/\n",
            ),
            repositories[0].path().display(),
            repositories[1].path().display(),
            repositories[2].path().display(),
        )
    );
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

#[rstest]
#[case::no_version_control(
    Err(ProcessError::NotFound),
    None,
    None,
    "# Editable install with no version control (demo==1)"
)]
#[case::no_remote(
    Ok(()),
    Some(Ok(process_output(""))),
    None,
    "# Editable git install with no remote (demo==1)"
)]
#[case::invalid_remote(
    Ok(()),
    Some(Ok(process_output("remote.origin.url invalid::remote"))),
    Some(Ok(process_output("commit"))),
    "# Editable git install (demo==1) with either a deleted local remote or invalid URI:"
)]
#[case::timed_out(
    Err(ProcessError::TimedOut),
    None,
    None,
    "# Editable VCS install whose lookup timed out (demo==1)"
)]
fn freezes_editable_locations_with_backslashes_as_file_urls(
    #[case] root: Result<(), ProcessError>,
    #[case] remote: Option<Result<ProcessOutput, ProcessError>>,
    #[case] commit: Option<Result<ProcessOutput, ProcessError>>,
    #[case] comment: &str,
) {
    let directory = tempfile::tempdir().unwrap();
    let location = directory.path().join(r"C:\proj");
    fs::create_dir(&location).unwrap();
    let site = editable_site(&location);
    let mut processes = MockProcesses::new();
    match root {
        Ok(()) => expect_git_root(&mut processes, &location),
        Err(error) => expect_process(
            &mut processes,
            "git",
            &["rev-parse", "--show-toplevel"],
            Err(error),
        ),
    }
    if let Some(remote) = remote {
        expect_process(
            &mut processes,
            "git",
            &["config", "--get-regexp", r"remote\..*\.url"],
            remote,
        );
    }
    if let Some(commit) = commit {
        expect_process(&mut processes, "git", &["rev-parse", "HEAD"], commit);
    }

    assert_eq!(
        freeze(&site, &processes),
        format!(
            "{comment}\n-e {}\n",
            url::Url::from_file_path(&location).unwrap()
        )
    );
}

fn editable_site(location: &Path) -> PackageSite {
    let site = PackageSite::new();
    write_editable(&site, "demo", location);
    site
}

fn write_editable(site: &PackageSite, name: &str, location: &Path) {
    let metadata = site.write(
        &format!("{name}-1.dist-info"),
        &format!("Name: {name}\nVersion: 1\n"),
    );
    fs::write(
        metadata.join("direct_url.json"),
        serde_json::to_vec(&serde_json::json!({
            "url": url::Url::from_directory_path(location).unwrap(),
            "dir_info": {"editable": true},
        }))
        .unwrap(),
    )
    .unwrap();
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
