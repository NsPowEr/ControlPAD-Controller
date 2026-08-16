import Foundation

/// Costruttori tipizzati sopra PythonBridge.send: ogni funzione qui
/// corrisponde a un comando di bridge.py. Nessuna logica di protocollo
/// vive qui — solo la busta JSON, esattamente come in bridge.py.
extension PythonBridge {
    @discardableResult
    func ping() async throws -> Bool {
        let reply = try await send("ping")
        return reply["pong"]?.boolValue ?? false
    }

    func status() async throws -> Bool {
        let reply = try await send("status")
        return reply["present"]?.boolValue ?? false
    }

    func setStatic(_ color: RGBColor, brightness: UInt8 = 255) async throws {
        try await send("set_static", [
            "r": .int(Int(color.r)), "g": .int(Int(color.g)), "b": .int(Int(color.b)),
            "brightness": .int(Int(brightness)),
        ])
    }

    /// Seleziona una delle 14 modalità per nome. Il motore replica il report
    /// registrato dal software ufficiale e ne sostituisce solo i campi
    /// passati qui: è l'unica strada che raggiunge anche le sei modalità
    /// reattive al tocco, che hanno un secondo colore.
    func setMode(_ mode: LightingMode, color: RGBColor, secondColor: RGBColor,
                 speed: UInt8, brightness: UInt8) async throws {
        var payload: [String: JSONValue] = ["mode": .string(mode.id)]

        if mode.usesColor {
            payload["color1"] = rgba(color, brightness)
            if mode.hasSecondColor {
                payload["color2"] = rgba(secondColor, brightness)
            }
        }
        if mode.usesSpeed {
            payload["speed"] = .int(Int(speed))
        }
        try await send("set_mode", payload)
    }

    private func rgba(_ c: RGBColor, _ a: UInt8) -> JSONValue {
        .array([.int(Int(c.r)), .int(Int(c.g)), .int(Int(c.b)), .int(Int(a))])
    }

    /// colors: posizione (colonna, riga) 0-based -> colore. Le posizioni non
    /// elencate si spengono, come fa set_leds lato Python.
    func setGrid(_ colors: [GridPosition: RGBColor]) async throws {
        var object: [String: JSONValue] = [:]
        for (pos, color) in colors {
            object["\(pos.col),\(pos.row)"] = .array([.int(Int(color.r)), .int(Int(color.g)), .int(Int(color.b))])
        }
        try await send("set_grid", ["colors": .object(object)])
    }

    /// I 4 LED indicatori sopra il pad, in ordine da sinistra a destra.
    ///
    /// `stream` distingue il fotogramma di un'animazione dal colore fisso: nel
    /// primo caso il motore tiene aperto il device fra un fotogramma e il
    /// successivo, nel secondo lo apre e lo richiude, così non resta occupato
    /// per sempre dopo una singola scrittura.
    func setIndicators(_ colors: [RGBColor], stream: Bool = false) async throws {
        let array = colors.map { c in
            JSONValue.array([.int(Int(c.r)), .int(Int(c.g)), .int(Int(c.b))])
        }
        try await send("set_indicators", [
            "colors": .array(array),
            "stream": .bool(stream),
        ])
    }

    /// Avvia un effetto sui quattro LED indicatori. Un comando solo per tutta
    /// l'animazione: il motore la disegna nel suo thread finché non gli si dice
    /// di smettere, con le scadenze ancorate all'istante iniziale — cosa che un
    /// ciclo di qui, che paga la latenza del bridge a ogni fotogramma, non può
    /// fare. `colors` sono i quattro colori grezzi: la luminosità la applica il
    /// motore per ultima, così non viene contata due volte.
    func startIndicatorEffect(_ effect: IndicatorEffect, colors: [RGBColor],
                              speed: UInt8, brightness: UInt8) async throws {
        func triplets(_ list: [RGBColor]) -> JSONValue {
            .array(list.map { c in
                .array([.int(Int(c.r)), .int(Int(c.g)), .int(Int(c.b))])
            })
        }
        try await send("start_indicator_effect", [
            "effect": .string(effect.id),
            "colors": triplets(IndicatorEffects.normalized(colors)),
            "speed": .int(Int(speed)),
            "brightness": .int(Int(brightness)),
            // I colori fissi a cui tornare quando l'animazione finisce. Vanno
            // mandati adesso perché uno dei modi in cui finisce è la chiusura
            // dell'app: a quel punto il motore non può più chiederli a nessuno,
            // e senza di essi il pad resta sull'ultimo fotogramma anche dopo
            // essere stato staccato e riattaccato.
            "static": triplets(IndicatorEffects.staticFrame(base: colors,
                                                            brightness: brightness)),
        ])
    }

    /// Ferma l'effetto e rimette i colori fissi passati qui, altrimenti i LED
    /// resterebbero sul fotogramma a metà ciclo in cui li ha colti lo stop.
    func stopIndicatorEffect(restoring colors: [RGBColor]) async throws {
        let array = colors.map { c in
            JSONValue.array([.int(Int(c.r)), .int(Int(c.g)), .int(Int(c.b))])
        }
        try await send("stop_indicator_effect", ["colors": .array(array)])
    }

