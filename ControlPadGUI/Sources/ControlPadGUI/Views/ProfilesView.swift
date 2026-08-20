import SwiftUI

struct ProfilesView: View {
    @Environment(AppModel.self) private var app
    @State private var renamingID: Preset.ID?
    @State private var renameText = ""
    @State private var busyID: Preset.ID?
    @State private var errorMessage: String?

    var body: some View {
        VStack(spacing: Metrics.gap) {
            GlassCard(titleKey: "profiles.hardwareTitle", subtitleKey: "profiles.hardwareSubtitle") {
                VStack(alignment: .leading, spacing: 10) {
                    LazyVGrid(columns: [GridItem(.adaptive(minimum: 130), spacing: 8)], spacing: 8) {
                        ForEach(0..<24, id: \.self) { index in
                            let isSelected = app.activeBankIndex == index
                            let bankPreset = app.hardwareBanks.indices.contains(index) ? app.hardwareBanks[index] : app.draft
                            
                            Button {
                                Task { await app.selectHardwareBank(index) }
                            } label: {
                                HStack {
                                    VStack(alignment: .leading, spacing: 2) {
                                        Text("Profilo \(index + 1)")
                                            .font(.system(size: 12, weight: .bold))
                                            .foregroundStyle(isSelected ? .white : .primary)
                                        Text("\(bankPreset.macros.count) macro · \(bankPreset.remaps.count) remap")
                                            .font(.system(size: 9))
                                            .foregroundStyle(isSelected ? .white.opacity(0.8) : .secondary)
                                    }
                                    Spacer(minLength: 0)
                                    if isSelected {
                                        Image(systemName: "checkmark.circle.fill")
                                            .font(.system(size: 12))
                                            .foregroundStyle(.white)
                                    }
                                }
                                .padding(.horizontal, 10)
                                .padding(.vertical, 8)
                                .background(
                                    isSelected
                                        ? Color.accentColor
                                        : Color.primary.opacity(0.06),
                                    in: RoundedRectangle(cornerRadius: 8)
                                )
                            }
                            .buttonStyle(.plain)
                        }
                    }
                }
            }
            .frame(maxWidth: 620)

            GlassCard(titleKey: "profiles.list", subtitleKey: "profiles.hint") {
                VStack(spacing: Metrics.stack) {
                    if let loadError = app.presetStore.loadError {
                        Label(String(format: L("profiles.loadFailed"), loadError),
                              systemImage: "exclamationmark.triangle.fill")
                            .font(.caption)
                            .foregroundStyle(.orange)
                            .fixedSize(horizontal: false, vertical: true)
                    }

                    if app.presetStore.presets.isEmpty {
                        Text(L("profiles.empty"))
                            .font(.callout)
                            .foregroundStyle(.secondary)
                            .multilineTextAlignment(.center)
                            .fixedSize(horizontal: false, vertical: true)
                            .frame(maxWidth: .infinity, minHeight: 80)
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
                    .disabled(app.presetStore.loadError != nil)
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
