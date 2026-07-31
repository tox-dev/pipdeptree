fn main() {
    // Meson passes the version it derived from the git tags; a bare cargo build falls back to the VERSION file.
    println!("cargo:rerun-if-env-changed=PIPDEPTREE_VERSION");
    let version = std::env::var("PIPDEPTREE_VERSION").unwrap_or_else(|_| {
        let version_file = format!("{}/VERSION", env!("CARGO_MANIFEST_DIR"));
        println!("cargo:rerun-if-changed={version_file}");
        std::fs::read_to_string(&version_file).expect("VERSION must be readable")
    });
    println!("cargo:rustc-env=PIPDEPTREE_VERSION={}", version.trim());
    if std::env::var_os("CARGO_FEATURE_EXTENSION_MODULE").is_some()
        && std::env::var("CARGO_CFG_TARGET_OS").as_deref() == Ok("macos")
    {
        println!("cargo:rustc-link-arg=-undefined");
        println!("cargo:rustc-link-arg=dynamic_lookup");
    }
}
