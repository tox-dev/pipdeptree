mod freeze;
mod graphviz;
mod json;
mod json_tree;
mod mermaid;
mod rich_text;
mod shared;
mod summary;
mod text;

use crate::Error;
use crate::graph::Graph;
use crate::options::{Format, Options};
use crate::process::ProcessRunner;

pub fn render(
    processes: &dyn ProcessRunner,
    graph: &Graph,
    options: &Options,
    color: bool,
) -> Result<Vec<u8>, Error> {
    let text = if options.summary() {
        summary::render(graph, options, color)
    } else {
        match &options.output_format {
            Format::Json => json::render(graph, options),
            Format::JsonTree => json_tree::render(graph, options),
            Format::Mermaid => format!("{}\n", mermaid::render(graph, options)),
            Format::Freeze => freeze::render(processes, graph, options),
            Format::Rich => rich_text::render(processes, graph, options, color),
            Format::Graphviz(target) => {
                let dot = graphviz::render(graph, options);
                if target == "dot" {
                    format!("{dot}\n")
                } else {
                    return graphviz::pipe(processes, &dot, target);
                }
            }
            Format::Text => text::render(
                processes,
                graph,
                options,
                if text::is_unicode(&options.encoding) {
                    text::TextStyle::Unicode
                } else {
                    text::TextStyle::Plain
                },
                false,
            ),
        }
    };
    let mut output = text.into_bytes();
    if !output.ends_with(b"\n") {
        output.push(b'\n');
    }
    Ok(output)
}
