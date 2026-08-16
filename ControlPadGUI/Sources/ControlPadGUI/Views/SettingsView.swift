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

            GlassCard(titleKey: "settings.about") {
                Text(L("settings.aboutText"))
                    .font(.system(size: 11))
                    .foregroundStyle(.secondary)
                    .fixedSize(horizontal: false, vertical: true)
            }

            Spacer(minLength: 0)
        }
        .padding(22)
        .frame(minWidth: 420, minHeight: 420)
    }
}
