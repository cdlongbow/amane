// swift-tools-version: 5.9
import PackageDescription

let package = Package(
    name: "Amane",
    platforms: [.macOS(.v13)],
    targets: [
        .executableTarget(name: "Amane"),
        .executableTarget(name: "AmaneUI"),
    ]
)
