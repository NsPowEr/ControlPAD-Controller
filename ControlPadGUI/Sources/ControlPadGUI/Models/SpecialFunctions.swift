import Foundation

/// Funzioni interne del dispositivo assegnabili a un tasto o a una rotella,
/// codice a 16 bit ≥ 0x0100 nel campo azione di 51 20 (session.py: FUNZIONI).
struct SpecialFunction: Identifiable, Hashable, Codable, Sendable {
    let code: UInt16
    let titleKey: String
    /// Etichetta compatta per il tasto 54pt sulla griglia — non localizzata,
    /// stessa idea delle etichette troncate ("M3", "DISABILI...") dell'app
    /// originale sui suoi tasti altrettanto piccoli.
    let shortLabel: String
    /// SF Symbol: su una griglia si riconosce la funzione dall'icona molto
    /// prima che leggendone il nome.
    let icon: String
    /// Raggruppamento nella griglia, così media e retroilluminazione non si
    /// mescolano.
    let group: Group
    var id: UInt16 { code }

    enum Group: String, Codable, Sendable, CaseIterable {
        case media, lighting, profile
        var titleKey: String {
            switch self {
            case .media: "function.group.media"
            case .lighting: "function.group.lighting"
            case .profile: "function.group.profile"
            }
        }
    }
}

enum SpecialFunctions {
    static let all: [SpecialFunction] = [
        .init(code: 0x00F0, titleKey: "function.playPause", shortLabel: "⏯",
              icon: "playpause.fill", group: .media),
        .init(code: 0x00F1, titleKey: "function.stop", shortLabel: "⏹",
              icon: "stop.fill", group: .media),
        .init(code: 0x00F2, titleKey: "function.previousTrack", shortLabel: "⏮",
              icon: "backward.end.fill", group: .media),
        .init(code: 0x00F3, titleKey: "function.nextTrack", shortLabel: "⏭",
              icon: "forward.end.fill", group: .media),
        .init(code: 0x00F4, titleKey: "function.mute", shortLabel: "Muto",
              icon: "speaker.slash.fill", group: .media),
        .init(code: 0x00F5, titleKey: "function.volumeDown", shortLabel: "Vol−",
              icon: "speaker.wave.1.fill", group: .media),
        .init(code: 0x00F6, titleKey: "function.volumeUp", shortLabel: "Vol+",
              icon: "speaker.wave.3.fill", group: .media),
        .init(code: 0x0181, titleKey: "function.effectCycleForward", shortLabel: "FX→",
              icon: "arrow.forward.circle.fill", group: .lighting),
        .init(code: 0x0182, titleKey: "function.effectCycleBackward", shortLabel: "FX←",
              icon: "arrow.backward.circle.fill", group: .lighting),
        .init(code: 0x0190, titleKey: "function.speedDown", shortLabel: "Vel−",
              icon: "tortoise.fill", group: .lighting),
        .init(code: 0x0191, titleKey: "function.speedUp", shortLabel: "Vel+",
              icon: "hare.fill", group: .lighting),
        .init(code: 0x0192, titleKey: "function.brightnessUp", shortLabel: "LED+",
              icon: "sun.max.fill", group: .lighting),
        .init(code: 0x0193, titleKey: "function.brightnessDown", shortLabel: "LED−",
              icon: "sun.min.fill", group: .lighting),
        .init(code: 0x0110, titleKey: "function.selectProfile", shortLabel: "Prof",
              icon: "square.stack.3d.up.fill", group: .profile),
    ]

    static func inGroup(_ group: SpecialFunction.Group) -> [SpecialFunction] {
        all.filter { $0.group == group }
    }

    /// Codice che riporta un tasto al comportamento di fabbrica (NESSUNA_RIMAPPATURA).
    static let none: UInt16 = 0x00FF

    /// Ciclo degli effetti in avanti. È il comportamento di fabbrica del solo
    /// tasto n.22, l'unico dei ventiquattro che non ha un carattere da battere.
    static let effectCycleForward: UInt16 = 0x0181

    /// "Questo tasto cambia profilo" — e basta: *quale* profilo sta in una
    /// tabella a parte (`51 90`, indicizzata per colonne). Servono entrambe le
    /// scritture, o il tasto conserva l'assegnazione che aveva prima.
    static let selectProfile: UInt16 = 0x0110

    /// Quanti banchi di profilo ha il device. Ventiquattro come i tasti: la
    /// tabella `51 90` porta un numero di profilo per tasto, un byte ciascuno.
    static let profileCount = 24

    /// Tasto muto: premendolo non esce niente.
    ///
    /// Non è un'invenzione: nelle catture l'app ufficiale scrive `0x0000`
    /// nella keymap esattamente sui tasti a cui è stata assegnata una macro —
    /// per non far uscire anche il carattere di fabbrica insieme alla macro.
    /// È lo stesso codice che serve per un tasto disattivato.
    static let disabled: UInt16 = 0x0000

    static func function(for code: UInt16) -> SpecialFunction? {
        all.first { $0.code == code }
    }
}

/// Cosa fa un tasto una volta rimappato: un altro tasto, una funzione interna,
/// o il comportamento di fabbrica.
enum RemapAction: Codable, Hashable, Sendable {
    case key(UInt8)
    case function(SpecialFunction)
    /// Tasto muto: premuto non scrive niente.
    case disabled
    case factoryDefault

    var rawValue: UInt16 {
        switch self {
        case .key(let k): return UInt16(k)
        case .function(let f): return f.code
        case .disabled: return SpecialFunctions.disabled
        case .factoryDefault: return SpecialFunctions.none
        }
    }

    init(rawValue: UInt16) {
        if rawValue == SpecialFunctions.none {
            self = .factoryDefault
        } else if rawValue == SpecialFunctions.disabled {
            self = .disabled
        } else if rawValue >= 0x0100, let f = SpecialFunctions.function(for: rawValue) {
            self = .function(f)
        } else if rawValue < 0x0100 {
            self = .key(UInt8(rawValue))
        } else {
            self = .factoryDefault
        }
    }
}
