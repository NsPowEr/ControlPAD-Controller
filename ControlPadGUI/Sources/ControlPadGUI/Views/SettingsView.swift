import SwiftUI

struct SettingsView: View {
    @Environment(AppModel.self) private var app
    @Environment(\.dismiss) private var dismiss
    @AppStorage("appLanguage") private var languageRaw: String = AppLanguage.system.rawValue

    var body: some View {
        VStack(alignment: .leading, spacing: 18) {
            HStack {
                Text(L("settings.title"))
                    .font(.system(size: 18, weight: .bold))
                Spacer()
                Button {
                    dismiss()
                } label: {
                    Image(systemName: "xmark.circle.fill")
                        .font(.system(size: 18))
                        .foregroundStyle(.secondary)
                }
                .buttonStyle(.plain)
            }

            GlassCard(titleKey: "settings.language") {
                Picker(L("settings.language"), selection: $languageRaw) {
                    ForEach(AppLanguage.allCases) { language in
                        Text(L(language.titleKey)).tag(language.rawValue)
                    }
                }
                .pickerStyle(.inline)
                .labelsHidden()
            }

            GlassCard(titleKey: "settings.device") {
                HStack(spacing: 8) {
                    Circle()
                        .fill(app.isConnected ? .green : .red)
                        .frame(width: 8, height: 8)
                    Text(app.isConnected ? L("settings.deviceConnected") : L("connection.notFound"))
                        .font(.system(size: 12))
                    Spacer()
                    Text("VID 0x2516 · PID 0x007B")
                        .font(.system(size: 11, design: .monospaced))
                        .foregroundStyle(.secondary)
                }
            }

            diagnosticCard

            GlassCard(titleKey: "settings.about") {
                Text(L("settings.aboutText"))
                    .font(.system(size: 11))
                    .foregroundStyle(.secondary)
                    .fixedSize(horizontal: false, vertical: true)
            }

            Spacer(minLength: 0)
        }
        .padding(22)
        .frame(minWidth: 420, minHeight: 520)
    }

    // MARK: - Pannello diagnostico

    private static let logURL: URL = {
        FileManager.default.homeDirectoryForCurrentUser
            .appendingPathComponent("Library/Logs/ControlPad-engine.log")
    }()

    @State private var logTail: String = ""
    @State private var logSize: String = ""

    private var diagnosticCard: some View {
        GlassCard(titleKey: "settings.diagnostics") {
            VStack(alignment: .leading, spacing: 10) {
                HStack(spacing: 6) {
                    Image(systemName: "doc.text.magnifyingglass")
                        .foregroundStyle(.secondary)
                    Text("~/Library/Logs/ControlPad-engine.log")
                        .font(.system(size: 10, design: .monospaced))
                        .foregroundStyle(.secondary)
                        .lineLimit(1)
                    Spacer(minLength: 0)
                    if !logSize.isEmpty {
                        Text(logSize)
                            .font(.system(size: 10))
                            .foregroundStyle(.tertiary)
                    }
                }

                if !logTail.isEmpty {
                    ScrollView {
                        Text(logTail)
                            .font(.system(size: 10, design: .monospaced))
                            .frame(maxWidth: .infinity, alignment: .leading)
                            .textSelection(.enabled)
                    }
                    .frame(height: 100)
                    .padding(6)
                    .background(.black.opacity(0.04), in: RoundedRectangle(cornerRadius: 6))
                } else {
                    Text(L("settings.noLogYet"))
                        .font(.system(size: 10))
                        .foregroundStyle(.tertiary)
                }

                HStack(spacing: 10) {
                    Button {
                        refreshLog()
                    } label: {
                        Label(L("settings.refreshLog"), systemImage: "arrow.clockwise")
                            .font(.system(size: 11))
                    }
                    .buttonStyle(.bordered)

                    Button {
                        NSWorkspace.shared.open(Self.logURL)
                    } label: {
                        Label(L("settings.openLog"), systemImage: "arrow.up.forward.square")
                            .font(.system(size: 11))
                    }
                    .buttonStyle(.bordered)

                    Spacer(minLength: 0)

                    Button {
                        exportLog()
                    } label: {
                        Label(L("settings.exportLog"), systemImage: "square.and.arrow.up")
                            .font(.system(size: 11))
                    }
                    .buttonStyle(.bordered)
                }
            }
            .onAppear { refreshLog() }
        }
    }

    private func refreshLog() {
        let url = Self.logURL
        guard let attrs = try? FileManager.default.attributesOfItem(atPath: url.path),
              let size = attrs[.size] as? UInt64 else {
            logTail = ""
            logSize = ""
            return
        }
        logSize = ByteCountFormatter.string(fromByteCount: Int64(size), countStyle: .file)

        // Ultime righe: leggere tutto su un log grande sarebbe lento.
        guard let handle = try? FileHandle(forReadingFrom: url) else { return }
        defer { try? handle.close() }
        let tailBytes: UInt64 = 4096
        if size > tailBytes {
            try? handle.seek(toOffset: size - tailBytes)
        }
        if let data = try? handle.readToEnd(), let text = String(data: data, encoding: .utf8) {
            let lines = text.split(separator: "\n", omittingEmptySubsequences: false)
            logTail = lines.suffix(30).joined(separator: "\n")
        }
    }

    private func exportLog() {
        let panel = NSSavePanel()
        panel.nameFieldStringValue = "ControlPad-engine.log"
        panel.allowedContentTypes = [.plainText]
        guard panel.runModal() == .OK, let dest = panel.url else { return }
        try? FileManager.default.copyItem(at: Self.logURL, to: dest)
    }
}