    /// I quattro colori che il pad ha davvero, riletti dall'indirizzo `0x00fc`.
    /// Serve a distinguere una scrittura ignorata da una scrittura accolta e
    /// non mostrata — è il controllo che manca a occhio.
    func readIndicators() async throws -> [RGBColor]? {
        let reply = try await send("read_indicators")
        guard let rows = reply["colors"]?.arrayValue else { return nil }
        return rows.compactMap { row in
            guard let c = row.arrayValue, c.count == 3,
                  let r = c[0].intValue, let g = c[1].intValue, let b = c[2].intValue
            else { return nil }
            return RGBColor(r: UInt8(clamping: r), g: UInt8(clamping: g),
                            b: UInt8(clamping: b))
        }
    }

    /// Scrittura permanente: macro, rimappature, illuminazione salvata nel
    /// profilo, tasti selettori. Corrisponde a session.scrivi().
    ///
    /// Restituisce quanti report non hanno ricevuto la loro conferma. Zero è
    /// l'unico valore che dica che la scrittura è passata tutta: il device
    /// ACKa anche quello che non esegue, ma non ACKare affatto è un guasto, e
    /// tacerlo lo farebbe somigliare a un successo.
    @discardableResult
    func writeSession(preset: Preset) async throws -> Int {
        var payload: [String: JSONValue] = [:]

        if !preset.macros.isEmpty {
            payload["macros"] = .array(preset.macros.map { macro in
                var m: [String: JSONValue] = [
                    "slot": .int(macro.slot),
                    "tasto": .int(Int(macro.key)),
                    "nome": .string(macro.name),
                ]
                switch macro.kind {
                case .text(let s):
                    m["kind"] = "text"
                    m["text"] = .string(s)
                case .combo(let usages):
                    m["kind"] = "combo"
                    m["usages"] = .array(usages.map { .int(Int($0)) })
                case .raw(let events):
                    m["kind"] = "raw"
                    m["events"] = .array(events.map { e in
                        .object([
                            "usage": .int(Int(e.usage)),
                            "press": .bool(e.isPress),
                            "delay": .int(Int(e.delayMs)),
                        ])
                    })
                }
                return .object(m)
            })
        }

        if !preset.remaps.isEmpty {
            var remapsObject: [String: JSONValue] = [:]
            for (key, action) in preset.remaps {
                remapsObject["\(key)"] = .int(Int(action.rawValue))
            }
            payload["remaps"] = .object(remapsObject)
        }

        if !preset.profileSelectors.isEmpty {
            var table: [String: JSONValue] = [:]
            for (index, profile) in preset.profileSelectors {
                table["\(index)"] = .int(profile)
            }
            payload["profile_keys"] = .object(table)
        }

        // Il blob di profilo è quello che il pad conserva: da lì ripesca i
        // colori quando ricarica la mappatura, e con quelli si riaccende. Se
        // non lo si riscrive resta la configurazione dell'ultima sessione del
        // software ufficiale, che è il motivo per cui a ogni scrittura
        // tornavano i colori di Cooler Master.
        // La tabella per-tasto va riscritta anche quando la modalità scelta
        // non è "Personalizza": è lo slot che conserva i colori sparsi
        // dell'ultima configurazione del software ufficiale, quelli che
        // ricomparivano per qualche secondo a ogni scrittura.
        let perKey = (0..<KeyLayout.cols).flatMap { col in
            (0..<KeyLayout.rows).map { row -> JSONValue in
                let position = GridPosition(col: col, row: row)
                let color = Effects.mode(id: preset.lighting.modeID).kind == .perKeyGrid
                    ? (preset.lighting.perKeyColors[position] ?? .black)
                    : preset.lighting.color
                return .array([.int(Int(color.r)), .int(Int(color.g)), .int(Int(color.b))])
            }
        }

        payload["lighting"] = .object([
            "color1": rgba(preset.lighting.color, preset.lighting.brightness),
            "color2": rgba(preset.lighting.secondColor, preset.lighting.brightness),
            "speed": .int(Int(preset.lighting.speed)),
            "perkey": .array(perKey),
            // La modalità scelta, che decide due cose oltre ai colori: quale
            // slot il pad seleziona (`51 28 00 00 <slot>`) e cosa resta nello
            // stato persistente (`55 50 28 00 05`). Senza, la sessione
            // ricopiava i valori della cattura e il pad si riaccendeva sul
            // proprio default — le luci tornavano viola.
            "mode": .string(preset.lighting.modeID),
        ])

        // Anche i quattro LED sopra il pad viaggiano qui dentro, nel punto in
        // cui li manda il software ufficiale (`captures/12_colori profilo`).
        // Il loro registro sopravvive allo scollegamento — è così che tornavano
        // i colori di MasterPlus — quindi l'ultimo valore scritto è quello con
        // cui il pad si riaccende: per questo il motore rimette i fissi quando
        // un'animazione finisce, chiusura dell'app compresa.
        payload["indicators"] = .array(
            IndicatorEffects.staticFrame(base: preset.lighting.indicatorColors,
                                         brightness: preset.lighting.brightness)
                .map { .array([.int(Int($0.r)), .int(Int($0.g)), .int(Int($0.b))]) })

        let reply = try await send("write_session", payload)
        return reply["missing_acks"]?.intValue ?? 0
    }
}
