use crate::Error;
use crate::graph::Graph;
use crate::options::Options;
use crate::process::ProcessRunner;

use super::text::{TextStyle, render as render_text};

pub(super) fn render(
    processes: &dyn ProcessRunner,
    graph: &Graph,
    options: &Options,
) -> Result<String, Error> {
    render_text(processes, graph, options, TextStyle::Frozen, false)
}
