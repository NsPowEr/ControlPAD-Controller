import SwiftUI

/// Stato condiviso dell'app: il bridge verso il motore Python e la presenza
/// del pad. Un'unica istanza vive per tutta la sessione, iniettata come
/// Environment nelle view.
@MainActor
@Observable
final class AppModel {
    let bridge = PythonBridge()
    private(set) var isConnected = false
    private(set) var startupError: String?

    /// Configurazione in modifica, condivisa fra le quattro schede: così
    /// passare da Illuminazione a Mappatura non perde nulla, e Profili può
    /// salvare uno scatto di tutto insieme in un colpo solo.
    ///
    /// Sopravvive alla chiusura dell'app: ogni modifica finisce in `draft.json`
    /// poco dopo. Prima no, e chiudere buttava via tutto quello che non era
    /// stato prima salvato a mano come profilo — con le macro e le rimappature
    /// ancora *dentro il pad*, che le tiene in flash, e l'app che riapriva
    /// vuota senza più modo di mostrarle.
    /// I 24 banchi profili fisici del dispositivo (0..23)
    var hardwareBanks: [Preset] = []
    var activeBankIndex: Int = 0

    var draft: Preset = Preset(name: "Profilo 1") {
        didSet {
            if activeBankIndex >= 0 && activeBankIndex < hardwareBanks.count {
                hardwareBanks[activeBankIndex] = draft
                autosaveHardwareBanks()
            }
            autosaveDraft()
        }
    }

    let presetStore = PresetStore()
    private var draftSaveTask: Task<Void, Never>?
    private var banksSaveTask: Task<Void, Never>?

    init() {
        hardwareBanks = presetStore.loadHardwareBanks()
        // La bozza salvata appartiene al banco su cui si stava lavorando, non
        // al banco 0: ripartire da zero la archivierebbe nel posto sbagliato
        // alla prima sincronizzazione col dispositivo.
        activeBankIndex = presetStore.loadActiveBank()
        if let salvato = presetStore.loadDraft() {
            draft = salvato
        } else if !hardwareBanks.isEmpty {
            draft = hardwareBanks[0]
        }

        NotificationCenter.default.addObserver(
            forName: NSApplication.willTerminateNotification,
            object: nil, queue: .main
        ) { [weak self] _ in
            MainActor.assumeIsolated {
                guard let self else { return }
                self.draftSaveTask?.cancel()
                self.banksSaveTask?.cancel()
                self.presetStore.saveDraft(self.draft)
                self.presetStore.saveHardwareBanks(self.hardwareBanks)
            }
        }
    }

    private func autosaveHardwareBanks() {
        banksSaveTask?.cancel()
        let scatto = hardwareBanks
        banksSaveTask = Task { [presetStore] in
            try? await Task.sleep(for: .milliseconds(400))
            guard !Task.isCancelled else { return }
            presetStore.saveHardwareBanks(scatto)
        }
    }

    func selectHardwareBank(_ index: Int, sendToHardware: Bool = true) async {
        guard index >= 0 && index < 24 else { return }
        if index < hardwareBanks.count {
            hardwareBanks[activeBankIndex] = draft
            activeBankIndex = index
            draft = hardwareBanks[index]
            presetStore.saveHardwareBanks(hardwareBanks)
            presetStore.saveActiveBank(index)
        }
        if sendToHardware && isConnected {
            try? await bridge.setActiveProfile(index)
            try? await applyLighting(draft.lighting)
        } else if isConnected {
            // Cambio arrivato dal pad: il banco l'ha già commutato lui, e la
            // sua illuminazione per tasto se la porta dietro — quella è
            // memorizzata per banco. I quattro LED indicatori **no**: il
            // dispositivo ne ha un registro solo, `0x00fc`, condiviso da tutti
            // i profili. Misurato — scritto rosso col pad sul banco 3, il
            // banco 7 li mostra rossi lo stesso; scritto blu sul 7, tornando
            // al 3 sono blu. Se non li riapplichiamo qui restano quelli del
            // profilo precedente, ed è il motivo per cui gli effetti dei LED
            // non seguivano il profilo cambiato dal pad.
            try? await applyIndicators(draft.lighting)
        }
    }

