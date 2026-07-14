// swift-tools-version: 5.9
import PackageDescription

let package = Package(
    name: "vibeedit-apple-vision",
    platforms: [.macOS(.v13)],
    products: [.executable(name: "vibeedit-apple-vision", targets: ["vibeedit-apple-vision"])],
    targets: [.executableTarget(name: "vibeedit-apple-vision", path: "Sources")]
)
