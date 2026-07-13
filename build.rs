fn main() {
    let version = std::fs::read_to_string("VERSION").expect("VERSION must be readable");
    println!("cargo:rustc-env=PIPDEPTREE_VERSION={}", version.trim());
    println!("cargo:rerun-if-changed=VERSION");
    if std::env::var_os("CARGO_FEATURE_EXTENSION_MODULE").is_some()
        && std::env::var("CARGO_CFG_TARGET_OS").as_deref() == Ok("macos")
    {
        println!("cargo:rustc-link-arg=-undefined");
        println!("cargo:rustc-link-arg=dynamic_lookup");
    }
}
