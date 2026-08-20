import Foundation

/// Configurazione salvata lato host. Sul dispositivo esiste una sola sessione
/// attiva (macro, keymap, blob di illuminazione a 14 slot): nessuna cattura
/// ha mai mostrato un comando che scriva su un banco N diverso da quello
/// attivo. "Profilo" qui è quindi un preset locale, riapplicato per intero
/// con una scrittura di sessione quando lo selezioni — esattamente come fa
/// già l'app ufficiale per l'illuminazione, che infatti non sopravvive allo
/// scollegamento nemmeno lì. Vedi il piano in
/// ~/.claude/plans/swift-crafting-wind.md, sezione "Punto aperto".
struct Preset: Identifiable, Codable, Sendable, Hashable {
    var id: UUID
    var name: String
    var lighting: LightingConfig
    var remaps: [UInt8: RemapAction]
    var macros: [MacroAssignment]
    /// Indice per colonne -> numero di profilo che quel tasto attiva (51 90).
    var profileSelectors: [Int: Int]

    init(name: String) {
        id = UUID()
        self.name = name
        lighting = LightingConfig()
        remaps = [:]
        macros = []
        profileSelectors = [:]
    }

    /// Macro che fallirebbero silenziosamente se scritte così — vedi
    /// MacroAssignment.validationError. Controllato prima di ogni scrittura
    /// (WriteSessionBar), non solo mostrato come avviso nell'editor.
    var invalidMacros: [MacroAssignment] {
        macros.filter { $0.validationError != nil }
    }

    /// Tasti fisici con sia una macro (51 18) sia una rimappatura (51 20)
    /// assegnate: comportamento del device in quel caso non documentato in
    /// nessuna cattura. Non blocca l'invio — potrebbe funzionare — ma va
    /// segnalato invece di restare invisibile.
    var keysWithMacroAndRemapConflict: Set<UInt8> {
        Set(macros.map(\.key)).intersection(remaps.keys)
    }
}

struct EffectSlotConfig: Codable, Sendable, Hashable {
    var color: RGBColor = .white
    var secondColor: RGBColor = .white
    var speed: UInt8 = Effects.defaultSpeed
    
    init(color: RGBColor = .white, secondColor: RGBColor = .white, speed: UInt8 = Effects.defaultSpeed) {
        self.color = color
        self.secondColor = secondColor
        self.speed = speed
    }
}

struct LightingConfig: Codable, Sendable, Hashable {
    var modeID: String = "static"
    var color: RGBColor = .white
    /// Secondo colore delle sei modalità reattive al tocco: il colore con cui
    /// il pad risponde alla pressione, distinto da quello di fondo.
    var secondColor: RGBColor = .white
    var speed: UInt8 = Effects.defaultSpeed
    var brightness: UInt8 = 255
    /// Usato solo dalla modalità "Personalizza" (colore per singolo tasto).
    var perKeyColors: [GridPosition: RGBColor] = [:]
    
    /// Tutti gli slot modificabili, così quando si cambia modalità o si salva
    /// vengono scritti tutti e restano selezionabili tramite hardware.
    var slots: [String: EffectSlotConfig] = [:]

    /// I quattro LED sopra il pad, da sinistra a destra. Hanno un comando
    /// tutto loro (`55 50`) e non fanno parte della tabella per-tasto: sono
    /// l'unica parte dell'illuminazione che resta accesa anche con l'app
    /// chiusa, perché il pad la conserva finché non gli si scrive sopra.
    var indicatorColors: [RGBColor] = IndicatorEffects.defaultColors
    /// Effetto animato sui quattro LED, nil = solo colore statico. Il
    /// firmware non ne ha: lo disegna l'app, quindi gira solo mentre è
    /// aperta — vedi IndicatorEffects.
    var indicatorEffect: String?

    private enum CodingKeys: String, CodingKey {
        case modeID, color, secondColor, speed, brightness, perKeyColors
        case slots, indicatorColors, indicatorEffect
    }

    init() {}

