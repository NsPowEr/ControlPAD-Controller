import Foundation

/// Sottoinsieme pratico della USB HID Usage Table (pagina 0x07) per la
/// rimappatura semplice: lettere, cifre, funzione, navigazione, modificatori.
/// Non serve l'intera tabella — solo ciò che ha senso assegnare a un tasto.
struct HIDKey: Identifiable, Hashable, Sendable {
    let code: UInt8
    let label: String
    var id: UInt8 { code }
}

enum HIDKeycodes {
    static let letters: [HIDKey] = (0..<26).map {
        HIDKey(code: UInt8(0x04 + $0), label: String(UnicodeScalar(UInt8(65 + $0))))
    }

    static let digits: [HIDKey] = [
        .init(code: 0x1E, label: "1"), .init(code: 0x1F, label: "2"), .init(code: 0x20, label: "3"),
        .init(code: 0x21, label: "4"), .init(code: 0x22, label: "5"), .init(code: 0x23, label: "6"),
        .init(code: 0x24, label: "7"), .init(code: 0x25, label: "8"), .init(code: 0x26, label: "9"),
        .init(code: 0x27, label: "0"),
    ]

    static let function: [HIDKey] = (0..<12).map {
        HIDKey(code: UInt8(0x3A + $0), label: "F\($0 + 1)")
    }

    static let navigation: [HIDKey] = [
        .init(code: 0x4F, label: "→"), .init(code: 0x50, label: "←"),
        .init(code: 0x51, label: "↓"), .init(code: 0x52, label: "↑"),
        .init(code: 0x4A, label: "Home"), .init(code: 0x4D, label: "End"),
        .init(code: 0x4B, label: "PgUp"), .init(code: 0x4E, label: "PgDn"),
        .init(code: 0x49, label: "Ins"), .init(code: 0x4C, label: "Del"),
    ]

    static let whitespace: [HIDKey] = [
        .init(code: 0x28, label: "Enter"), .init(code: 0x2C, label: "Space"),
        .init(code: 0x2B, label: "Tab"), .init(code: 0x29, label: "Esc"),
        .init(code: 0x2A, label: "⌫"),
    ]

    static let punctuation: [HIDKey] = [
        .init(code: 0x2D, label: "-"), .init(code: 0x2E, label: "="),
        .init(code: 0x2F, label: "["), .init(code: 0x30, label: "]"),
        .init(code: 0x31, label: "\\"), .init(code: 0x33, label: ";"),
        .init(code: 0x34, label: "'"), .init(code: 0x35, label: "`"),
        .init(code: 0x36, label: ","), .init(code: 0x37, label: "."),
        .init(code: 0x38, label: "/"),
    ]

    static let modifiers: [HIDKey] = [
        .init(code: 0xE0, label: "LCtrl"), .init(code: 0xE1, label: "LShift"),
        .init(code: 0xE2, label: "LAlt"), .init(code: 0xE3, label: "LGUI"),
        .init(code: 0xE4, label: "RCtrl"), .init(code: 0xE5, label: "RShift"),
        .init(code: 0xE6, label: "RAlt"), .init(code: 0xE7, label: "RGUI"),
    ]

    static let groups: [(titleKey: String, keys: [HIDKey])] = [
        ("hid.group.letters", letters),
        ("hid.group.digits", digits),
        ("hid.group.function", function),
        ("hid.group.whitespace", whitespace),
        ("hid.group.navigation", navigation),
        ("hid.group.punctuation", punctuation),
        ("hid.group.modifiers", modifiers),
    ]

    static func label(for code: UInt8) -> String {
        groups.lazy.flatMap(\.keys).first { $0.code == code }?.label
            ?? String(format: "0x%02X", code)
    }
}
