use std::ffi::OsString;
use std::fs;
use std::path::Path;

use _pipdeptree::{ProcessError, ProcessOutput};
use rstest::rstest;

use super::super::super::common::{MockProcesses, process_output, write_oversized};
use super::{editable_site, expect_no_git, freeze};

const REMOTE: &str = "[paths]\ndefault = https://example.com/repo\n";

#[rstest]
#[case::plain(REMOTE)]
#[case::compact("[paths]\ndefault=https://example.com/repo")]
#[case::windows_line_endings("[paths]\r\ndefault = https://example.com/repo\r\n")]
#[case::other_sections(
    "[ui]\ndefault = ui\n[paths]\ndefault = https://example.com/repo\n[web]\ndefault = web\n"
)]
#[case::other_paths(
    "[paths]\nupstream = up\ndefault = https://example.com/repo\ndefault:pushurl = push\n# default = no\n"
)]
#[case::last_value("[paths]\ndefault = first\n[paths]\ndefault = https://example.com/repo\n")]
#[case::continuation(
    "[paths]\ndefault = https://example.com/repo\n  --index-url=https://example.com\n"
)]
fn freezes_hg_repositories(#[case] hgrc: &str) {
    let repository = tempfile::tempdir().unwrap();
    write_hgrc(repository.path(), hgrc);

    assert_eq!(
        freeze_hg(repository.path(), Ok(process_output("abc"))),
        "-e hg+https://example.com/repo@abc#egg=demo\n"
    );
}

fn write_hgrc(repository: &Path, content: &str) {
    fs::create_dir_all(repository.join(".hg")).unwrap();
    fs::write(repository.join(".hg/hgrc"), content).unwrap();
}

fn freeze_hg(repository: &Path, commit: Result<ProcessOutput, ProcessError>) -> String {
    let site = editable_site(repository);
    let mut processes = MockProcesses::new();
    expect_no_git(&mut processes, repository);
    processes
        .expect_run()
        .withf(|request| {
            request.program == "hg"
                && request.args == ["parents", "--template={node}"]
                && request.added_environment
                    == [(OsString::from("HGRCSKIPREPO"), OsString::from("1"))]
        })
        .times(1)
        .return_once(move |_| commit);
    freeze(&site, &processes)
}

#[rstest]
#[case::missing_hgrc(None, Ok(process_output("abc")), true)]
#[case::missing_section(
    Some("default = https://example.com/repo\n"),
    Ok(process_output("abc")),
    true
)]
#[case::missing_remote(
    Some("[paths]\nupstream = https://example.com/repo\n"),
    Ok(process_output("abc")),
    true
)]
#[case::empty_remote(Some("[paths]\ndefault =\n"), Ok(process_output("abc")), true)]
#[case::missing_hg(Some(REMOTE), Err(ProcessError::NotFound), false)]
#[case::empty_commit(Some(REMOTE), Ok(process_output("")), true)]
#[case::failed_commit(
    Some(REMOTE),
    Ok(ProcessOutput { success: false, stdout: Vec::new(), stderr: Vec::new() }),
    true
)]
fn reports_hg_failures(
    #[case] hgrc: Option<&str>,
    #[case] commit: Result<ProcessOutput, ProcessError>,
    #[case] comments: bool,
) {
    let repository = tempfile::tempdir().unwrap();
    fs::create_dir(repository.path().join(".hg")).unwrap();
    if let Some(hgrc) = hgrc {
        write_hgrc(repository.path(), hgrc);
    }

    let frozen = freeze_hg(repository.path(), commit);

    assert_eq!(
        (
            frozen.contains("Editable hg install with no remote"),
            frozen.starts_with("-e "),
        ),
        (comments, !comments)
    );
}

#[test]
fn ignores_hgrc_includes() {
    let repository = tempfile::tempdir().unwrap();
    let included = repository.path().join("included");
    fs::write(&included, REMOTE).unwrap();
    write_hgrc(
        repository.path(),
        &format!("%include {}\n", included.display()),
    );

    assert!(
        freeze_hg(repository.path(), Ok(process_output("abc")))
            .contains("Editable hg install with no remote")
    );
}

#[test]
fn ignores_oversized_hgrc() {
    let repository = tempfile::tempdir().unwrap();
    fs::create_dir(repository.path().join(".hg")).unwrap();
    write_oversized(&repository.path().join(".hg/hgrc"), REMOTE);

    assert!(
        freeze_hg(repository.path(), Ok(process_output("abc")))
            .contains("Editable hg install with no remote")
    );
}

#[cfg(unix)]
#[rstest]
#[case::hgrc("hgrc", ".hg/hgrc")]
#[case::hg_directory("", ".hg")]
fn ignores_linked_hgrc(#[case] target: &str, #[case] link: &str) {
    let outside = tempfile::tempdir().unwrap();
    fs::write(outside.path().join("hgrc"), REMOTE).unwrap();
    let repository = tempfile::tempdir().unwrap();
    let link = repository.path().join(link);
    fs::create_dir_all(link.parent().unwrap()).unwrap();
    std::os::unix::fs::symlink(outside.path().join(target), link).unwrap();

    assert!(
        freeze_hg(repository.path(), Ok(process_output("abc")))
            .contains("Editable hg install with no remote")
    );
}

#[rstest]
#[case::absolute(HgRemote::Absolute, "-e hg+file://")]
#[case::missing_absolute(HgRemote::MissingAbsolute, "-e hg+file://")]
#[case::windows(HgRemote::Value(r"C:\missing"), r"-e hg+C:\missing")]
#[case::prefixed(HgRemote::Value("hg:https://example.com/repo"), "-e hg:https://")]
fn normalizes_hg_remotes(#[case] source: HgRemote, #[case] expected: &str) {
    let repository = tempfile::tempdir().unwrap();
    let remote = match source {
        HgRemote::Absolute => repository.path().to_string_lossy().into_owned(),
        HgRemote::MissingAbsolute => repository
            .path()
            .join("missing")
            .to_string_lossy()
            .into_owned(),
        HgRemote::Value(value) => value.to_string(),
    };
    write_hgrc(repository.path(), &format!("[paths]\ndefault = {remote}\n"));

    assert!(freeze_hg(repository.path(), Ok(process_output("abc"))).starts_with(expected));
}

#[derive(Clone, Copy)]
enum HgRemote {
    Absolute,
    MissingAbsolute,
    Value(&'static str),
}
