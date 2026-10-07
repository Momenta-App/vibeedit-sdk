use std::env;
use std::path::PathBuf;
use std::process::Command;

fn main() {
    println!("cargo:rerun-if-changed=src/encoder.mm");
    if env::var("CARGO_CFG_TARGET_OS").as_deref() != Ok("macos") {
        return;
    }
    let output = PathBuf::from(env::var_os("OUT_DIR").expect("Cargo sets OUT_DIR"));
    let library = output.join("libvibeedit_metal_bridge.a");
    let encoder = output.join("encoder.o");
    assert!(
        Command::new("clang++")
            .args([
                "-std=c++17",
                "-fobjc-arc",
                "-mmacosx-version-min=12.0",
                "-c",
                "src/encoder.mm",
                "-o"
            ])
            .arg(&encoder)
            .status()
            .expect("clang++ is required")
            .success()
    );
    assert!(
        Command::new("ar")
            .arg("rcs")
            .arg(&library)
            .arg(&encoder)
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
    println!("cargo:rustc-link-lib=framework=AVFoundation");
    println!("cargo:rustc-link-lib=framework=CoreVideo");
    println!("cargo:rustc-link-lib=framework=CoreMedia");
    println!("cargo:rustc-link-lib=framework=VideoToolbox");
    println!("cargo:rustc-link-lib=c++");
}
