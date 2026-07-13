use std::path::PathBuf;

use clap::builder::styling::{AnsiColor, Styles};
use clap::{
    ArgAction, Args, ColorChoice, CommandFactory, FromArgMatches, Parser, Subcommand, ValueEnum,
};

use crate::Error;

#[derive(Clone, Copy, Debug, Eq, PartialEq, ValueEnum)]
pub enum ExtrasMode {
    None,
    Explicit,
    Active,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq, ValueEnum)]
pub enum WarningMode {
    Silence,
    Suppress,
    Fail,
}

#[derive(Clone, Copy, Debug, Eq, Ord, PartialEq, PartialOrd, ValueEnum)]
pub enum ComputedField {
    Size,
    SizeRaw,
    UniqueDepsCount,
    UniqueDepsNames,
    UniqueDepsSize,
}

impl ComputedField {
    pub const fn is_unique(self) -> bool {
        matches!(
            self,
            Self::UniqueDepsCount | Self::UniqueDepsNames | Self::UniqueDepsSize
        )
    }
}

#[derive(Debug, Parser)]
#[command(
    name = "pipdeptree",
    version = env!("PIPDEPTREE_VERSION"),
    about = "Dependency tree of the installed python packages",
    disable_help_subcommand = true,
    disable_version_flag = true
)]
pub struct Options {
    #[arg(
        short = 'v',
        long = "version",
        action = ArgAction::Version
    )]
    version: Option<bool>,

    #[arg(
        short = 'w',
        long,
        value_enum,
        default_value = "suppress",
        global = true,
        help = "Warning control"
    )]
    pub warn: WarningMode,

    #[arg(
        short = 'p',
        long,
        value_name = "P",
        global = true,
        help = "Comma-separated packages to show; wildcards and name[extra] are supported"
    )]
    pub packages: Option<String>,

    #[arg(
        short = 'e',
        long,
        value_name = "P",
        global = true,
        help = "Comma-separated packages to exclude; wildcards are supported"
    )]
    pub exclude: Option<String>,

    #[arg(
        long,
        action = ArgAction::SetTrue,
        global = true,
        help = "Also exclude dependencies of excluded packages"
    )]
    pub exclude_dependencies: bool,

    #[arg(
        short = 'x',
        long,
        value_enum,
        num_args = 0..=1,
        default_missing_value = "explicit",
        default_value = "explicit",
        global = true,
        help = "Optional dependencies to include"
    )]
    pub extras: ExtrasMode,

    #[command(flatten)]
    legacy_formats: LegacyFormats,

    #[arg(
        long,
        default_value = "utf-8",
        value_name = "E",
        global = true,
        help = "Output encoding"
    )]
    pub encoding: String,

    #[arg(
        short = 'a',
        long,
        action = ArgAction::SetTrue,
        global = true,
        help = "List every package at the top level"
    )]
    pub all: bool,

    #[arg(
        short = 'd',
        long,
        value_name = "D",
        allow_hyphen_values = true,
        global = true,
        help = "Limit tree depth"
    )]
    pub depth: Option<usize>,

    #[arg(
        short = 'r',
        long,
        action = ArgAction::SetTrue,
        global = true,
        help = "Show each package with its dependents"
    )]
    pub reverse: bool,

    #[command(flatten)]
    additional_formats: AdditionalFormats,

    #[arg(
        long = "graph-output",
        value_name = "FMT",
        global = true,
        help = "Render Graphviz output (deprecated; use -o graphviz-FMT)"
    )]
    pub graphviz_format: Option<String>,

    #[arg(
        short = 'o',
        long = "output",
        value_name = "FMT",
        default_value = "text",
        global = true,
        help = "Output format: text, rich, freeze, json, json-tree, mermaid, or graphviz-FMT"
    )]
    pub output_format: String,

    #[arg(long, help = "Python interpreter whose environment to inspect")]
    pub python: Option<String>,

    #[arg(
        long,
        action = ArgAction::Append,
        help = "Package search path; repeatable"
    )]
    pub path: Vec<PathBuf>,

    #[command(flatten)]
    installed: InstalledFlags,

    #[arg(
        short = 'm',
        long,
        value_delimiter = ',',
        help = "Comma-separated core metadata fields"
    )]
    pub metadata: Vec<String>,

    #[arg(
        short = 'c',
        long,
        value_delimiter = ',',
        value_enum,
        help = "Comma-separated computed fields"
    )]
    pub computed: Vec<ComputedField>,

    #[command(subcommand)]
    pub command: Option<Command>,
}

