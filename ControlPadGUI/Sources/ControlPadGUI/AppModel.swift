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
    var draft = Preset(name: "Corrente")

    let presetStore = PresetStore()

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
        if isConnected { await restoreLighting() }
        Task { await observeConnection() }
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
    func writeDraft() async throws {
        // L'animazione dei LED la ferma il motore da sé: ogni comando che apre
        // il device per conto suo — la scrittura di sessione per prima — aspetta
        // che il thread dei LED lo abbia lasciato, perché due handle insieme
        // sullo stesso device non sono garantiti. Riparte da applyLighting.
        try await bridge.writeSession(preset: draft)
        try await applyLighting(draft.lighting)
    }

    /// Rende un profilo salvato quello corrente e lo scrive per intero sul
    /// dispositivo: sessione permanente (macro/rimappature/profili) più
    /// l'illuminazione dal vivo.
    func applyPresetToDevice(_ preset: Preset) async throws {
        draft = preset
        try await writeDraft()
    }
}
