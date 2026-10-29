use std::fs;

use _pipdeptree::{ProcessError, ProcessOutput};
use rstest::rstest;

use super::super::super::common::{MockProcesses, expect_process, process_output, write_oversized};
use super::{editable_site, expect_no_git, freeze};

#[rstest]
#[case::failed_svn(Ok(ProcessOutput { success: false, stdout: Vec::new(), stderr: Vec::new() }))]
#[case::timed_out_svn(Err(ProcessError::TimedOut))]
fn uses_legacy_subversion_metadata(#[case] info: Result<ProcessOutput, ProcessError>) {
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
    expect_process(&mut processes, "svn", &["info", "--xml"], info);

    assert_eq!(
        freeze(&site, &processes),
        "-e svn+https://example.com/repo@12#egg=demo\n"
    );
}

#[test]
fn ignores_oversized_legacy_subversion_metadata() {
    let repository = tempfile::tempdir().unwrap();
    fs::create_dir(repository.path().join(".svn")).unwrap();
    write_oversized(
        &repository.path().join(".svn/entries"),
        "10\n\ndir\n12\nhttps://example.com/repo\n",
    );
    let site = editable_site(repository.path());
    let mut processes = MockProcesses::new();
    expect_no_git(&mut processes, repository.path());
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
        format!(
            "# Editable svn install with no remote (demo==1)\n-e {}/\n",
            repository.path().display()
        )
    );
}

#[cfg(unix)]
#[rstest]
#[case::entries("entries", ".svn/entries")]
#[case::administrative_directory("", ".svn")]
fn ignores_linked_legacy_subversion_metadata(#[case] target: &str, #[case] link: &str) {
    let outside = tempfile::tempdir().unwrap();
    fs::write(
        outside.path().join("entries"),
        "10\n\ndir\n12\nhttps://example.com/repo\n",
    )
    .unwrap();
    let repository = tempfile::tempdir().unwrap();
    let link = repository.path().join(link);
    fs::create_dir_all(link.parent().unwrap()).unwrap();
    std::os::unix::fs::symlink(outside.path().join(target), link).unwrap();
    let site = editable_site(repository.path());
    let mut processes = MockProcesses::new();
    expect_no_git(&mut processes, repository.path());
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
        format!(
            "# Editable svn install with no remote (demo==1)\n-e {}/\n",
            repository.path().display()
        )
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
#[case::legacy_revision(
    Ok(ProcessOutput { success: false, stdout: Vec::new(), stderr: Vec::new() }),
    Some("10\n\ndir\nHEAD\nhttps://example.com/repo\n"),
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
