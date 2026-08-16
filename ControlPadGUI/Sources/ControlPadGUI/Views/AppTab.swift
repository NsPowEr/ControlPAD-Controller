import Foundation

enum AppTab: String, CaseIterable, Identifiable {
    case lighting, mapping, macros, profiles

    var id: String { rawValue }

    var titleKey: String {
        switch self {
        case .lighting: "tab.lighting"
        case .mapping: "tab.mapping"
        case .macros: "tab.macros"
        case .profiles: "tab.profiles"
        }
    }

    var icon: String {
        switch self {
        case .lighting: "lightbulb.fill"
        case .mapping: "keyboard.fill"
        case .macros: "record.circle.fill"
        case .profiles: "square.stack.3d.up.fill"
        }
    }
}