#[derive(Debug, Args)]
struct LegacyFormats {
    #[arg(
        short = 'f',
        long,
        action = ArgAction::SetTrue,
        global = true,
        help = "Print freeze-compatible requirements (deprecated; use -o freeze)"
    )]
    freeze: bool,

    #[arg(
        short = 'j',
        long,
        action = ArgAction::SetTrue,
        global = true,
        help = "Render flat JSON (deprecated; use -o json)"
    )]
    json: bool,

    #[arg(
        long,
        action = ArgAction::SetTrue,
        global = true,
        help = "Render nested JSON (deprecated; use -o json-tree)"
    )]
    json_tree: bool,
}

#[derive(Debug, Args)]
struct AdditionalFormats {
    #[arg(
        long,
        action = ArgAction::SetTrue,
        global = true,
        help = "Render an environment health summary"
    )]
    summary: bool,

    #[arg(
        long,
        action = ArgAction::SetTrue,
        global = true,
        help = "Render a Mermaid flowchart (deprecated; use -o mermaid)"
    )]
    mermaid: bool,
}

#[derive(Debug, Args)]
struct InstalledFlags {
    #[arg(
        short = 'l',
        long,
        action = ArgAction::SetTrue,
        conflicts_with = "user_only",
        help = "Exclude globally installed packages from a virtual environment"
    )]
    local_only: bool,

    #[arg(
        short = 'u',
        long,
        action = ArgAction::SetTrue,
        conflicts_with = "local_only",
        help = "Show only packages installed in the user site"
    )]
    user_only: bool,

    #[arg(
        long,
        action = ArgAction::SetTrue,
        help = "Show package licenses (deprecated; use --metadata license)"
    )]
    license: bool,
}

#[derive(Debug, Subcommand)]
pub enum Command {
    #[command(
        name = "from-index",
        visible_alias = "i",
        about = "Resolve requirements from a package index without installing them"
    )]
    FromIndex {
        #[arg(value_name = "REQUIREMENT", help = "Inline PEP 508 requirement")]
        requirements: Vec<String>,

        #[arg(
            long = "requirements",
            action = ArgAction::Append,
            value_name = "FILE",
            help = "Requirements file; repeatable"
        )]
        requirement_files: Vec<PathBuf>,

        #[arg(
            long = "pyproject",
            action = ArgAction::Append,
            value_name = "FILE",
            help = "pyproject.toml input; repeatable"
        )]
        pyproject_files: Vec<PathBuf>,

        #[arg(long, value_name = "URL", help = "Primary package index URL")]
        index_url: Option<String>,

        #[arg(
            long,
            action = ArgAction::Append,
            value_name = "URL",
            help = "Additional package index URL; repeatable"
        )]
        extra_index_url: Vec<String>,
    },
    #[command(
        name = "from-lock",
        visible_alias = "l",
        about = "Render an existing PEP 751 lock without network access"
    )]
    FromLock {
        #[arg(value_name = "PYLOCK", help = "PEP 751 pylock.toml file")]
        lock: PathBuf,
    },
}

