use std::ffi::OsString;
use std::time::{Duration, Instant};

use _pipdeptree::{
    ProcessError, ProcessOutput, ProcessRequest, ProcessRunner, SystemProcessRunner,
};
use rstest::rstest;

#[test]
fn builds_process_requests() {
    let request = ProcessRequest::new("tool", ["first", "second"])
        .in_directory("work")
        .with_stdin(b"input".to_vec())
        .with_timeout(Duration::from_secs(2))
        .with_output_limit(64)
        .without_environment(["FIRST", "SECOND"])
        .with_environment([("THIRD", "value")]);

    assert_eq!(
        request,
        ProcessRequest {
            program: OsString::from("tool"),
            args: vec![OsString::from("first"), OsString::from("second")],
            current_dir: Some("work".into()),
            stdin: b"input".to_vec(),
            timeout: Some(Duration::from_secs(2)),
            output_limit: 64,
            removed_environment: vec![OsString::from("FIRST"), OsString::from("SECOND")],
            added_environment: vec![(OsString::from("THIRD"), OsString::from("value"))],
        }
    );
}

#[rstest]
#[case::success("print('output')", true, "output\n", "")]
#[case::failure(
    "import sys; print('error', file=sys.stderr); sys.exit(3)",
    false,
    "",
    "error\n"
)]
fn runs_system_processes(
    #[case] script: &str,
    #[case] success: bool,
    #[case] stdout: &str,
    #[case] stderr: &str,
) {
    let output = SystemProcessRunner
        .run(&ProcessRequest::new(python(), ["-c", script]))
        .unwrap();

    assert_eq!(
        output,
        ProcessOutput {
            success,
            stdout: stdout.as_bytes().to_vec(),
            stderr: stderr.as_bytes().to_vec(),
        }
    );
}

#[test]
fn passes_process_input_and_directory() {
    let directory = tempfile::tempdir().unwrap();
    let output = SystemProcessRunner
        .run(
            &ProcessRequest::new(
                python(),
                [
                    "-c",
                    "import os, sys; print(os.getcwd()); print(sys.stdin.read())",
                ],
            )
            .in_directory(directory.path())
            .with_stdin("content"),
        )
        .unwrap();

    assert_eq!(
        String::from_utf8(output.stdout).unwrap(),
        format!(
            "{}\ncontent\n",
            directory.path().canonicalize().unwrap().display()
        )
    );
}

#[test]
fn drains_output_while_writing_input() {
    let output = SystemProcessRunner
        .run(
            &ProcessRequest::new(
                python(),
                [
                    "-c",
                    concat!(
                        "import sys; ",
                        "sys.stdout.buffer.write(b'x' * 1_000_000); ",
                        "sys.stdout.flush(); ",
                        "data = sys.stdin.buffer.read(); ",
                        "sys.stderr.write(str(len(data)))",
                    ),
                ],
            )
            .with_stdin(vec![b'i'; 1_000_000])
            .with_timeout(Duration::from_secs(5)),
        )
        .unwrap();

    assert_eq!(
        (output.success, output.stdout.len(), output.stderr),
        (true, 1_000_000, b"1000000".to_vec())
    );
}

#[test]
fn ignores_unread_input_when_child_succeeds() {
    let output = SystemProcessRunner
        .run(
            &ProcessRequest::new(python(), ["-c", "print('ok')"])
                .with_stdin(vec![b'i'; 1_000_000])
                .with_timeout(Duration::from_secs(5)),
        )
        .unwrap();

    assert_eq!((output.success, output.stdout), (true, b"ok\n".to_vec()));
}

#[test]
fn preserves_child_error_when_it_closes_stdin() {
    let output = SystemProcessRunner
        .run(
            &ProcessRequest::new(
                python(),
                [
                    "-c",
                    "import sys; sys.stderr.write('bad format\\n'); sys.exit(2)",
                ],
            )
            .with_stdin(vec![b'i'; 1_000_000]),
        )
        .unwrap();

    assert_eq!(
        output,
        ProcessOutput {
            success: false,
            stdout: Vec::new(),
            stderr: b"bad format\n".to_vec(),
        }
    );
}

#[test]
fn removes_process_environment() {
    temp_env::with_var("PIPDEPTREE_PROCESS_TEST", Some("present"), || {
        let output = SystemProcessRunner
            .run(
                &ProcessRequest::new(
                    python(),
                    [
                        "-c",
                        "import os; print(os.environ.get('PIPDEPTREE_PROCESS_TEST', 'missing'))",
                    ],
                )
                .without_environment(["PIPDEPTREE_PROCESS_TEST"]),
            )
            .unwrap();

        assert_eq!(output.stdout, b"missing\n");
    });
}

#[test]
fn adds_process_environment() {
    let output = SystemProcessRunner
        .run(
            &ProcessRequest::new(
                python(),
                [
                    "-c",
                    "import os; print(os.environ['PIPDEPTREE_ADDED_TEST'])",
                ],
            )
            .with_environment([("PIPDEPTREE_ADDED_TEST", "present")]),
        )
        .unwrap();

    assert_eq!(output.stdout, b"present\n");
}

