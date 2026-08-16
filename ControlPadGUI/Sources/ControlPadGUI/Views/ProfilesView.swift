import SwiftUI

struct ProfilesView: View {
    @Environment(AppModel.self) private var app
    @State private var renamingID: Preset.ID?
    @State private var renameText = ""
    @State private var busyID: Preset.ID?
    @State private var errorMessage: String?

    var body: some View {
        VStack(spacing: Metrics.gap) {
            GlassCard(titleKey: "profiles.list", subtitleKey: "profiles.hint") {
                VStack(spacing: Metrics.stack) {
                    if app.presetStore.presets.isEmpty {
                        Text(L("profiles.empty"))
                            .font(.callout)
                            .foregroundStyle(.secondary)
                            .multilineTextAlignment(.center)
                            .fixedSize(horizontal: false, vertical: true)
                            .frame(maxWidth: .infinity, minHeight: 140)
                    } else {
                        VStack(spacing: 6) {
                            ForEach(app.presetStore.presets) { preset in
                                row(preset)
                            }
                        }
                    }

                    Button {
                        saveCurrentAsNewPreset()
                    } label: {
                        Label(L("profiles.saveCurrent"), systemImage: "square.and.arrow.down")
                            .frame(maxWidth: .infinity)
                    }
                    .buttonStyle(.borderedProminent)
                }
            }
            .frame(maxWidth: 620)

            if let errorMessage {
                Label(errorMessage, systemImage: "exclamationmark.triangle.fill")
                    .font(.caption).foregroundStyle(.red)
            }
        }
        .padding(Metrics.page)
        .frame(maxWidth: .infinity, alignment: .top)
    }

    private func row(_ preset: Preset) -> some View {
        HStack(spacing: 10) {
            if renamingID == preset.id {
                TextField(L("profiles.name"), text: $renameText, onCommit: {
                    app.presetStore.rename(preset.id, to: renameText)
                    renamingID = nil
                })
                .textFieldStyle(.roundedBorder)
            } else {
                VStack(alignment: .leading, spacing: 2) {
                    Text(preset.name).font(.system(size: 13, weight: .semibold))
                    Text("\(preset.macros.count) \(L("profiles.macroCount")) · \(preset.remaps.count) \(L("profiles.remapCount"))")
                        .font(.system(size: 10))
                        .foregroundStyle(.secondary)
                }
            }

            Spacer()

            if busyID == preset.id {
                ProgressView().controlSize(.small)
            } else {
                Button {
                    renamingID = preset.id
                    renameText = preset.name
                } label: {
                    Image(systemName: "pencil")
                }
                .buttonStyle(.borderless)

                Button {
                    Task { await apply(preset) }
                } label: {
                    Image(systemName: "bolt.fill")
                }
                .buttonStyle(.borderless)
                .disabled(!app.isConnected)

                Button(role: .destructive) {
                    app.presetStore.remove(preset.id)
                } label: {
                    Image(systemName: "trash")
                }
                .buttonStyle(.borderless)
            }
        }
        .padding(.horizontal, 10)
        .padding(.vertical, 8)
        .background(.quaternary.opacity(0.3), in: RoundedRectangle(cornerRadius: 8))
    }

    private func saveCurrentAsNewPreset() {
        var preset = app.draft
        preset.id = UUID()
        preset.name = String(format: L("profiles.defaultName"), app.presetStore.presets.count + 1)
        app.presetStore.add(preset)
    }

    private func apply(_ preset: Preset) async {
        busyID = preset.id
        errorMessage = nil
        do {
            try await app.applyPresetToDevice(preset)
        } catch {
            errorMessage = error.localizedDescription
        }
        busyID = nil
    }
}
