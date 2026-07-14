use std::fs;
use std::path::Path;

use _pipdeptree::{ProcessError, ProcessOutput};
use rstest::rstest;

use super::common::{
    MockProcesses, PackageSite, execute_with_runner, expect_process, process_output, stdout,
    with_python,
};

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
fn uses_legacy_subversion_metadata() {
    let repository = tempfile::tempdir().unwrap();
    fs::create_dir(repository.path().join(".svn")).unwrap();
    fs::write(
        repository.path().join(".svn/entries"),
        "10\n\ndir\n12\nhttps://example.com/repo\n",
    )
    .unwrap();
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
        "svn",
        &["info", "--xml"],
        Ok(ProcessOutput {
            success: false,
            stdout: Vec::new(),
            stderr: Vec::new(),
        }),
    );

    assert_eq!(
        freeze(&site, &processes),
        "-e svn+https://example.com/repo@12#egg=demo\n"
    );
}

#[rstest]
#[case::missing(Err(ProcessError::NotFound), None, false)]
#[case::malformed(Ok(process_output("<info>")), None, true)]
#[case::legacy_xml(
    Ok(ProcessOutput { success: false, stdout: Vec::new(), stderr: Vec::new() }),
    Some("<?xml version='1.0'?><wc-entries/>"),
    true
)]
#[case::invalid_utf8(
    Ok(ProcessOutput { success: true, stdout: vec![0xFF], stderr: Vec::new() }),
    None,
    true
)]
fn reports_subversion_failures(
    #[case] result: Result<ProcessOutput, ProcessError>,
    #[case] entries: Option<&str>,
    #[case] comments: bool,
) {
    let repository = tempfile::tempdir().unwrap();
    fs::create_dir(repository.path().join(".svn")).unwrap();
    if let Some(entries) = entries {
        fs::write(repository.path().join(".svn/entries"), entries).unwrap();
    }
    let site = editable_site(repository.path());
    let mut processes = MockProcesses::new();
    expect_no_git(&mut processes, repository.path());
    expect_process(&mut processes, "svn", &["info", "--xml"], result);

    let frozen = freeze(&site, &processes);

    assert_eq!(
        (
            frozen.contains("Editable svn install with no remote"),
            frozen.starts_with("-e "),
        ),
        (comments, !comments)
    );
}

#[test]
fn unescapes_subversion_info() {
    let repository = tempfile::tempdir().unwrap();
    fs::create_dir(repository.path().join(".svn")).unwrap();
    let site = editable_site(repository.path());
    let mut processes = MockProcesses::new();
    expect_no_git(&mut processes, repository.path());
    expect_process(
        &mut processes,
        "svn",
        &["info", "--xml"],
        Ok(process_output(concat!(
            "<info><entry><url>",
            "https://example.com/a&amp;b&lt;c&gt;d&quot;e&apos;f&amp;lt;g",
            "</url></entry></info>",
        ))),
    );

    assert_eq!(
        freeze(&site, &processes),
        "-e svn+https://example.com/a&b<c>d\"e'f&lt;g@#egg=demo\n"
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