#[test]
fn times_out_system_processes() {
    let error = SystemProcessRunner
        .run(
            &ProcessRequest::new(python(), ["-c", "import time; time.sleep(1)"])
                .with_timeout(Duration::from_millis(1)),
        )
        .unwrap_err();

    assert_eq!(error, ProcessError::TimedOut);
}

#[rstest]
#[case::child_killed("time.sleep(60)")]
#[case::child_exited("")]
fn times_out_while_a_grandchild_holds_the_output(#[case] child_rest: &str) {
    let script = format!(
        "import subprocess, sys, time\n\
         subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'], \
         stdout=sys.stdout, stderr=sys.stderr)\n\
         {child_rest}"
    );
    let started = Instant::now();

    let error = SystemProcessRunner
        .run(&ProcessRequest::new(python(), ["-c", &script]).with_timeout(Duration::from_secs(3)))
        .unwrap_err();

    assert_eq!(
        (error, started.elapsed() < Duration::from_secs(30)),
        (ProcessError::TimedOut, true)
    );
}

#[rstest]
#[case::stdout("import sys; sys.stdout.write('x' * 1001)")]
#[case::stderr("import sys; sys.stderr.write('x' * 1001)")]
fn rejects_output_over_the_limit(#[case] script: &str) {
    let error = SystemProcessRunner
        .run(&ProcessRequest::new(python(), ["-c", script]).with_output_limit(1000))
        .unwrap_err();

    assert_eq!(
        error,
        ProcessError::Failed("output exceeds 1000 bytes".to_string())
    );
}

#[test]
fn keeps_output_at_the_limit() {
    let output = SystemProcessRunner
        .run(
            &ProcessRequest::new(python(), ["-c", "import sys; sys.stdout.write('x' * 1000)"])
                .with_output_limit(1000),
        )
        .unwrap();

    assert_eq!(output.stdout, vec![b'x'; 1000]);
}

#[test]
fn stops_children_that_write_past_the_limit() {
    let error = SystemProcessRunner
        .run(
            &ProcessRequest::new(
                python(),
                [
                    "-c",
                    "import sys\nwhile True: sys.stdout.write('x' * 65536)",
                ],
            )
            .with_output_limit(1000)
            .with_timeout(Duration::from_secs(60)),
        )
        .unwrap_err();

    assert_eq!(
        error,
        ProcessError::Failed("output exceeds 1000 bytes".to_string())
    );
}

#[test]
fn reports_missing_processes() {
    let error = SystemProcessRunner
        .run(&ProcessRequest::new(
            "pipdeptree-command-that-does-not-exist",
            std::iter::empty::<&str>(),
        ))
        .unwrap_err();

    assert_eq!(error, ProcessError::NotFound);
}

#[test]
fn reports_process_start_failures() {
    let directory = tempfile::tempdir().unwrap();
    let error = SystemProcessRunner
        .run(&ProcessRequest::new(
            directory.path(),
            std::iter::empty::<&str>(),
        ))
        .unwrap_err();

    assert!(matches!(error, ProcessError::Failed(message) if !message.is_empty()));
}

#[cfg(unix)]
#[test]
fn skips_programs_in_the_working_directory() {
    let project = tempfile::tempdir().unwrap();
    write_probe(project.path(), 0o755);
    let search = format!("{}:", std::env::var("PATH").unwrap());

    let error = temp_env::with_var("PATH", Some(search), || {
        SystemProcessRunner
            .run(
                &ProcessRequest::new("pipdeptree-path-probe", std::iter::empty::<&str>())
                    .in_directory(project.path()),
            )
            .unwrap_err()
    });

    assert_eq!(error, ProcessError::NotFound);
}

#[cfg(unix)]
#[test]
fn skips_programs_without_execute_permission() {
    let (skipped, found, project) = (
        tempfile::tempdir().unwrap(),
        tempfile::tempdir().unwrap(),
        tempfile::tempdir().unwrap(),
    );
    write_probe(skipped.path(), 0o644);
    write_probe(found.path(), 0o755);
    let search = std::env::join_paths(
        [skipped.path().to_path_buf(), found.path().to_path_buf()]
            .into_iter()
            .chain(std::env::split_paths(&std::env::var_os("PATH").unwrap())),
    )
    .unwrap();

    let output = temp_env::with_var("PATH", Some(search), || {
        SystemProcessRunner
            .run(
                &ProcessRequest::new("pipdeptree-path-probe", std::iter::empty::<&str>())
                    .in_directory(project.path()),
            )
            .unwrap()
    });

    assert_eq!((output.success, output.stdout), (true, b"probe\n".to_vec()));
}

#[cfg(unix)]
fn write_probe(directory: &std::path::Path, mode: u32) {
    use std::os::unix::fs::PermissionsExt as _;

    let probe = directory.join("pipdeptree-path-probe");
    std::fs::write(&probe, "#!/bin/sh\necho probe\n").unwrap();
    std::fs::set_permissions(&probe, std::fs::Permissions::from_mode(mode)).unwrap();
}

const fn python() -> &'static str {
    if cfg!(windows) {
        "python.exe"
    } else {
        "python3"
    }
}
