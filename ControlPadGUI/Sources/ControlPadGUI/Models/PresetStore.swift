import Foundation

/// Persistenza dei profili lato host, in ~/Library/Application Support —
/// vedi la nota in Preset.swift sul perché "profilo" è un preset locale e
/// non un banco separato sul dispositivo.
@MainActor
@Observable
final class PresetStore {
    private(set) var presets: [Preset] = []
    private let fileURL: URL

    init() {
        let base = FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask)[0]
        let dir = base.appendingPathComponent("ControlPad", isDirectory: true)
        try? FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        fileURL = dir.appendingPathComponent("presets.json")
        load()
    }

    func load() {
        guard let data = try? Data(contentsOf: fileURL) else { return }
        presets = (try? JSONDecoder().decode([Preset].self, from: data)) ?? []
    }

    private func save() {
        guard let data = try? JSONEncoder().encode(presets) else { return }
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
