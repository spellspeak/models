// swift-tools-version: 6.0
import PackageDescription

let package = Package(
    name: "SpellSpeakAudience",
    platforms: [.iOS(.v18), .macOS(.v15)],
    products: [
        .library(name: "SpellSpeakAudience", targets: ["SpellSpeakAudience"]),
    ],
    targets: [
        .target(name: "SpellSpeakAudience"),
        .testTarget(
            name: "SpellSpeakAudienceTests",
            dependencies: ["SpellSpeakAudience"],
            resources: [.copy("Fixtures")]
        ),
    ]
)