    /// Porta l'app sul banco su cui il dispositivo si trova davvero, senza
    /// riapplicargli niente: all'avvio ci pensa `restoreLighting`, e al
    /// ricollegamento pure. Solo lo scambio di stato, quindi.
    private func allineaAlBanco(_ index: Int) {
        guard index >= 0, index < hardwareBanks.count, index != activeBankIndex
        else { return }
        hardwareBanks[activeBankIndex] = draft
        activeBankIndex = index
        draft = hardwareBanks[index]
        presetStore.saveHardwareBanks(hardwareBanks)
        presetStore.saveActiveBank(index)
    }

    private func autosaveDraft() {
        draftSaveTask?.cancel()
        let scatto = draft
        draftSaveTask = Task { [presetStore] in
            try? await Task.sleep(for: .milliseconds(400))
            guard !Task.isCancelled else { return }
            presetStore.saveDraft(scatto)
        }
    }

    /// Propagazione in corso: (fatti, totale). La scrittura di un banco costa
    /// qualche secondo, e ventiquattro banchi sono un minuto abbondante — senza
    /// un segno di avanzamento sembrerebbe che l'app si sia piantata.
    private(set) var propagazione: (fatti: Int, totale: Int)?

    /// Copia l'assegnazione di un tasto su altri profili e la **scrive** lì.
    ///
    /// La keymap del dispositivo è per banco: un tasto rimappato su un profilo
    /// non esiste sugli altri. Chi vuole lo stesso tasto ovunque deve
    /// scriverlo ovunque, ed è quello che fa questo metodo.
    ///
    /// **"Profilo +/−" fa eccezione** e non ha bisogno di essere propagato: il
    /// passo profilo non è per banco, sta nel dispositivo una volta sola e
    /// vale su tutti e ventiquattro. Propagarlo non fa danno, ma non serve.
    ///
    /// Scrive **solo** i banchi indicati, uno per uno, e alla fine rimette il
    /// pad sul banco da cui si è partiti. Il banco corrente non è incluso
    /// d'ufficio: chi lo vuole lo mette fra i bersagli.
    func propagaAssegnazione(key: UInt8, to banchi: [Int]) async throws {
        let azione = draft.remaps[key]
        let selettore = draft.profileSelectors.first { KeyLayout.key(atColumnIndex: $0.key) == key }
        let bancoIniziale = activeBankIndex
        let bersagli = banchi.filter { $0 >= 0 && $0 < hardwareBanks.count }
        guard !bersagli.isEmpty else { return }

        propagazione = (0, bersagli.count)
        defer { propagazione = nil }

        for (fatti, banco) in bersagli.enumerated() {
            var preset = banco == activeBankIndex ? draft : hardwareBanks[banco]
            if let azione {
                preset.remaps[key] = azione
            } else {
                preset.remaps.removeValue(forKey: key)
            }
            // Un tasto "seleziona profilo" porta con sé quale profilo attiva:
            // senza, sugli altri banchi resterebbe un selettore senza meta.
            if let selettore {
                preset.profileSelectors[selettore.key] = selettore.value
            }
            hardwareBanks[banco] = preset
            if banco == activeBankIndex { draft = preset }

            if isConnected {
                let esito = try await bridge.writeSession(preset: preset, profile: banco)
                if esito.verified == false {
                    throw PythonBridge.BridgeError(
                        message: L("error.writeNotVerified"))
                }
            }
            propagazione = (fatti + 1, bersagli.count)
        }

        presetStore.saveHardwareBanks(hardwareBanks)
        if isConnected {
            try? await bridge.setActiveProfile(bancoIniziale)
            try? await applyLighting(draft.lighting)
        }
    }