    /// I profili salvati prima che esistesse il secondo colore non lo hanno:
    /// senza questo, ricaricarli fallirebbe.
    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        modeID = try c.decodeIfPresent(String.self, forKey: .modeID) ?? "static"
        color = try c.decodeIfPresent(RGBColor.self, forKey: .color) ?? .white
        secondColor = try c.decodeIfPresent(RGBColor.self, forKey: .secondColor) ?? .white
        speed = try c.decodeIfPresent(UInt8.self, forKey: .speed) ?? Effects.defaultSpeed
        brightness = try c.decodeIfPresent(UInt8.self, forKey: .brightness) ?? 255
        perKeyColors = try c.decodeIfPresent([GridPosition: RGBColor].self,
                                              forKey: .perKeyColors) ?? [:]
        slots = try c.decodeIfPresent([String: EffectSlotConfig].self, forKey: .slots) ?? [:]
        let saved = try c.decodeIfPresent([RGBColor].self, forKey: .indicatorColors)
        indicatorColors = IndicatorEffects.normalized(saved ?? IndicatorEffects.defaultColors)
        indicatorEffect = try c.decodeIfPresent(String.self, forKey: .indicatorEffect)
    }
}

/// Un singolo passo di una macro a eventi grezzi: premi o rilascia `usage`
/// dopo `delayMs` millisecondi dal passo precedente (macro.py: 4 byte,
/// ritardo a 16 bit little-endian).
struct MacroEvent: Identifiable, Codable, Sendable, Hashable {
    var id = UUID()
    var usage: UInt8
    var isPress: Bool
    var delayMs: UInt16

    private enum CodingKeys: String, CodingKey { case usage, isPress, delayMs }
}

struct MacroAssignment: Identifiable, Codable, Sendable, Hashable {
    var id: UUID = UUID()
    var slot: Int
    var key: UInt8
    var name: String
    var kind: Kind

    enum Kind: Codable, Sendable, Hashable {
        case text(String)
        case combo([UInt8])
        /// Pressione/rilascio con ritardo esplicito — come li registra
        /// l'app ufficiale premendo i tasti a mano invece di digitare testo.
        case raw([MacroEvent])
    }

    /// Conteggio esatto: per il testo replica events_for() byte per byte
    /// (MacroEncoding, non un'approssimazione — un `*2` ignorava gli eventi
    /// extra dei cambi Shift). Per combinazione e eventi grezzi il conteggio
    /// è già esatto per costruzione.
    var estimatedEventCount: Int {
        switch kind {
        case .text(let s): return MacroEncoding.eventCount(forText: s)
        case .combo(let usages): return usages.count * 2
        case .raw(let events): return events.count
        }
    }

    /// Non esiste un tetto a 15 eventi. Quel numero è la capienza di *un*
    /// report da 64 byte, ma `macro_packets()` spezza le macro lunghe su più
    /// report col byte di continuazione, e la cosa è stata verificata sul
    /// dispositivo fino a 49 eventi su 4 report (vedi stato.html, sezione
    /// "Macro di lunghezza arbitraria"). Sopra quella soglia nessuno ha
    /// ancora provato: si avvisa, non si blocca.
    static let verifiedEventCeiling = 49

    /// Il campo nome finisce grezzo dopo l'header di 51 19 in un report da
    /// 64 byte — PROTOCOL.md lo documenta come un solo byte nelle catture
    /// originali ("da confermare con una macro dal nome non banale"), mai
    /// verificato oltre un singolo carattere. 12 byte è un margine
    /// prudente, non un limite noto del device.
    static let maxNameBytes = 12

    /// nil = pronta per essere scritta. Controllato prima di ogni invio,
    /// non solo mostrato come avviso: vedi WriteSessionBar.
    var validationError: MacroValidationError? {
        if name.utf8.count > Self.maxNameBytes {
            return .nameTooLong(name.utf8.count)
        }
        if case .text(let text) = kind {
            let bad = MacroEncoding.unmappableCharacters(in: text)
            if !bad.isEmpty { return .unmappableCharacters(bad) }
        }
        if estimatedEventCount == 0 {
            return .empty
        }
        return nil
    }

    /// Lunga oltre quanto è stato provato sul dispositivo: non è un errore,
    /// ma vale la pena dirlo prima che l'utente dia la colpa all'app.
    var isBeyondVerifiedLength: Bool {
        estimatedEventCount > Self.verifiedEventCeiling
    }
}

enum MacroValidationError: Equatable {
    case unmappableCharacters([Character])
    case nameTooLong(Int)
    case empty
}
