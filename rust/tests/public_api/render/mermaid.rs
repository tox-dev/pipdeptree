use super::super::common::PackageSite;
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

#[rstest]
#[case::quote_in_version(
    "Name: demo\nVersion: 1\"]; click other href \"https://example.com/\"\n",
    "    demo[\"demo<br/>1#34;]; click other href #34;https://example.com/#34;\"]\n"
)]
#[case::markup_in_version(
    "Name: demo\nVersion: <b>1</b> & #`\n",
    "    demo[\"demo<br/>#60;b#62;1#60;/b#62; #38; #35;#96;\"]\n"
)]
#[case::control_in_version("Name: demo\nVersion: 1\u{1b}\n", "    demo[\"demo<br/>1\u{fffd}\"]\n")]
#[case::statement_in_name(
    "Name: demo; other[forged]; demo\nVersion: 1\n",
    "    package_0[\"demo; other[forged]; demo<br/>1\"]\n"
)]
#[case::empty_name("Name: \nVersion: 1\n", "    package_0[\"<br/>1\"]\n")]
fn escapes_mermaid_node(#[case] metadata: &str, #[case] expected: &str) {
    let site = PackageSite::new();
    site.write("demo-1.dist-info", metadata);
    let output = execute(&site, &["-o", "mermaid"]);

    assert_eq!(
        text(&output),
        format!("flowchart TD\n    classDef missing stroke-dasharray: 5\n{expected}\n")
    );
}

#[test]
fn gives_reserved_and_invalid_keys_distinct_ids() {
    let site = PackageSite::new();
    site.write(
        "end-1.dist-info",
        "Name: end\nVersion: 1\nRequires-Dist: bad\n",
    );
    site.write("bad-1.dist-info", "Name: bad\nVersion: 1\n");
    site.write(
        "weird-1.dist-info",
        "Name: we ird\nVersion: 1\nRequires-Dist: end\n",
    );
    let output = execute(&site, &["-o", "mermaid"]);

    assert_eq!(
        text(&output),
        concat!(
            "flowchart TD\n",
            "    classDef missing stroke-dasharray: 5\n",
            "    bad[\"bad<br/>1\"]\n",
            "    end_0[\"end<br/>1\"]\n",
            "    package_2[\"we ird<br/>1\"]\n",
            "    end_0 -- \"any\" --> bad\n",
            "    package_2 -- \"any\" --> end_0\n",
            "\n",
        )
    );
}
