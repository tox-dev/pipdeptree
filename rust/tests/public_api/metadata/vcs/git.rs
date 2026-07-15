use std::fs;

use _pipdeptree::{ProcessError, ProcessOutput};
use rstest::rstest;

use super::super::super::common::{MockProcesses, expect_process, process_output};
use super::{editable_site, expect_git_root, freeze};

#[test]
fn freezes_editable_git_subdirectories() {
    let repository = tempfile::tempdir().unwrap();
    let project = repository.path().join("packages/demo");
    fs::create_dir_all(&project).unwrap();
    fs::write(project.join("pyproject.toml"), "").unwrap();
    let site = editable_site(&project);
    let mut processes = MockProcesses::new();
    expect_process(
        &mut processes,
        "git",
        &["rev-parse", "--show-toplevel"],
        Ok(process_output(
            repository.path().to_string_lossy().into_owned(),
        )),
    );
    expect_process(
        &mut processes,
        "git",
        &["config", "--get-regexp", r"remote\..*\.url"],
        Ok(process_output(
            "remote.upstream.url git@example.com:owner/repo.git\nremote.origin.url https://example.com/repo\n",
        )),
    );
    expect_process(
        &mut processes,
        "git",
        &["rev-parse", "HEAD"],
        Ok(process_output("a b/c")),
    );

    assert_eq!(
        freeze(&site, &processes),
        "-e git+https://example.com/repo@a%20b/c#egg=demo&subdirectory=packages/demo\n"
    );
}

#[rstest]
#[case::no_remote(
    Ok(process_output("")),
    None,
    "# Editable git install with no remote (demo==1)"
)]
#[case::failed_remote(
    Ok(ProcessOutput { success: false, stdout: Vec::new(), stderr: Vec::new() }),
    None,
    "# Editable git install with no remote (demo==1)"
)]
#[case::missing_git(Err(ProcessError::NotFound), None, "-e ")]
#[case::empty_commit(
    Ok(process_output("remote.origin.url https://example.com/repo")),
    Some(Ok(process_output(""))),
    "# Editable git install with no remote (demo==1)"
)]
#[case::invalid_remote(
    Ok(process_output("remote.origin.url invalid::remote")),
    Some(Ok(process_output("commit"))),
    "# Editable git install (demo==1) with either a deleted local remote or invalid URI:"
)]
#[case::missing_commit(
    Ok(process_output("remote.origin.url https://example.com/repo")),
    Some(Err(ProcessError::NotFound)),
    "-e "
)]
#[case::failed_commit(
    Ok(process_output("remote.origin.url https://example.com/repo")),
    Some(Err(ProcessError::TimedOut)),
    "# Editable git install with no remote (demo==1)"
)]
fn reports_git_failures(
    #[case] remote: Result<ProcessOutput, ProcessError>,
    #[case] commit: Option<Result<ProcessOutput, ProcessError>>,
    #[case] expected: &str,
) {
    let repository = tempfile::tempdir().unwrap();
    let site = editable_site(repository.path());
    let mut processes = MockProcesses::new();
    expect_process(
        &mut processes,
        "git",
        &["rev-parse", "--show-toplevel"],
        Ok(process_output(
            repository.path().to_string_lossy().into_owned(),
        )),
    );
    expect_process(
        &mut processes,
        "git",
        &["config", "--get-regexp", r"remote\..*\.url"],
        remote,
    );
    if let Some(commit) = commit {
        expect_process(&mut processes, "git", &["rev-parse", "HEAD"], commit);
    }

    assert!(freeze(&site, &processes).starts_with(expected));
}

#[rstest]
#[case::absolute(GitRemote::Absolute, "git+file://", true)]
#[case::relative(GitRemote::Relative, "git+file://", true)]
#[case::host(GitRemote::Value("host:path"), "git+ssh://host/path", true)]
#[case::user(
    GitRemote::Value("user_name@host:path"),
    "git+ssh://user_name@host/path",
    true
)]
#[case::host_slash(GitRemote::Value("bad/host:path"), "invalid URI", false)]
#[case::empty_path(GitRemote::Value("host:"), "invalid URI", false)]
#[case::absolute_scp_path(GitRemote::Value("host:/path"), "invalid URI", false)]
#[case::colon_path(GitRemote::Value("host:path:tail"), "invalid URI", false)]
#[case::empty_host(GitRemote::Value(":path"), "invalid URI", false)]
#[case::empty_user(GitRemote::Value("@host:path"), "invalid URI", false)]
#[case::invalid_user(GitRemote::Value("bad-user@host:path"), "invalid URI", false)]
#[case::empty_hostname(GitRemote::Value("user@:path"), "invalid URI", false)]
fn normalizes_git_remotes(#[case] source: GitRemote, #[case] expected: &str, #[case] valid: bool) {
    let repository = tempfile::tempdir().unwrap();
    let remote = match source {
        GitRemote::Absolute => {
            let path = repository.path().join("absolute");
            fs::create_dir(&path).unwrap();
            path.to_string_lossy().into_owned()
        }
        GitRemote::Relative => {
            fs::create_dir(repository.path().join("relative")).unwrap();
            "relative".to_string()
        }
        GitRemote::Value(value) => value.to_string(),
    };
    let site = editable_site(repository.path());
    let mut processes = MockProcesses::new();
    expect_git_root(&mut processes, repository.path());
    expect_process(
        &mut processes,
        "git",
        &["config", "--get-regexp", r"remote\..*\.url"],
        Ok(process_output(format!("remote.upstream.url {remote}"))),
    );
    expect_process(
        &mut processes,
        "git",
        &["rev-parse", "HEAD"],
        Ok(process_output("commit")),
    );

    let frozen = freeze(&site, &processes);

    assert_eq!(
        (frozen.starts_with("-e "), frozen.contains(expected)),
        (valid, true)
    );
}

#[test]
fn omits_git_subdirectory_for_repository_project() {
    let repository = tempfile::tempdir().unwrap();
    fs::write(repository.path().join("pyproject.toml"), "").unwrap();
    let site = editable_site(repository.path());
    let mut processes = MockProcesses::new();
    expect_git_root(&mut processes, repository.path());
    expect_process(
        &mut processes,
        "git",
        &["config", "--get-regexp", r"remote\..*\.url"],
        Ok(process_output("remote.origin.url https://example.com/repo")),
    );
    expect_process(
        &mut processes,
        "git",
        &["rev-parse", "HEAD"],
        Ok(process_output("commit")),
    );

    assert_eq!(
        freeze(&site, &processes),
        "-e git+https://example.com/repo@commit#egg=demo\n"
    );
}

#[derive(Clone, Copy)]
enum GitRemote {
    Absolute,
    Relative,
    Value(&'static str),
}
