use std::env;
use std::path::PathBuf;
use std::process::Command;

fn main() {
    println!("cargo:rerun-if-changed=src/metal_bridge.mm");
    if env::var("CARGO_CFG_TARGET_OS").as_deref() != Ok("macos") {
        return;
    }
    let output = PathBuf::from(env::var_os("OUT_DIR").expect("Cargo sets OUT_DIR"));
    let object = output.join("metal_bridge.o");
    let library = output.join("libvibeedit_metal_bridge.a");
    assert!(
        Command::new("clang++")
            .args([
                "-std=c++17",
                "-fobjc-arc",
                "-mmacosx-version-min=11.0",
                "-c",
                "src/metal_bridge.mm",
                "-o"
            ])
            .arg(&object)
            .status()
            .expect("clang++ is required for the macOS Metal adapter")
            .success(),
        "Metal adapter compilation failed"
    );
    assert!(
        Command::new("ar")
            .arg("rcs")
            .arg(&library)
            .arg(&object)
            .status()
            .expect("ar is required for the macOS Metal adapter")
            .success(),
        "Metal adapter archive failed"
    );
    println!("cargo:rustc-link-search=native={}", output.display());
    println!("cargo:rustc-link-lib=static=vibeedit_metal_bridge");
    println!("cargo:rustc-link-lib=framework=Metal");
    println!("cargo:rustc-link-lib=framework=IOSurface");
    println!("cargo:rustc-link-lib=framework=Foundation");
    println!("cargo:rustc-link-lib=c++");
}
