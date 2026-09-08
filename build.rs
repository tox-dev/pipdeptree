use std::env;
use std::fs;
use std::path::Path;
use std::process::Command;

fn main() {
    println!("cargo:rerun-if-env-changed=PIPDEPTREE_VERSION");
    println!("cargo:rerun-if-changed=PKG-INFO");
    println!("cargo:rerun-if-changed=.git");
    let version = env::var("PIPDEPTREE_VERSION")
        .ok()
        .or_else(from_git)
        .or_else(from_metadata)
        .unwrap_or_else(|| "0.0.0".to_string());
    println!("cargo:rustc-env=PIPDEPTREE_VERSION={}", version.trim());
    if env::var_os("CARGO_FEATURE_EXTENSION_MODULE").is_some()
        && env::var("CARGO_CFG_TARGET_OS").as_deref() == Ok("macos")
    {
        println!("cargo:rustc-link-arg=-undefined");
        println!("cargo:rustc-link-arg=dynamic_lookup");
    }
}

fn from_git() -> Option<String> {
    if !Path::new(".git").exists() {
        return None;
    }
    if let Some(paths) = git(&[
        "rev-parse",
        "--git-path",
        "HEAD",
        "--git-path",
        "refs",
        "--git-path",
        "packed-refs",
    ]) {
        for path in paths.lines() {
            println!("cargo:rerun-if-changed={path}");
        }
    }
    let described = git(&["describe", "--tags", "--long", "--match", "[0-9]*"])?;
    let (release, commit) = described
        .rsplit_once('-')
        .expect("git describe includes a commit");
    let (tag, distance) = release
        .rsplit_once('-')
        .expect("git describe includes a distance");
    Some(if distance == "0" {
        tag.to_string()
    } else {
        format!("{tag}.dev{distance}+{commit}")
    })
}

fn git(args: &[&str]) -> Option<String> {
    let output = Command::new("git").args(args).output().ok()?;
    output
        .status
        .success()
        .then(|| String::from_utf8_lossy(&output.stdout).trim().to_string())
}

fn from_metadata() -> Option<String> {
    fs::read_to_string("PKG-INFO")
        .ok()?
        .lines()
        .take_while(|line| !line.is_empty())
        .find_map(|line| {
            line.strip_prefix("Version:")
                .map(str::trim)
                .filter(|version| !version.is_empty())
                .map(ToOwned::to_owned)
        })
}
