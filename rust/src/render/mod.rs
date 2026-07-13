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
use crate::options::Options;
use crate::process::ProcessRunner;

pub fn render(
    processes: &dyn ProcessRunner,
    graph: &Graph,
    options: &Options,
    color: bool,
) -> Result<Vec<u8>, Error> {
    if !options.summary() && options.output_format == "json" {
        let mut output = json::render(graph, options);
        output.push(b'\n');
        return Ok(output);
    }
    let text = if options.summary() {
        summary::render(graph, options, color)
    } else {
        match options.output_format.as_str() {
            "json" => unreachable!("flat JSON returns before string rendering"),
            "json-tree" => json_tree::render(graph, options),
            "mermaid" => format!("{}\n", mermaid::render(graph, options)),
            "freeze" => freeze::render(processes, graph, options),
            "rich" => rich_text::render(processes, graph, options, color),
            format if format.starts_with("graphviz-") => {
                let format = &format["graphviz-".len()..];
                let dot = graphviz::render(graph, options);
                if format == "dot" {
                    format!("{dot}\n")
                } else {
                    return graphviz::pipe(processes, &dot, format);
                }
            }
            _ => text::render(
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
