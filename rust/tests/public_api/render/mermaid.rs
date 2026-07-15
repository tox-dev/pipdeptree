use super::{execute, render_site, text};
use rstest::rstest;

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
