import Foundation

/// Persistenza dei profili lato host, in ~/Library/Application Support —
/// vedi la nota in Preset.swift sul perché "profilo" è un preset locale e
/// non un banco separato sul dispositivo.
@MainActor
@Observable
final class PresetStore {
    private(set) var presets: [Preset] = []
    /// Il file c'era ma non si è lasciato leggere. Finché è pieno la lista in
    /// memoria non vale niente e non va salvata sopra l'originale.
    private(set) var loadError: String?
    private let fileURL: URL
    private let draftURL: URL

    init() {
        let base = FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask)[0]
        let dir = base.appendingPathComponent("ControlPad", isDirectory: true)
        try? FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        fileURL = dir.appendingPathComponent("presets.json")
        draftURL = dir.appendingPathComponent("draft.json")
        load()
    }

    // MARK: - La configurazione in modifica

    /// Il lavoro in corso, salvato a parte dai profili.
    ///
    /// Senza questo, chiudere l'app buttava via tutto quello che non era stato
    /// prima salvato a mano come profilo: macro appena registrate, tasti
    /// rimappati, colori scelti. Nel pad restavano — macro e keymap stanno in
    /// flash — ma l'app riapriva vuota e non aveva più modo di mostrarli, il
    /// che è peggio che perderli: la configurazione visibile e quella reale
    /// dicevano due cose diverse.
    ///
    /// Sta in `draft.json` e non dentro `presets.json` perché non è un profilo:
    /// non ha un nome scelto, non compare nell'elenco, e va riscritto a ogni
    /// modifica invece che a ogni comando esplicito.
    func loadDraft() -> Preset? {
        guard let data = try? Data(contentsOf: draftURL) else { return nil }
        return try? JSONDecoder().decode(Preset.self, from: data)
    }

    func saveDraft(_ draft: Preset) {
        guard let data = try? JSONEncoder().encode(draft) else { return }
        try? data.write(to: draftURL, options: .atomic)
    }

    /// Distingue i tre casi che prima finivano tutti in una lista vuota:
    /// file mai creato (normale, primo avvio), file leggibile (si carica),
    /// file presente e illeggibile (**non** si carica e non si sovrascrive).
    ///
    /// Prima era `(try? decode) ?? []`: un `presets.json` scritto da una
    /// versione futura, o troncato da un arresto a metà scrittura, svuotava la
    /// lista in silenzio e il primo salvataggio successivo cancellava per
    /// sempre i profili dell'utente.
    func load() {
        loadError = nil
        guard FileManager.default.fileExists(atPath: fileURL.path) else { return }
        do {
            presets = try JSONDecoder().decode([Preset].self,
                                               from: try Data(contentsOf: fileURL))
        } catch {
            loadError = error.localizedDescription
            presets = []
        }
    }

    /// Scrive solo se il caricamento è andato a buon fine, e tiene da parte la
    /// versione precedente: `presets.json.bak` è l'ultimo stato buono, l'unica
    /// rete quando qualcosa va storto a metà scrittura.
    private func save() {
        guard loadError == nil else { return }
        guard let data = try? JSONEncoder().encode(presets) else { return }
        let backup = fileURL.appendingPathExtension("bak")
        if let vecchio = try? Data(contentsOf: fileURL) {
            try? vecchio.write(to: backup, options: .atomic)
        }
        try? data.write(to: fileURL, options: .atomic)
    }

    func add(_ preset: Preset) {
        presets.append(preset)
        save()
    }

    func remove(_ id: Preset.ID) {
        presets.removeAll { $0.id == id }
        save()
    }

    func update(_ preset: Preset) {
        guard let index = presets.firstIndex(where: { $0.id == preset.id }) else { return }
        presets[index] = preset
        save()
    }

    func rename(_ id: Preset.ID, to name: String) {
        guard let index = presets.firstIndex(where: { $0.id == id }) else { return }
        presets[index].name = name
        save()
    }
}
