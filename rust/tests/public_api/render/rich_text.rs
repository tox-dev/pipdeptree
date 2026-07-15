use super::{execute, render_site, text};

#[test]
fn renders_rich_ascii_for_non_unicode_encodings() {
    let site = render_site();
    let output = execute(
        &site,
        &[
            "--output",
            "rich",
            "--encoding",
            "ascii",
            "--computed",
            "unique-deps-count",
        ],
    );
    let rendered = text(&output);

    assert_eq!(
        (
            rendered.is_ascii(),
            rendered.contains("+-- "),
            rendered.contains("`-- "),
            rendered.contains("! child"),
            rendered.contains("x missing"),
            rendered.contains("v * unique"),
        ),
        (true, true, true, true, true, true)
    );
}

#[test]
fn renders_rich_color_and_computed_fields() {
    let site = render_site();
    site.write(
        "exact-1.dist-info",
        "Name: exact\nVersion: 1\nRequires-Dist: child==1\n",
    );
    let output = super::execute_with(
        &_pipdeptree::SystemProcessRunner,
        &site,
        &[
            "--output",
            "rich",
            "--metadata",
            "license",
            "--computed",
            "size,size-raw,unique-deps-count,unique-deps-names,unique-deps-size",
        ],
        true,
    );

    let name_style = anstyle::AnsiColor::Cyan.on_default().bold();
    let version_style = anstyle::AnsiColor::Green.on_default().bold();
    let constraint_style = anstyle::AnsiColor::BrightBlue.on_default();
    let label_style = anstyle::Style::new().dimmed();
    let conflict_style = anstyle::AnsiColor::Yellow.on_default().bold();
    let error_style = anstyle::AnsiColor::Red.on_default().bold();
    let extra_style = anstyle::AnsiColor::Magenta.on_default();
    assert_eq!(
        (
            text(&output).contains("\u{1b}["),
            text(&output).contains(&format!("{name_style}child{name_style:#}")),
            text(&output).contains(&format!("{version_style}1{version_style:#}")),
            text(&output).contains(&format!("{constraint_style}>=2{constraint_style:#}")),
            text(&output).contains(&format!("{constraint_style}==1{constraint_style:#}")),
            text(&output).contains(&format!("{label_style}installed:{label_style:#}")),
            text(&output).contains(&format!("{conflict_style}1{conflict_style:#}")),
            text(&output).contains(&format!("{conflict_style}⚠{conflict_style:#} ")),
            text(&output).contains(&format!("{error_style}✗{error_style:#} ")),
            text(&output).contains(&format!("{error_style}?{error_style:#}")),
            text(&output).contains(&format!("{extra_style} (GPL-3.0")),
            text(&output).contains("unique: leaf | unique"),
        ),
        (
            true, true, true, true, true, true, true, true, true, true, true, true
        )
    );
}