    /// Riporta **tutti i ventiquattro profili** alla configurazione di
    /// fabbrica e li riscrive sul dispositivo.
    ///
    /// "Di fabbrica" non vuol dire vuoto: il n.22 fa girare gli effetti su ogni
    /// profilo, ed è il motore a rimettercelo — vedi
    /// `session._azione_predefinita`. Il ripristino toglie anche il passo
    /// profilo, che il pad tiene fuori dai banchi e si porta dietro anche da
    /// sessioni di altri software.
    ///
    /// Azzera **tutto** quello che distingue un profilo: rimappature, macro,
    /// selettori, modalità di illuminazione, colori per tasto e i quattro LED
    /// indicatori. Il punto è proprio quello: dopo, il pad e il software
    /// dicono la stessa cosa su tutti e ventiquattro i profili, e si riparte
    /// da una base nota invece che da residui di configurazioni precedenti —
    /// che su questo dispositivo restano in flash finché non li si sovrascrive.
    ///
    /// Non si può annullare.
    func ripristinaTuttiIProfili() async throws {
        let bancoIniziale = activeBankIndex
        propagazione = (0, 24)
        defer { propagazione = nil }

        for banco in 0..<24 {
            // Preset(name:) porta con sé un LightingConfig() di default, e la
            // scrittura di sessione manda sempre illuminazione e indicatori:
            // basta non conservare i vecchi perché tornino tutti al punto di
            // partenza, ciascuno nel proprio banco.
            let pulito = Preset(name: "Profilo \(banco + 1)")
            hardwareBanks[banco] = pulito
            if banco == activeBankIndex { draft = pulito }
            if isConnected {
                _ = try await bridge.writeSession(preset: pulito, profile: banco)
            }
            propagazione = (banco + 1, 24)
        }

        presetStore.saveHardwareBanks(hardwareBanks)
        if isConnected {
            try? await bridge.setActiveProfile(bancoIniziale)
            try? await applyLighting(draft.lighting)
        }
    }

    /// Registrazione macro in corso: finché è true la UI si blocca tutta
    /// tranne il pulsante Ferma. Vive qui e non nella scheda Macro perché a
    /// doversi bloccare sono anche le schede vicine e la barra in alto.
    var isRecordingMacro = false

    func start() async {
        do {
            try await bridge.start()
            isConnected = try await bridge.status()
        } catch {
            startupError = error.localizedDescription
        }
        // Prima si scopre dove sta il pad, poi si applica. Nell'altro ordine
        // l'app applicava l'illuminazione della bozza e un istante dopo se la
        // vedeva sostituire dall'allineamento col dispositivo: nel diario del
        // motore restava uno `start_indicator_effect` seguito dallo `stop`,
        // "animazione chiusa: 1 fotogrammi", e i LED del profilo non
        // partivano mai.
        if isConnected {
            if let stato = try? await bridge.state(), let banco = stato.profile {
                allineaAlBanco(banco)
            }
            await restoreLighting()
        }
        Task { await observeConnection() }
        Task { await observeHardwareEvents() }
    }

    private func observeHardwareEvents() async {
        Task {
            for await modeID in bridge.hardwareModeEvents {
                draft.lighting.modeID = modeID
            }
        }
        Task {
            for await prof in bridge.hardwareProfileEvents {
                await selectHardwareBank(prof, sendToHardware: false)
            }
        }
    }

    /// Il pad perde l'illuminazione quando lo si stacca — è così anche col
    /// software ufficiale — e le macro invece restano, perché stanno in flash.
    /// Quindi a ogni ricollegamento si riapplica solo la parte volatile: si
    /// riattacca il cavo e si ritrova la configurazione scelta qui, senza
    /// dover premere niente.
    private func observeConnection() async {
        for await present in bridge.connectionEvents {
            let wasConnected = isConnected
            isConnected = present
            if present && !wasConnected {
                await restoreLighting()
            }
            // Pad staccato: non c'è niente da fermare qui. L'effetto gira nel
            // motore, che si accorge del device sparito al primo fotogramma e
            // chiude il suo thread da sé.
        }
    }

