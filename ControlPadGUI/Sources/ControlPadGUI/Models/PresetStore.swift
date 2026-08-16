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

    init() {
        let base = FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask)[0]
        let dir = base.appendingPathComponent("ControlPad", isDirectory: true)
        try? FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        fileURL = dir.appendingPathComponent("presets.json")
        load()
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
