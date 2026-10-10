use anstyle::{AnsiColor, Style};

use crate::graph::Graph;
use crate::options::Options;
use crate::process::ProcessRunner;

use super::text::{TextStyle, render as render_text, star_marker, status_marker};

pub(super) fn render(
    processes: &dyn ProcessRunner,
    graph: &Graph,
    options: &Options,
    color: bool,
) -> String {
    render_text(processes, graph, options, TextStyle::Rich, color)
}

pub(super) fn root(name: &str, version: &str, suffix: &str) -> String {
    format!(
        "{}{}{}",
        paint(name, AnsiColor::Cyan),
        style_version(version),
        style_suffix(suffix)
    )
}

pub(super) fn reverse(name: &str, version: &str, required: &str, suffix: &str) -> String {
    let operator = Style::new().dimmed();
    format!(
        "{}{} {operator}[requires:{operator:#} {}{operator}]{operator:#}{}",
        paint(name, AnsiColor::Cyan),
        style_version(version),
        style_constraint(required),
        style_suffix(suffix)
    )
}

pub(super) fn dependency(label: &DependencyLabel<'_>) -> String {
    let marker = paint(
        status_marker(label.status, label.unicode),
        match label.status {
            Status::Success => AnsiColor::Green,
            Status::Warning => AnsiColor::Yellow,
            Status::Error => AnsiColor::Red,
        },
    );
    let star = if label.unique {
        format!(" {}", paint(star_marker(label.unicode), AnsiColor::Magenta))
    } else {
        String::new()
    };
    let detail = match label.version {
        VersionLabel::Installed {
            required,
            installed,
        } => {
            format!(
                "{} {} {} {}",
                style_label("required:"),
                style_constraint(required),
                style_label("installed:"),
                style_installed(installed, label.status)
            )
        }
        VersionLabel::Candidate {
            required: Some(required),
            candidate,
        } => format!(
            "{} {} {} {}",
            style_label("required:"),
            style_constraint(required),
            style_label("candidate:"),
            style_installed(candidate, label.status)
        ),
        VersionLabel::Candidate {
            required: None,
            candidate,
        } => {
            format!(
                "{} {}",
                style_label("candidate:"),
                style_installed(candidate, label.status)
            )
        }
    };
    let extra = label
        .extra
        .map_or_else(String::new, |extra| format!(" [extra: {extra}]"));
    format!(
        "{marker}{star} {} {detail}{}{}",
        paint(label.name, AnsiColor::Cyan),
        style_suffix(&extra),
        style_suffix(label.suffix)
    )
}

pub(super) fn tree_prefix(value: &str) -> String {
    let style = Style::new().dimmed();
    format!("{style}{value}{style:#}")
}

fn style_version(value: &str) -> String {
    let operator = Style::new().dimmed();
    format!("{operator}=={operator:#}{}", paint(value, AnsiColor::Green))
}

fn style_label(value: &str) -> String {
    let style = Style::new().dimmed();
    format!("{style}{value}{style:#}")
}

fn style_constraint(value: &str) -> String {
    let style = AnsiColor::BrightBlue.on_default();
    format!("{style}{value}{style:#}")
}

fn style_installed(value: &str, status: Status) -> String {
    paint(
        value,
        match status {
            Status::Success => AnsiColor::Green,
            Status::Warning => AnsiColor::Yellow,
            Status::Error => AnsiColor::Red,
        },
    )
}

fn style_suffix(value: &str) -> String {
    if value.is_empty() {
        return String::new();
    }
    let style = AnsiColor::Magenta.on_default();
    format!("{style}{value}{style:#}")
}

fn paint(value: &str, color: AnsiColor) -> String {
    let style = color.on_default().bold();
    format!("{style}{value}{style:#}")
}

#[derive(Clone, Copy)]
pub(super) enum Status {
    Success,
    Warning,
    Error,
}

pub(super) struct DependencyLabel<'a> {
    pub(super) status: Status,
    pub(super) unique: bool,
    pub(super) unicode: bool,
    pub(super) name: &'a str,
    pub(super) version: VersionLabel<'a>,
    pub(super) extra: Option<&'a str>,
    pub(super) suffix: &'a str,
}

pub(super) enum VersionLabel<'a> {
    Installed {
        required: &'a str,
        installed: &'a str,
    },
    Candidate {
        required: Option<&'a str>,
        candidate: &'a str,
    },
}
