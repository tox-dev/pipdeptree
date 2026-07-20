use std::fs;

use _pipdeptree::{ProcessError, ProcessOutput};
use rstest::rstest;

use super::super::super::common::{MockProcesses, expect_process, process_output};
use super::{editable_site, expect_no_git, freeze};

#[rstest]
#[case::empty_remote(Ok(process_output("")), None, true)]
#[case::failed_remote(
    Ok(ProcessOutput { success: false, stdout: Vec::new(), stderr: Vec::new() }),
    None,
    true
)]
#[case::missing_bzr(Err(ProcessError::NotFound), None, false)]
#[case::empty_revision(
    Ok(process_output("parent branch: https://example.com/repo")),
    Some(Ok(process_output(""))),
    true
)]
#[case::failed_revision(
    Ok(process_output("parent branch: https://example.com/repo")),
    Some(Ok(ProcessOutput { success: false, stdout: Vec::new(), stderr: Vec::new() })),
    true
)]
#[case::missing_revision(
    Ok(process_output("parent branch: https://example.com/repo")),
    Some(Err(ProcessError::NotFound)),
    false
)]
fn reports_bzr_failures(
    #[case] remote: Result<ProcessOutput, ProcessError>,
    #[case] revision: Option<Result<ProcessOutput, ProcessError>>,
    #[case] comments: bool,
) {
    let repository = tempfile::tempdir().unwrap();
    fs::create_dir(repository.path().join(".bzr")).unwrap();
    let site = editable_site(repository.path());
    let mut processes = MockProcesses::new();
    expect_no_git(&mut processes, repository.path());
    expect_process(&mut processes, "bzr", &["info"], remote);
    if let Some(revision) = revision {
        expect_process(&mut processes, "bzr", &["revno"], revision);
    }

    let frozen = freeze(&site, &processes);

    assert_eq!(
        (
            frozen.contains("Editable bzr install with no remote"),
            frozen.starts_with("-e "),
        ),
        (comments, !comments)
    );
}

#[rstest]
#[case::local(true, "-e bzr+file://")]
#[case::prefixed(false, "-e bzr:https://")]
fn normalizes_bzr_remotes(#[case] local: bool, #[case] expected: &str) {
    let repository = tempfile::tempdir().unwrap();
    fs::create_dir(repository.path().join(".bzr")).unwrap();
    let remote = if local {
        repository.path().to_string_lossy().into_owned()
    } else {
        "bzr:https://example.com/repo".to_string()
    };
    let site = editable_site(repository.path());
    let mut processes = MockProcesses::new();
    expect_no_git(&mut processes, repository.path());
    expect_process(
        &mut processes,
        "bzr",
        &["info"],
        Ok(process_output(format!("parent branch: {remote}"))),
    );
    expect_process(&mut processes, "bzr", &["revno"], Ok(process_output("42")));

    assert!(freeze(&site, &processes).starts_with(expected));
}
