import SwiftUI

/// Gli effetti dei quattro LED sopra il pad.
///
/// Il firmware non ne ha: il comando `55 50` all'indirizzo `0x00fc` scrive
/// dodici byte — quattro terzine RGB — e agisce **dal vivo**, senza passare dal
/// profilo e senza scrittura in flash. L'animazione la fa quindi l'host, a
/// differenza dell'illuminazione dei tasti dove l'effetto gira nel pad e l'app
/// manda un comando solo.
///
/// A disegnarla è il **motore Python** (`ControlPadEngine/indicatori.py`), non
/// questo file: il canale regge 250 fotogrammi al secondo, ma il ritmo va
/// tenuto con scadenze ancorate all'istante iniziale, e il ciclo Swift che
/// mandava un fotogramma per volta sommava invece i 6 ms di trasmissione alla
/// pausa — di 30 fps chiesti ne consegnava 26, con le fasi che divergevano fra
/// effetti. Qui restano soltanto identità, nome ed icona delle voci di menu;
/// gli `id` devono restare uguali a quelli di `indicatori.py`, perché sono ciò
/// che viaggia nel comando `start_indicator_effect`.
///
/// La conseguenza va detta all'utente e non nascosta: **il colore fisso resta,
/// l'effetto no.** Per questo ogni profilo porta entrambe le cose — i quattro
/// colori, che sono ciò con cui il pad rimane, e un effetto facoltativo sopra
/// che vive solo mentre l'app è aperta.
struct IndicatorEffect: Identifiable, Hashable, Sendable {
    let id: String
    let titleKey: String
    let icon: String
    /// true se l'effetto si fa i colori da sé e ignora quelli scelti: il
    /// colore *è* l'effetto, come nell'arcobaleno o nella palette del fuoco.
    let ignoresColors: Bool
}

enum IndicatorEffects {
    static let ledCount = 4

    static let defaultColors: [RGBColor] = Array(repeating: .white, count: ledCount)

    /// I diciassette di `indicatori.py`, nello stesso ordine: prima quelli che
    /// si muovono, poi quelli che cambiano colore fermi, poi quelli che devono
    /// comunicare qualcosa.
    static let all: [IndicatorEffect] = [
        .init(id: "rincorsa", titleKey: "indicator.effect.rincorsa",
              icon: "arrow.right.to.line", ignoresColors: false),
        .init(id: "cometa", titleKey: "indicator.effect.cometa",
              icon: "sparkle", ignoresColors: false),
        .init(id: "arrivo", titleKey: "indicator.effect.arrivo",
              icon: "arrow.left.to.line", ignoresColors: false),
        .init(id: "pendolo", titleKey: "indicator.effect.pendolo",
              icon: "arrow.left.arrow.right", ignoresColors: false),
        .init(id: "riempimento", titleKey: "indicator.effect.riempimento",
              icon: "chart.bar.fill", ignoresColors: false),
        .init(id: "onda", titleKey: "indicator.effect.onda",
              icon: "wave.3.forward", ignoresColors: false),
        .init(id: "arcobaleno", titleKey: "indicator.effect.arcobaleno",
              icon: "rainbow", ignoresColors: true),
        .init(id: "respiro", titleKey: "indicator.effect.respiro",
              icon: "lungs.fill", ignoresColors: false),
        .init(id: "battito", titleKey: "indicator.effect.battito",
              icon: "heart.fill", ignoresColors: false),
        .init(id: "brace", titleKey: "indicator.effect.brace",
              icon: "flame.fill", ignoresColors: true),
        .init(id: "scintille", titleKey: "indicator.effect.scintille",
              icon: "sparkles", ignoresColors: true),
        .init(id: "allarme", titleKey: "indicator.effect.allarme",
              icon: "exclamationmark.triangle.fill", ignoresColors: false),
        .init(id: "polizia", titleKey: "indicator.effect.polizia",
              icon: "light.beacon.max.fill", ignoresColors: true),
        .init(id: "notifica", titleKey: "indicator.effect.notifica",
              icon: "bell.badge.fill", ignoresColors: false),
        .init(id: "vu_meter", titleKey: "indicator.effect.vuMeter",
              icon: "waveform", ignoresColors: true),
        .init(id: "profilo", titleKey: "indicator.effect.profilo",
              icon: "square.stack.3d.up.fill", ignoresColors: false),
        .init(id: "countdown", titleKey: "indicator.effect.countdown",
              icon: "timer", ignoresColors: true),
    ]

    static func effect(id: String?) -> IndicatorEffect? {
        id.flatMap { key in all.first { $0.id == key } }
    }

    /// Esattamente quattro colori, comunque sia fatto l'array in arrivo: i
    /// profili salvati prima che i LED esistessero non ne hanno nessuno.
    static func normalized(_ colors: [RGBColor]) -> [RGBColor] {
        var out = Array(colors.prefix(ledCount))
        while out.count < ledCount { out.append(.white) }
        return out
    }

    /// Quello che si manda al pad quando non c'è nessun effetto: i colori
    /// scelti, scalati dalla luminosità — come fa il quarto byte del colore
    /// nei comandi del pad. È anche il fotogramma con cui si chiude
    /// un'animazione, così i LED non restano fermi a metà ciclo.
    static func staticFrame(base: [RGBColor], brightness: UInt8) -> [RGBColor] {
        normalized(base).map { $0.scaled(by: Double(brightness) / 255) }
    }
}

private extension RGBColor {
    func scaled(by factor: Double) -> RGBColor {
        func channel(_ value: UInt8) -> UInt8 {
            UInt8(clamping: Int((Double(value) * factor).rounded()))
        }
        return RGBColor(r: channel(r), g: channel(g), b: channel(b))
    }
}
