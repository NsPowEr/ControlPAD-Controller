import SwiftUI

struct RootView: View {
    @Environment(AppModel.self) private var app
    @State private var tab: AppTab = .lighting
    @State private var showSettings = false

    var body: some View {
        ZStack(alignment: .top) {
            ScrollView(.vertical) {
                currentTab
                    .frame(maxWidth: .infinity, alignment: .top)
                    .padding(.top, 74)
            }
            .scrollBounceBehavior(.basedOnSize)
            // Una ScrollView per scheda: con una sola, condivisa, cambiando
            // scheda restava la posizione della precedente e il contenuto
            // partiva già scorso, finendo sotto la barra flottante.
            .id(tab)

            VStack(spacing: 8) {
                GlassTabBar(selection: $tab, showSettings: $showSettings)
                    // A registrazione macro avviata la barra è bloccata come
                    // tutto il resto: cambiare scheda mentre si registra
                    // lasciava i monitor addosso e la sequenza in mano alla
                    // macro sbagliata.
                    .disabled(app.isRecordingMacro)

                if let startupError = app.startupError {
                    banner(startupError, icon: "exclamationmark.triangle.fill", tint: .red)
                } else if !app.isConnected {
                    ConnectionBanner()
                } else if app.isRecordingMacro {
                    banner(L("macro.recordingLock"), icon: "record.circle", tint: .red)
                }
            }
            .padding(.top, 14)
        }
        .frame(minWidth: Metrics.windowMinWidth, minHeight: Metrics.windowMinHeight)
        .sheet(isPresented: $showSettings) {
            SettingsView()
        }
        .task {
            await app.start()
        }
    }

    private func banner(_ text: String, icon: String, tint: Color) -> some View {
        Label(text, systemImage: icon)
            .font(.system(size: 12, weight: .medium))
            .lineLimit(2)
            .padding(.horizontal, 14)
            .padding(.vertical, 8)
            .foregroundStyle(tint)
            .glassEffect(.regular.tint(tint.opacity(0.15)), in: .capsule)
            .frame(maxWidth: 620)
    }

    @ViewBuilder
    private var currentTab: some View {
        switch tab {
        case .lighting: LightingView()
        case .mapping: KeyMappingView()
        case .macros: MacroView()
        case .profiles: ProfilesView()
        }
    }
}