    private func restoreLighting() async {
        try? await applyLighting(draft.lighting)
    }

    /// Applica dal vivo la modalità di illuminazione corrente — condiviso fra
    /// il pulsante Applica di Illuminazione, la scrittura di sessione, la
    /// riconnessione del pad e l'applicazione di un profilo intero, così la
    /// logica di smistamento per tipo di modalità vive in un solo posto.
    func applyLighting(_ lighting: LightingConfig) async throws {
        let mode = Effects.mode(id: lighting.modeID)
        switch mode.kind {
        case .device:
            try await bridge.setMode(mode, color: lighting.color,
                                      secondColor: lighting.secondColor,
                                      speed: lighting.speed,
                                      brightness: lighting.brightness)
        case .perKeyGrid:
            try await bridge.setGrid(lighting.perKeyColors)
        }
        try await applyIndicators(lighting)
    }

    /// I quattro LED sopra il pad: colore fisso, oppure un effetto se il
    /// profilo ne ha scelto uno.
    ///
    /// L'effetto lo disegna il motore, con un comando solo: prima l'app
    /// mandava un fotogramma per volta e il ritmo dipendeva dalla latenza del
    /// bridge, che sommandosi alla pausa fissa consegnava 26 dei 30 fps
    /// chiesti. Vedi ControlPadEngine/indicatori.py.
    func applyIndicators(_ lighting: LightingConfig) async throws {
        let colors = IndicatorEffects.staticFrame(base: lighting.indicatorColors,
                                                  brightness: lighting.brightness)

        guard let effect = IndicatorEffects.effect(id: lighting.indicatorEffect) else {
            try await bridge.stopIndicatorEffect(restoring: colors)
            return
        }
        try await bridge.startIndicatorEffect(effect, colors: lighting.indicatorColors,
                                              speed: lighting.speed,
                                              brightness: lighting.brightness)
    }

    /// Scrive la configurazione corrente sul dispositivo.
    ///
    /// L'illuminazione va **sempre** riapplicata dopo: la scrittura di
    /// sessione rigioca la traccia registrata dall'app ufficiale, che dentro
    /// porta anche il blob di illuminazione (`56 15` × 14, `56 21` × 11) e
    /// chiude con l'apply — senza questo passaggio ogni modifica a una macro o
    /// a un tasto riporterebbe le luci a quelle della cattura.
    /// Restituisce quanti report non hanno ricevuto la loro conferma: zero è
    /// l'unico valore che dica che è passata tutta.
    @discardableResult
    func writeDraft() async throws -> Int {
        // L'animazione dei LED la ferma il motore da sé: ogni comando che apre
        // il device per conto suo — la scrittura di sessione per prima — aspetta
        // che il thread dei LED lo abbia lasciato, perché due handle insieme
        // sullo stesso device non sono garantiti. Riparte da applyLighting.
        // Il banco di destinazione va detto: senza, la sessione finisce nel
        // banco su cui il pad si trova in quel momento, e modificare un
        // profilo qualunque scriveva sempre sullo stesso.
        let esito = try await bridge.writeSession(preset: draft,
                                                  profile: activeBankIndex)
        // Una rilettura che non torna vale come scrittura fallita: meglio un
        // errore visibile di un successo che non c'è stato.
        if esito.verified == false {
            let dove = esito.profileWritten.map {
                " " + String(format: L("error.writeNotVerified.onProfile"), $0 + 1)
            } ?? ""
            throw PythonBridge.BridgeError(
                message: L("error.writeNotVerified") + dove)
        }
        try await applyLighting(draft.lighting)
        return esito.missingAcks
    }

    /// Rende un profilo salvato quello corrente e lo scrive per intero sul
    /// dispositivo: sessione permanente (macro/rimappature/profili) più
    /// l'illuminazione dal vivo.
    func applyPresetToDevice(_ preset: Preset) async throws {
        draft = preset
        try await writeDraft()
    }
}
