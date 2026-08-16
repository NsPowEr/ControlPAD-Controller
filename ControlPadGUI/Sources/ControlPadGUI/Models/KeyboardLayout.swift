import Foundation

/// Disposizione di una tastiera vera, per far scegliere il tasto dove l'utente
/// si aspetta di trovarlo invece che in un elenco alfabetico. È la stessa
/// scelta dell'app ufficiale, che sotto al pad disegna una tastiera intera.
///
/// Layout italiano, perché è quello su cui il pad viene usato e perché
/// `macro.py` codifica già la punteggiatura con quella logica.
struct KeyboardKey: Identifiable, Hashable, Sendable {
    let usage: UInt8
    let label: String
    /// Larghezza in unità di tasto: 1 è un tasto normale.
    let width: Double
    /// Etichetta secondaria (il carattere con Shift), quando aiuta.
    let shifted: String?

    var id: UInt8 { usage }

    init(_ usage: UInt8, _ label: String, width: Double = 1, shifted: String? = nil) {
        self.usage = usage
        self.label = label
        self.width = width
        self.shifted = shifted
    }
}

enum KeyboardLayout {
    /// Uno spazio vuoto fra i gruppi di tasti, non un tasto.
    static let gap = KeyboardKey(0x00, "", width: 0.5)

    static let mainRows: [[KeyboardKey]] = [
        [
            .init(0x29, "esc"), gap,
            .init(0x3A, "F1"), .init(0x3B, "F2"), .init(0x3C, "F3"), .init(0x3D, "F4"), gap,
            .init(0x3E, "F5"), .init(0x3F, "F6"), .init(0x40, "F7"), .init(0x41, "F8"), gap,
            .init(0x42, "F9"), .init(0x43, "F10"), .init(0x44, "F11"), .init(0x45, "F12"),
        ],
        [
            .init(0x35, "\\", shifted: "|"),
            .init(0x1E, "1", shifted: "!"), .init(0x1F, "2", shifted: "\""),
            .init(0x20, "3", shifted: "£"), .init(0x21, "4", shifted: "$"),
            .init(0x22, "5", shifted: "%"), .init(0x23, "6", shifted: "&"),
            .init(0x24, "7", shifted: "/"), .init(0x25, "8", shifted: "("),
            .init(0x26, "9", shifted: ")"), .init(0x27, "0", shifted: "="),
            .init(0x2D, "'", shifted: "?"), .init(0x2E, "ì", shifted: "^"),
            .init(0x2A, "⌫", width: 1.8),
        ],
        [
            .init(0x2B, "⇥", width: 1.5),
            .init(0x14, "Q"), .init(0x1A, "W"), .init(0x08, "E"), .init(0x15, "R"),
            .init(0x17, "T"), .init(0x1C, "Y"), .init(0x18, "U"), .init(0x0C, "I"),
            .init(0x12, "O"), .init(0x13, "P"),
            .init(0x2F, "è", shifted: "é"), .init(0x30, "+", shifted: "*"),
            .init(0x28, "↩", width: 1.3),
        ],
        [
            .init(0x39, "⇪", width: 1.8),
            .init(0x04, "A"), .init(0x16, "S"), .init(0x07, "D"), .init(0x09, "F"),
            .init(0x0A, "G"), .init(0x0B, "H"), .init(0x0D, "J"), .init(0x0E, "K"),
            .init(0x0F, "L"),
            .init(0x33, "ò", shifted: "ç"), .init(0x34, "à", shifted: "°"),
            .init(0x31, "ù", shifted: "§"),
        ],
        [
            .init(0xE1, "⇧", width: 1.3),
            .init(0x64, "<", shifted: ">"),
            .init(0x1D, "Z"), .init(0x1B, "X"), .init(0x06, "C"), .init(0x19, "V"),
            .init(0x05, "B"), .init(0x11, "N"), .init(0x10, "M"),
            .init(0x36, ",", shifted: ";"), .init(0x37, ".", shifted: ":"),
            .init(0x38, "-", shifted: "_"),
            .init(0xE5, "⇧", width: 1.8),
        ],
        [
            .init(0xE0, "ctrl", width: 1.3), .init(0xE3, "⌘"), .init(0xE2, "⌥", width: 1.3),
            .init(0x2C, "spazio", width: 6),
            .init(0xE6, "⌥", width: 1.3), .init(0xE7, "⌘"), .init(0xE4, "ctrl", width: 1.3),
        ],
    ]

    /// Blocco navigazione e frecce, di fianco alla tastiera principale.
    static let navigationRows: [[KeyboardKey]] = [
        [.init(0x49, "ins"), .init(0x4A, "↖"), .init(0x4B, "⇞")],
        [.init(0x4C, "canc"), .init(0x4D, "↘"), .init(0x4E, "⇟")],
        [],
        [.init(0x00, "", width: 1), .init(0x52, "↑"), .init(0x00, "", width: 1)],
        [.init(0x50, "←"), .init(0x51, "↓"), .init(0x4F, "→")],
    ]

    static var allKeys: [KeyboardKey] {
        (mainRows + navigationRows).flatMap { $0 }.filter { $0.usage != 0 }
    }

    static func label(for usage: UInt8) -> String {
        allKeys.first { $0.usage == usage }?.label
            ?? String(format: "0x%02X", usage)
    }
}
