import Foundation

/// Specchio esatto di ControlPadEngine/macro.py — non un'approssimazione.
/// Serve a poter validare e contare gli eventi lato Swift, prima di
/// mandare qualunque cosa al motore, senza duplicare la logica in modo
/// impreciso (era esattamente il bug: `testo.count * 2` ignorava gli
/// eventi extra dei cambi di stato Shift).
enum MacroEncoding {
    /// Tabella CHARS di macro.py: carattere -> richiede Shift. Un carattere
    /// assente da questa mappa non è codificabile — events_for() lo
    /// rifiuterebbe lato motore.
    private static let requiresShift: [Character: Bool] = {
        var map: [Character: Bool] = [:]
        for c in "abcdefghijklmnopqrstuvwxyz" { map[c] = false }
        for c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ" { map[c] = true }
        for c in "1234567890" { map[c] = false }
        map[" "] = false
        map["!"] = true
        map["|"] = true
        map["\\"] = false
        map["<"] = false
        map[">"] = true
        return map
    }()

    static func isMappable(_ ch: Character) -> Bool {
        requiresShift[ch] != nil
    }

    static func unmappableCharacters(in text: String) -> [Character] {
        var seen: [Character] = []
        for ch in text where !isMappable(ch) && !seen.contains(ch) {
            seen.append(ch)
        }
        return seen
    }

    /// Conteggio esatto degli eventi che genererebbe events_for(): 2 per
    /// carattere (pressione+rilascio) più 1 per ogni transizione dello stato
    /// Shift, compreso il rilascio finale se il testo termina con Shift giù.
    /// Ignora i caratteri non mappabili (contati a parte da unmappableCharacters,
    /// e comunque bloccanti prima dell'invio).
    static func eventCount(forText text: String) -> Int {
        var count = 0
        var shiftDown = false
        for ch in text {
            guard let needsShift = requiresShift[ch] else { continue }
            if needsShift != shiftDown {
                count += 1
                shiftDown = needsShift
            }
            count += 2
        }
        if shiftDown { count += 1 }
        return count
    }
}
