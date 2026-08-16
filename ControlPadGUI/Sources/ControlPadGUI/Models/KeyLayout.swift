import Foundation

/// Posizione nella griglia 5×5, 0-based dall'alto a sinistra — stesso ordine
/// (colonna, riga) che usa controlpad.py in set_grid, per non dover
/// convertire avanti e indietro al confine col bridge.
struct GridPosition: Hashable, Codable, Sendable {
    var col: Int
    var row: Int
}

/// Porta di layout.py: il pad numera le stesse 24 posizioni in tre modi
/// diversi (codice HID, indice per colonne, indice per righe) e confonderli
/// è l'errore più insidioso del protocollo. Vedi PROTOCOL.md.
enum KeyLayout {
    static let rows = 5
    static let cols = 5
    static let indicatorLEDs = 4

    /// Codici HID di default, riga per riga come li carica la keymap.
    /// nil dove lo spazio (tasto largo) occupa la posizione.
    static let grid: [[UInt8?]] = [
        [0x35, 0x1E, 0x1F, 0x20, 0x21],   // `  1  2  3  4
        [0x2B, 0x14, 0x1A, 0x08, 0x15],   // Tab Q  W  E  R
        [0x39, 0x04, 0x16, 0x07, 0x09],   // Caps A  S  D  F
        [0xE1, 0x1D, 0x1B, 0x06, 0x19],   // Shift Z  X  C  V
        [0xE0, 0xC0, 0xE2, 0x2C, nil],    // Ctrl  ·  Alt  Spazio (largo)
    ]

    static let defaultLabels: [UInt8: String] = [
        0x35: "`", 0x1E: "1", 0x1F: "2", 0x20: "3", 0x21: "4",
        0x2B: "Tab", 0x14: "Q", 0x1A: "W", 0x08: "E", 0x15: "R",
        0x39: "Caps", 0x04: "A", 0x16: "S", 0x07: "D", 0x09: "F",
        0xE1: "Shift", 0x1D: "Z", 0x1B: "X", 0x06: "C", 0x19: "V",
        0xE0: "Ctrl", 0xC0: "·", 0xE2: "Alt", 0x2C: "Space",
    ]

    /// Le due rotelle in alto. Nella keymap sono quattro pseudo-tasti — una
    /// coppia di codici per rotella, uno per verso — e accettano lo stesso
    /// comando `51 20` dei tasti, quindi qualunque tasto o funzione.
    ///
    /// Attenzione ai due namespace: `0xF5`/`0xF6` qui sono *quale* pseudo-tasto,
    /// mentre `0x00F5`/`0x00F6` nel campo azione sono Volume −/+. Non
    /// c'entrano niente l'uno con l'altro.
    struct Wheel: Identifiable, Hashable, Sendable {
        let id: String
        let titleKey: String
        let counterClockwise: UInt8
        let clockwise: UInt8
        /// Cosa fanno i due versi appena uscite di fabbrica. Non è una
        /// supposizione: rileggendo le catture con `51 20` si vedono già
        /// assegnate così in tutte e sei, prima che si toccasse niente.
        let factoryCounterClockwise: UInt16
        let factoryClockwise: UInt16
    }

    static let wheels: [Wheel] = [
        .init(id: "left", titleKey: "mapping.wheel.left",
              counterClockwise: 0xC6, clockwise: 0xC7,
              factoryCounterClockwise: 0x0192,   // LED più luminoso
              factoryClockwise: 0x0193),         // LED più scuro
        .init(id: "right", titleKey: "mapping.wheel.right",
              counterClockwise: 0xF5, clockwise: 0xF6,
              factoryCounterClockwise: 0x00F5,   // Volume −
              factoryClockwise: 0x00F6),         // Volume +
    ]

    /// L'azione di fabbrica di un verso di rotella, se quel codice è una rotella.
    static func factoryAction(forWheelKey code: UInt8) -> UInt16? {
        for wheel in wheels {
            if wheel.counterClockwise == code { return wheel.factoryCounterClockwise }
            if wheel.clockwise == code { return wheel.factoryClockwise }
        }
        return nil
    }

    static let wheelKeys: [UInt8] = wheels.flatMap { [$0.counterClockwise, $0.clockwise] }

    static func isWheelKey(_ code: UInt8) -> Bool { wheelKeys.contains(code) }

    static func key(at position: GridPosition) -> UInt8? {
        grid[position.row][position.col]
    }

    /// Il numero serigrafato sul pad, 1–24, da sinistra a destra e dall'alto
    /// in basso, con il tasto largo che chiude come 24. È l'unico riferimento
    /// che l'utente vede davvero sull'hardware: i codici HID di default
    /// (`, 1, Tab, Q…) sono quello che il pad *batte*, non quello che c'è
    /// scritto sui tasti.
    static func number(at position: GridPosition) -> Int {
        position.row * cols + position.col + 1
    }

    static func position(forNumber number: Int) -> GridPosition? {
        let index = number - 1
        guard index >= 0, index < rows * cols else { return nil }
        let position = GridPosition(col: index % cols, row: index / cols)
        return grid[position.row][position.col] != nil ? position : nil
    }

    static func number(forKey hidCode: UInt8) -> Int? {
        position(of: hidCode).map(number(at:))
    }

    /// Indice per colonne: la numerazione di LED e tabella profili.
    static func columnIndex(_ position: GridPosition) -> Int {
        position.col * rows + position.row
    }

    /// Indice del LED sotto quella posizione, nella tabella dei colori.
    static func ledIndex(_ position: GridPosition) -> Int {
        indicatorLEDs + columnIndex(position)
    }

    static func position(of hidCode: UInt8) -> GridPosition? {
        for row in 0..<rows {
            for col in 0..<cols where grid[row][col] == hidCode {
                return GridPosition(col: col, row: row)
            }
        }
        return nil
    }

    /// L'inverso di columnIndex: serve per leggere la tabella dei profili.
    static func key(atColumnIndex index: Int) -> UInt8? {
        let col = index / rows
        let row = index % rows
        guard row < rows, col < cols else { return nil }
        return grid[row][col]
    }

    static var allKeys: [UInt8] {
        grid.flatMap { $0 }.compactMap { $0 }
    }

    static var allPositions: [GridPosition] {
        (0..<rows).flatMap { row in
            (0..<cols).compactMap { col -> GridPosition? in
                grid[row][col] != nil ? GridPosition(col: col, row: row) : nil
            }
        }
    }
}
