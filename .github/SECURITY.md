# Security policy

pipdeptree is a command-line tool that shows the installed packages of a Python environment, or a resolution from a
package index, as a dependency tree. This policy says how to report a security problem and how we decide whether a
report is one.

## Reporting a vulnerability

**Do not open a public issue for a security problem.** Use
[GitHub's private vulnerability reporting](https://github.com/tox-dev/pipdeptree/security/advisories/new). If you do not
have a GitHub account, or you are a Tidelift subscriber, report through the
[Tidelift security contact](https://tidelift.com/security) instead; Tidelift coordinates the fix and the disclosure with
us. If neither works for you, email [gaborjbernat@gmail.com](mailto:gaborjbernat@gmail.com).

Include what the attacker controls and what they gain, the steps or a proof of concept, and the versions and platform
you tested. Write the report yourself; unreviewed tool or model output takes longer to triage.

## What to expect

Volunteers maintain pipdeptree, with no on-call rotation. We aim to acknowledge a report within **5 working days** and
assess it within **15 working days**. We develop fixes in a private fork attached to the draft advisory and ship them in
a new release; the advisory, with a CVE requested through GitHub, goes out with that release. The default embargo is
**90 days** from the report; we agree any change with the reporter. We credit reporters in the advisory under the name
they choose, or not at all. There is no bug bounty.

## Supported versions

Only the latest release receives fixes. Confirm the problem reproduces on it before reporting.

## Vulnerability or bug

A report is a vulnerability when an attacker who controls only an input that the [threat model](THREAT_MODEL.md) lists
as untrusted breaks a guarantee pipdeptree makes. A report that first needs control of something the threat model
trusts, such as the inspected environment or the interpreter passed with `--python`, is a bug: we fix it in the open and
publish no advisory. Classify a report by who supplies the dangerous input.

**In scope**

- Package metadata from an index, a lock file or a crafted installed distribution breaking out of its field in JSON,
  CycloneDX, DOT or Mermaid output, so the output describes packages or edges that do not exist.
- Parsing metadata (`METADATA`, `direct_url.json`, `RECORD`, `entry_points.txt`, egg-links) executing code, or following
  links out of the inspected environment.
- A malformed input causing a Rust panic, an invalid lifetime or a memory-safety defect at the Python boundary instead
  of an ordinary error.
- Unbounded allocation or recursion from long fields, many packages, duplicate records or deep cycles.
- `from-index` sending requests to a host other than the configured indexes, or leaking index credentials into output.
- Rendering that runs anything other than the Graphviz `dot` binary, or passes it more than the DOT text.
- Code or package metadata from the working directory, or from files another local user can write, being run or reported
  as installed.

**Out of scope**

- The interpreter given with `--python`, or auto-detected from the active virtual environment: pipdeptree runs it to
  read the environment, and its startup runs the environment's `.pth` files.
- Packages installed in the inspected environment; pipdeptree reads their metadata but installing them already ran their
  code.
- Build backends that run when `from-index` resolves a local path or VCS requirement, which Nab may build.
- Index URLs and credentials from options or `PIP_INDEX_URL`, `PIP_EXTRA_INDEX_URL`, `UV_INDEX_URL` and
  `UV_EXTRA_INDEX_URL`.
- Wrong dependency data that pipdeptree reports as it received it.
- What a program that consumes the JSON, SBOM or graph output does with names that are valid but misleading.

If you cannot tell which side a finding falls on, report it through private vulnerability reporting and we will decide.
