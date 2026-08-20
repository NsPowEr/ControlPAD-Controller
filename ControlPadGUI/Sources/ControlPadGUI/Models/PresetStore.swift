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
    private let banksURL: URL
    private let activeBankURL: URL

    init() {
        let base = FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask)[0]
        let dir = base.appendingPathComponent("ControlPad", isDirectory: true)
        try? FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        fileURL = dir.appendingPathComponent("presets.json")
        draftURL = dir.appendingPathComponent("draft.json")
        banksURL = dir.appendingPathComponent("hardware_banks.json")
        activeBankURL = dir.appendingPathComponent("active_bank.json")
        load()
    }

    // MARK: - 24 Banchi Hardware del Dispositivo (0..23 / Profilo 1..24)

    func loadHardwareBanks() -> [Preset] {
        if let data = try? Data(contentsOf: banksURL),
           let list = try? JSONDecoder().decode([Preset].self, from: data),
           list.count == 24 {
            return list
        }
        return (0..<24).map { i in
            var p = Preset(name: "Profilo \(i + 1)")
            p.remaps = [:]
            p.macros = []
            p.profileSelectors = [:]
            return p
        }
    }

    /// Quale banco stava modificando l'utente quando l'app si è chiusa.
    ///
    /// Va ricordato perché la bozza salvata appartiene a *quel* banco: senza,
    /// alla riapertura l'app riparte da `activeBankIndex = 0` e la prima
    /// sincronizzazione col dispositivo archivierebbe la bozza sotto il banco
    /// sbagliato.
    func loadActiveBank() -> Int {
        guard let data = try? Data(contentsOf: activeBankURL),
              let index = try? JSONDecoder().decode(Int.self, from: data),
              index >= 0, index < 24 else { return 0 }
        return index
    }

    func saveActiveBank(_ index: Int) {
        guard let data = try? JSONEncoder().encode(index) else { return }
        try? data.write(to: activeBankURL, options: .atomic)
    }

    func saveHardwareBanks(_ banks: [Preset]) {
        guard let data = try? JSONEncoder().encode(banks) else { return }
        try? data.write(to: banksURL, options: .atomic)
    }

    // MARK: - La configurazione in modifica

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
