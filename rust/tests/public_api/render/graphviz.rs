use std::time::Duration;

use super::super::common::MockProcesses;
use super::{PackageSite, execute, execute_with, render_site, text, write_requiring};
use _pipdeptree::{ProcessError, ProcessOutput};
use rstest::rstest;

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
#[case::timed_out(
    "png",
    Err(ProcessError::TimedOut),
    1,
    b"",
    "graphviz did not finish within 300 seconds; use graphviz-dot and run dot on its output\n"
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
                && request.timeout == Some(Duration::from_secs(300))
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

#[test]
fn replaces_nul_in_graphviz_labels() {
    let site = PackageSite::new();
    site.write(
        "hostile-1.dist-info",
        "Name: hostile\nVersion: 1.0\x00\" image=<private.png>] //\n",
    );

    let output = execute(&site, &["--output", "graphviz-dot"]);

    assert!(
        text(&output)
            .contains("hostile [label=\"hostile\\n1.0\u{fffd}\\\" image=<private.png>] //\"]")
    );
}

#[rstest]
#[case::quote_after_backslash("1\\\" color=red] //", "1\\\\\\\" color=red] //")]
#[case::trailing_backslash("1\\", "1\\\\")]
fn escapes_backslashes_in_graphviz_labels(#[case] version: &str, #[case] escaped: &str) {
    let site = super::PackageSite::new();
    site.write(
        "demo-1.dist-info",
        &format!("Name: demo\nVersion: {version}\n"),
    );

    let dot = execute(&site, &["--graph-output", "dot"]);

    assert!(text(&dot).contains(&format!("demo [label=\"demo\\n{escaped}\"]\n")));
}

// app needs the missing gone and the installed mid, so in reverse mode app sits one level below
// the missing root gone but two levels below the installed root base.
fn missing_parent_site() -> PackageSite {
    let site = PackageSite::new();
    write_requiring(&site, "app", &["gone", "mid"]);
    write_requiring(&site, "mid", &["base"]);
    write_requiring(&site, "base", &[] as &[&str]);
    site
}

#[rstest]
#[case::depth_zero(
    "0",
    concat!(
        "digraph {\n",
        "\tbase [label=\"base\\n1\"]\n",
        "\tgone [label=\"gone\\n(missing)\" style=dashed]\n",
        "}\n",
    )
)]
#[case::depth_one(
    "1",
    concat!(
        "digraph {\n",
        "\tapp [label=\"app\\n1\"]\n",
        "\tbase -> mid [label=\"any\"]\n",
        "\tbase [label=\"base\\n1\"]\n",
        "\tgone -> app [style=dashed]\n",
        "\tgone [label=\"gone\\n(missing)\" style=dashed]\n",
        "\tmid [label=\"mid\\n1\"]\n",
        "}\n",
    )
)]
fn limits_reverse_graphviz_below_missing_roots(#[case] depth: &str, #[case] expected: &str) {
    let site = missing_parent_site();
    let output = execute(
        &site,
        &["--graph-output", "dot", "--reverse", "--depth", depth],
    );

    assert_eq!(text(&output), format!("{expected}\n"));
}
