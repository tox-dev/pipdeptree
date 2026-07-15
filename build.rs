fn main() {
    let version_file = format!("{}/VERSION", env!("CARGO_MANIFEST_DIR"));
    let version = std::fs::read_to_string(&version_file).expect("VERSION must be readable");
    println!("cargo:rustc-env=PIPDEPTREE_VERSION={}", version.trim());
    println!("cargo:rerun-if-changed={version_file}");
    if std::env::var_os("CARGO_FEATURE_EXTENSION_MODULE").is_some()
        && std::env::var("CARGO_CFG_TARGET_OS").as_deref() == Ok("macos")
    {
        println!("cargo:rustc-link-arg=-undefined");
        println!("cargo:rustc-link-arg=dynamic_lookup");
    }
}
