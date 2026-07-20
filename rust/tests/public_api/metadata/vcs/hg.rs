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
#[case::missing_hg(Err(ProcessError::NotFound), None, false)]
#[case::timed_out_hg(Err(ProcessError::TimedOut), None, true)]
#[case::empty_commit(
    Ok(process_output("https://example.com/repo")),
    Some(Ok(process_output(""))),
    true
)]
#[case::failed_commit(
    Ok(process_output("https://example.com/repo")),
    Some(Ok(ProcessOutput { success: false, stdout: Vec::new(), stderr: Vec::new() })),
    true
)]
#[case::missing_commit(
    Ok(process_output("https://example.com/repo")),
    Some(Err(ProcessError::NotFound)),
    false
)]
fn reports_hg_failures(
    #[case] remote: Result<ProcessOutput, ProcessError>,
    #[case] commit: Option<Result<ProcessOutput, ProcessError>>,
    #[case] comments: bool,
) {
    let repository = tempfile::tempdir().unwrap();
    fs::create_dir(repository.path().join(".hg")).unwrap();
    let site = editable_site(repository.path());
    let mut processes = MockProcesses::new();
    expect_no_git(&mut processes, repository.path());
    expect_process(
        &mut processes,
        "hg",
        &["showconfig", "paths.default"],
        remote,
    );
    if let Some(commit) = commit {
        expect_process(
            &mut processes,
            "hg",
            &["parents", "--template={node}"],
            commit,
        );
    }

    let frozen = freeze(&site, &processes);

    assert_eq!(
        (
            frozen.contains("Editable hg install with no remote"),
            frozen.starts_with("-e "),
        ),
        (comments, !comments)
    );
}

#[rstest]
#[case::absolute(HgRemote::Absolute, "-e hg+file://")]
#[case::missing_absolute(HgRemote::MissingAbsolute, "-e hg+file://")]
#[case::windows(HgRemote::Value(r"C:\missing"), r"-e hg+C:\missing")]
#[case::prefixed(HgRemote::Value("hg:https://example.com/repo"), "-e hg:https://")]
fn normalizes_hg_remotes(#[case] source: HgRemote, #[case] expected: &str) {
    let repository = tempfile::tempdir().unwrap();
    fs::create_dir(repository.path().join(".hg")).unwrap();
    let remote = match source {
        HgRemote::Absolute => repository.path().to_string_lossy().into_owned(),
        HgRemote::MissingAbsolute => repository
            .path()
            .join("missing")
            .to_string_lossy()
            .into_owned(),
        HgRemote::Value(value) => value.to_string(),
    };
    let site = editable_site(repository.path());
    let mut processes = MockProcesses::new();
    expect_no_git(&mut processes, repository.path());
    expect_process(
        &mut processes,
        "hg",
        &["showconfig", "paths.default"],
        Ok(process_output(remote)),
    );
    expect_process(
        &mut processes,
        "hg",
        &["parents", "--template={node}"],
        Ok(process_output("abc")),
    );

    assert!(freeze(&site, &processes).starts_with(expected));
}

#[derive(Clone, Copy)]
enum HgRemote {
    Absolute,
    MissingAbsolute,
    Value(&'static str),
}
