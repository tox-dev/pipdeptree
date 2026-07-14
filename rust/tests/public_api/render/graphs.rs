use _pipdeptree::{ProcessError, ProcessOutput};
use rstest::rstest;

use super::super::common::MockProcesses;
use super::{execute, execute_with, render_site, text};

#[rstest]
#[case::forward(&["--graph-output", "dot"] as &[&str], "root -> missing [style=dashed]")]
#[case::reverse_depth(
    &["--graph-output", "dot", "--reverse", "--depth", "1"],
    "child -> root"
)]
#[case::forward_depth(
    &["--graph-output", "dot", "--depth", "1"],
    "root -> unique"
)]
#[case::metadata(
    &["--graph-output", "dot", "--metadata", "license"],
    "GPL-3.0 License"
)]
#[case::reverse_metadata(
    &["--graph-output", "dot", "--reverse", "--metadata", "license"],
    "GPL-3.0 License"
)]
fn renders_graphviz_dot(#[case] args: &[&str], #[case] expected: &str) {
    let site = render_site();
    let output = execute(&site, args);

    assert_eq!(
        (
            text(&output).starts_with("digraph {\n"),
            text(&output).contains(expected),
            text(&output).contains("\"graph\" [label="),
            text(&output).ends_with("\n\n"),
        ),
        (true, true, true, true)
    );
}

#[test]
fn limits_graphviz_to_roots_at_depth_zero() {
    let site = render_site();
    let output = execute(&site, &["--graph-output", "dot", "--depth", "0"]);

    assert_eq!(
        (
            text(&output).contains("root [label="),
            text(&output).contains(" -> "),
        ),
        (true, false)
    );
}

#[rstest]
#[case::forward(&["--mermaid"] as &[&str], "root -.-> missing")]
#[case::reverse(&["--mermaid", "--reverse"], "child -- \"any\" --> other")]
#[case::metadata(
    &["--mermaid", "--metadata", "license"],
    "GPL-3.0 License"
)]
#[case::reverse_metadata(
    &["--mermaid", "--reverse", "--metadata", "license"],
    "GPL-3.0 License"
)]
fn renders_mermaid(#[case] args: &[&str], #[case] expected: &str) {
    let site = render_site();
    let output = execute(&site, args);

    assert_eq!(
        (
            text(&output).starts_with("flowchart TD\n"),
            text(&output).contains(expected),
            text(&output).contains("graph_0"),
            text(&output).ends_with("\n\n"),
        ),
        (true, true, true, true)
    );
}

#[rstest]
#[case::png(
    "png",
    Ok(ProcessOutput { success: true, stdout: b"image".to_vec(), stderr: Vec::new() }),
    0,
    b"image" as &[u8],
    ""
)]
#[case::pdf(
    "pdf",
    Ok(ProcessOutput { success: true, stdout: b"%PDF".to_vec(), stderr: Vec::new() }),
    0,
    b"%PDF" as &[u8],
    ""
)]
#[case::svg(
    "svg",
    Ok(ProcessOutput { success: true, stdout: b"<svg/>".to_vec(), stderr: Vec::new() }),
    0,
    b"<svg/>" as &[u8],
    ""
)]
#[case::failure(
    "png",
    Ok(ProcessOutput { success: false, stdout: Vec::new(), stderr: b"bad format\n".to_vec() }),
    1,
    b"",
    "bad format\n"
)]
#[case::missing(
    "png",
    Err(ProcessError::NotFound),
    1,
    b"",
    "graphviz is not available: command not found\n"
)]
fn pipes_graphviz_formats(
    #[case] format: &str,
    #[case] result: Result<ProcessOutput, ProcessError>,
    #[case] code: i32,
    #[case] expected_stdout: &[u8],
    #[case] expected_stderr: &str,
) {
    let site = render_site();
    let mut processes = MockProcesses::new();
    let graphviz_arg = format!("-T{format}");
    processes
        .expect_run()
        .withf(move |request| {
            request.program == "dot"
                && request.args == [graphviz_arg.as_str()]
                && request.stdin.starts_with(b"digraph {\n")
        })
        .return_once(move |_| result);

    let output = execute_with(&processes, &site, &["--graph-output", format], false);

    assert_eq!(
        (
            output.code,
            output.stdout.as_slice(),
            output.stderr.as_str()
        ),
        (code, expected_stdout, expected_stderr)
    );
}

#[test]
fn lists_missing_packages_in_reverse_graphs() {
    let site = render_site();

    let mermaid = execute(&site, &["--mermaid", "--reverse"]);
    let dot = execute(&site, &["--graph-output", "dot", "--reverse"]);

    assert_eq!(
        (
            text(&mermaid).contains("missing<br/>(missing)"),
            text(&mermaid).contains("missing -.-> root"),
            text(&dot).contains("(missing)"),
            text(&dot).contains("missing -> root [style=dashed]"),
        ),
        (true, true, true, true)
    );
}

#[test]
fn keeps_parentheses_in_graph_labels() {
    let site = super::PackageSite::new();
    site.write(
        "demo-1.dist-info",
        concat!(
            "Name: demo\n",
            "Version: 1\n",
            "Classifier: License :: OSI Approved :: GNU General Public License v3 (GPLv3+)\n",
        ),
    );

    let mermaid = execute(&site, &["--mermaid", "--metadata", "license"]);
    let dot = execute(&site, &["--graph-output", "dot", "--metadata", "license"]);

    assert_eq!(
        (
            text(&mermaid).contains("GNU General Public License v3 (GPLv3+)\""),
            text(&dot).contains("GNU General Public License v3 (GPLv3+)\""),
        ),
        (true, true)
    );
}
