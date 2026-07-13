use std::ffi::OsString;
use std::time::Duration;

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
        .without_environment(["FIRST", "SECOND"]);

    assert_eq!(
        request,
        ProcessRequest {
            program: OsString::from("tool"),
            args: vec![OsString::from("first"), OsString::from("second")],
            current_dir: Some("work".into()),
            stdin: b"input".to_vec(),
            timeout: Some(Duration::from_secs(2)),
            removed_environment: vec![OsString::from("FIRST"), OsString::from("SECOND")],
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
fn times_out_system_processes() {
    let error = SystemProcessRunner
        .run(
            &ProcessRequest::new(python(), ["-c", "import time; time.sleep(1)"])
                .with_timeout(Duration::from_millis(1)),
        )
        .unwrap_err();

    assert_eq!(error, ProcessError::TimedOut);
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

const fn python() -> &'static str {
    if cfg!(windows) {
        "python.exe"
    } else {
        "python3"
    }
}