impl Options {
    pub fn parse_args(args: &[String], color: bool) -> Result<Self, clap::Error> {
        let matches = Self::command()
            .mut_arg("output_format", |argument| {
                argument.default_value(if color { "rich" } else { "text" })
            })
            .styles(cli_styles())
            .color(if color {
                ColorChoice::Always
            } else {
                ColorChoice::Never
            })
            .try_get_matches_from(
                std::iter::once("pipdeptree").chain(args.iter().map(String::as_str)),
            )?;
        Self::from_arg_matches(&matches)
    }

    pub fn validate(&mut self) -> Result<(), Error> {
        let legacy_formats = usize::from(self.legacy_formats.freeze)
            + usize::from(self.legacy_formats.json)
            + usize::from(self.legacy_formats.json_tree)
            + usize::from(self.additional_formats.mermaid)
            + usize::from(self.graphviz_format.is_some());
        if legacy_formats > 1 {
            return Err(Error::usage("render options are mutually exclusive"));
        }
        if self.legacy_formats.freeze {
            self.output_format = "freeze".to_string();
        } else if self.legacy_formats.json {
            self.output_format = "json".to_string();
        } else if self.legacy_formats.json_tree {
            self.output_format = "json-tree".to_string();
        } else if self.additional_formats.mermaid {
            self.output_format = "mermaid".to_string();
        } else if let Some(format) = &self.graphviz_format {
            self.output_format = format!("graphviz-{format}");
        }
        if !matches!(
            self.output_format.as_str(),
            "freeze" | "json" | "json-tree" | "mermaid" | "rich" | "text"
        ) && !self.output_format.starts_with("graphviz-")
        {
            return Err(Error::usage(format!(
                "\"{}\" is not a known output format",
                self.output_format
            )));
        }
        if self.summary() && !matches!(self.output_format.as_str(), "json" | "rich" | "text") {
            return Err(Error::usage(format!(
                "--summary supports only -o json, rich, text (got {})",
                self.output_format
            )));
        }
        if self.exclude_dependencies && self.exclude.is_none() {
            return Err(Error::usage(
                "must use --exclude-dependencies with --exclude",
            ));
        }
        if !self.path.is_empty() && (self.local_only() || self.user_only()) {
            return Err(Error::usage(
                "cannot use --path with --user-only or --local-only",
            ));
        }
        if self.installed.license {
            if self.metadata.iter().any(|field| field == "license") {
                return Err(Error::usage("cannot use --license with --metadata license"));
            }
            self.metadata.insert(0, "license".to_string());
        }
        let mut metadata = std::collections::HashSet::new();
        self.metadata
            .retain(|field| !field.is_empty() && metadata.insert(field.clone()));
        if let Some(Command::FromIndex {
            requirements,
            requirement_files,
            pyproject_files,
            ..
        }) = &self.command
        {
            if requirements.is_empty() && requirement_files.is_empty() && pyproject_files.is_empty()
            {
                return Err(Error::usage(
                    "from-index needs at least one REQUIREMENT, --requirements FILE, or --pyproject FILE",
                ));
            }
        }
        if self.command.is_some()
            && (self.installed.license || !self.metadata.is_empty() || !self.computed.is_empty())
        {
            return Err(Error::usage(
                "installed package metadata options cannot be used with a subcommand",
            ));
        }
        Ok(())
    }

    pub const fn resolved(&self) -> bool {
        self.command.is_some()
    }

    pub const fn summary(&self) -> bool {
        self.additional_formats.summary
    }

    pub const fn local_only(&self) -> bool {
        self.installed.local_only
    }

    pub const fn user_only(&self) -> bool {
        self.installed.user_only
    }
}

const fn cli_styles() -> Styles {
    Styles::styled()
        .header(AnsiColor::BrightBlue.on_default().bold().underline())
        .usage(AnsiColor::BrightBlue.on_default().bold().underline())
        .literal(AnsiColor::Cyan.on_default().bold())
        .error(AnsiColor::Red.on_default().bold())
        .invalid(AnsiColor::Red.on_default().bold())
        .valid(AnsiColor::Green.on_default().bold())
}
