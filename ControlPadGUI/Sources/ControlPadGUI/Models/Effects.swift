import Foundation

/// Le 14 modalità di illuminazione, nello stesso ordine in cui le elenca il
/// software ufficiale. Nessuna è più bloccata: i sei effetti reattivi al
/// tocco usavano una forma di comando più lunga che ora è decodificata, e
/// portano un **secondo colore** — vedi ControlPadEngine/effects.py per come
/// è stata ricavata dalle catture.
///
/// Le chiavi qui devono restare uguali a quelle di effects.py: sono ciò che
/// viaggia nel comando `set_mode`. I byte veri stanno solo lì.
enum LightingKind: Sendable, Hashable {
    /// Modalità gestita dal firmware: il motore replica il report registrato
    /// dall'app sostituendo colori e velocità.
    case device(dual: Bool)
    /// Tabella per-tasto ("Personalizza"): passa da set_grid, non da set_mode.
    case perKeyGrid
}

struct LightingMode: Identifiable, Sendable, Hashable {
    let id: String
    let titleKey: String
    let icon: String
    let kind: LightingKind

    /// true se la modalità espone un secondo colore.
    var hasSecondColor: Bool {
        if case .device(let dual) = kind { return dual }
        return false
    }

    /// Modalità che si fanno i colori da sole: scorrono l'intera ruota e
    /// ignorano quello che si sceglie. Mostrare un selettore colore lì
    /// significa promettere una cosa che il pad non fa — restano velocità e
    /// luminosità, che invece contano.
    static let rainbowIDs: Set<String> = [
        "rainbowWave", "colorCycle", "circularSpectrum", "reactiveTornado",
    ]

    var usesColor: Bool { !Self.rainbowIDs.contains(id) && id != "off" }

    /// Arcobaleno per costruzione: lo dice la UI al posto del selettore.
    var isRainbow: Bool { Self.rainbowIDs.contains(id) }

    var usesSpeed: Bool {
        switch id {
        case "static", "custom", "off": return false
        default: return true
        }
    }
}

enum Effects {
    static let modes: [LightingMode] = [
        .init(id: "static", titleKey: "effect.static",
              icon: "circle.fill", kind: .device(dual: false)),
        .init(id: "rainbowWave", titleKey: "effect.rainbowWave",
              icon: "rainbow", kind: .device(dual: false)),
        .init(id: "crosshair", titleKey: "effect.crosshair",
              icon: "plus.viewfinder", kind: .device(dual: true)),
        .init(id: "reactiveFade", titleKey: "effect.reactiveFade",
              icon: "aqi.medium", kind: .device(dual: true)),
        .init(id: "custom", titleKey: "effect.custom",
              icon: "paintpalette.fill", kind: .perKeyGrid),
        .init(id: "stars", titleKey: "effect.stars",
              icon: "sparkles", kind: .device(dual: true)),
        .init(id: "snow", titleKey: "effect.snow",
              icon: "snowflake", kind: .device(dual: true)),
        .init(id: "colorCycle", titleKey: "effect.colorCycle",
              icon: "arrow.triangle.2.circlepath", kind: .device(dual: false)),
        .init(id: "blink", titleKey: "effect.blink",
              icon: "light.beacon.max.fill", kind: .device(dual: false)),
        .init(id: "reactivePunch", titleKey: "effect.reactivePunch",
              icon: "burst.fill", kind: .device(dual: true)),
        .init(id: "circularSpectrum", titleKey: "effect.circularSpectrum",
              icon: "circle.hexagongrid.fill", kind: .device(dual: false)),
        .init(id: "reactiveTornado", titleKey: "effect.reactiveTornado",
              icon: "tornado", kind: .device(dual: false)),
        .init(id: "waterRipple", titleKey: "effect.waterRipple",
              icon: "drop.circle.fill", kind: .device(dual: true)),
        .init(id: "off", titleKey: "effect.off",
              icon: "power", kind: .device(dual: false)),
    ]

    static func mode(id: String) -> LightingMode {
        modes.first { $0.id == id } ?? modes[0]
    }

    static let defaultSpeed: UInt8 = 0x08
}
