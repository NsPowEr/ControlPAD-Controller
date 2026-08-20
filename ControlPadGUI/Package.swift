// swift-tools-version:6.2
import PackageDescription

let package = Package(
    name: "ControlPadGUI",
    defaultLocalization: "it",
    platforms: [.macOS(.v26)],
    targets: [
        .executableTarget(
            name: "ControlPadGUI",
            path: "Sources/ControlPadGUI",
            resources: [
                .process("Resources/it.lproj"),
                .process("Resources/en.lproj"),
            ]
        ),
        .testTarget(
            name: "ControlPadGUITests",
            dependencies: ["ControlPadGUI"],
            path: "Tests/ControlPadGUITests"
        ),
    ]
)
