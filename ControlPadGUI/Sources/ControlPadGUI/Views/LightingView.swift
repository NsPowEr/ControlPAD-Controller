import SwiftUI

struct LightingView: View {
    @Environment(AppModel.self) private var app
    @State private var errorMessage: String?

    private var mode: LightingMode { Effects.mode(id: app.draft.lighting.modeID) }

    var body: some View {
        VStack(spacing: Metrics.gap) {
            ResponsiveRow {
                padCard
                modesCard.sidebarColumn(280)
            }

            ResponsiveRow(breakpoint: 860) {
                controlsCard
                indicatorsCard
            }

            if let errorMessage {
                Label(errorMessage, systemImage: "exclamationmark.triangle.fill")
                    .font(.caption)
                    .foregroundStyle(.red)
                    .frame(maxWidth: .infinity, alignment: .leading)
            }

            // Questa scheda non aveva alcuna via per rendere permanente ciò che
            // mostra: "Applica" manda i comandi dal vivo, che il pad dimentica
            // allo scollegamento, e il pulsante di scrittura stava solo in
            // Mappatura e Macro. Chi cambiava le luci qui non aveva modo di
            // sapere perché, ricollegando il pad, tornava la configurazione del
            // software ufficiale rimasta in flash.
            Label(L("lighting.persistenceHint"), systemImage: "internaldrive")
                .font(.caption2)
                .foregroundStyle(.secondary)
                .frame(maxWidth: .infinity, alignment: .leading)
                .fixedSize(horizontal: false, vertical: true)

            WriteSessionBar()
        }
        .padding(Metrics.page)
        .frame(maxWidth: .infinity, alignment: .top)
    }

    // MARK: - Pad

    private var padCard: some View {
        GlassCard(titleKey: "lighting.preview",
                  subtitleKey: mode.kind == .perKeyGrid ? "lighting.customHint" : nil) {
            PadGridView(
                fill: { position in
                    if case .perKeyGrid = mode.kind {
                        return (app.draft.lighting.perKeyColors[position] ?? .black).color
                    }
                    if mode.isRainbow { return .gray.opacity(0.3) }
                    return mode.usesColor ? app.draft.lighting.color.color : .gray.opacity(0.3)
                },
                assignment: { _ in nil },
                onTap: { position in
                    guard case .perKeyGrid = mode.kind else { return }
                    app.draft.lighting.perKeyColors[position] = app.draft.lighting.color
                    Task { await push() }
                },
                showIndicatorLEDs: true,
                indicatorColors: app.draft.lighting.indicatorColors.map(\.color)
            )
        }
    }

    // MARK: - Modalità

    private var modesCard: some View {
        GlassCard(titleKey: "lighting.mode") {
            VStack(spacing: 3) {
                ForEach(Effects.modes) { m in
                    modeRow(m)
                }
            }
        }
    }

    private func modeRow(_ m: LightingMode) -> some View {
        let isSelected = mode.id == m.id
        return Button {
            app.draft.lighting.modeID = m.id
            // Le modalità arcobaleno non hanno niente da configurare: la
            // selezione è già tutto, quindi parte subito verso il pad. Vale
            // per tutte, ma lì è l'unica cosa che l'utente deve fare.
            Task { await push() }
        } label: {
            HStack(spacing: 9) {
                Image(systemName: m.icon)
                    .font(.system(size: 13))
                    .symbolRenderingMode(.hierarchical)
                    .frame(width: 18)
                Text(L(m.titleKey))
                    .font(.system(size: 12, weight: .medium))
                    .lineLimit(1)
                Spacer(minLength: 4)
                if m.isRainbow {
                    // Sfumatura al posto dei pallini: dice a colpo d'occhio
                    // che quella modalità i colori se li fa da sé.
                    Capsule()
                        .fill(LinearGradient(colors: [.red, .yellow, .green, .cyan, .blue, .purple],
                                             startPoint: .leading, endPoint: .trailing))
                        .frame(width: 26, height: 8)
                        .opacity(isSelected ? 1 : 0.5)
                } else if m.hasSecondColor {
                    // Due pallini: si vede subito quali modalità hanno il
                    // secondo colore, senza doverle selezionare una per una.
                    HStack(spacing: -3) {
                        Circle().fill(app.draft.lighting.color.color).frame(width: 9, height: 9)
                        Circle().fill(app.draft.lighting.secondColor.color).frame(width: 9, height: 9)
                    }
                    .opacity(isSelected ? 1 : 0.5)
                }
            }
            .padding(.horizontal, 10)
            .padding(.vertical, 8)
            .background(
                isSelected ? Color.accentColor.opacity(0.22) : .clear,
                in: RoundedRectangle(cornerRadius: 8)
            )
            .foregroundStyle(isSelected ? Color.accentColor : .primary)
            .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
    }

    // MARK: - Controlli

    private var controlsCard: some View {
        @Bindable var app = app
        return GlassCard(titleKey: "lighting.tuning") {
            VStack(alignment: .leading, spacing: Metrics.stack) {
                if mode.usesColor {
                    HStack(alignment: .top, spacing: 24) {
                        colorWell(L(mode.hasSecondColor ? "lighting.color1" : "lighting.color"),
                                  Binding(
                                    get: { app.draft.lighting.color.color },
                                    set: { app.draft.lighting.color = RGBColor(color: $0) }
                                  ))
                        if mode.hasSecondColor {
                            colorWell(L("lighting.color2"), Binding(
                                get: { app.draft.lighting.secondColor.color },
                                set: { app.draft.lighting.secondColor = RGBColor(color: $0) }
                            ))
                        }
                        Spacer(minLength: 0)
                    }
                } else {
                    Label(L(noColorMessageKey), systemImage: mode.isRainbow ? "rainbow" : "circle.slash")
                        .font(.caption2)
                        .foregroundStyle(.secondary)
                        .fixedSize(horizontal: false, vertical: true)
                }

                if mode.usesSpeed {
                    labelled(L("lighting.speed")) {
                        Slider(value: Binding(
                            get: { Double(app.draft.lighting.speed) },
                            set: { app.draft.lighting.speed = UInt8($0) }
                        ), in: 0...32, step: 1)
                    }
                }

                labelled(L("lighting.brightness")) {
                    Slider(value: Binding(
                        get: { Double(app.draft.lighting.brightness) },
                        set: { app.draft.lighting.brightness = UInt8($0) }
                    ), in: 0...255)
                }

                Spacer(minLength: 0)

                Button {
                    Task { await push() }
                } label: {
                    Label(L("lighting.apply"), systemImage: "paintbrush.fill")
                        .frame(maxWidth: .infinity)
                }
                .buttonStyle(.borderedProminent)
                .disabled(!app.isConnected)
            }
        }
    }

    private var noColorMessageKey: String {
        if mode.id == "off" { return "lighting.noColor" }
        return "lighting.colorIgnored"
    }

    // MARK: - LED indicatori

    /// I quattro LED sopra il pad. Vale la pena distinguerli bene dal resto:
    /// il colore fisso resta anche a app chiusa, l'effetto no — lo disegna
    /// l'app, perché il firmware per questi quattro non ne ha.
    private var indicatorsCard: some View {
        @Bindable var app = app
        return GlassCard(titleKey: "lighting.indicators",
                         subtitleKey: "lighting.indicatorsHint") {
            VStack(alignment: .leading, spacing: Metrics.stack) {
                HStack(spacing: 14) {
                    ForEach(0..<IndicatorEffects.ledCount, id: \.self) { index in
                        colorWell("\(index + 1)", Binding(
                            get: { app.draft.lighting.indicatorColors[index].color },
                            set: {
                                app.draft.lighting.indicatorColors[index] = RGBColor(color: $0)
                                Task { await pushIndicators() }
                            }
                        ))
                    }
                    Spacer(minLength: 0)
                }

                labelled(L("lighting.indicatorEffect")) {
                    Picker("", selection: Binding(
                        get: { app.draft.lighting.indicatorEffect ?? "" },
                        set: {
                            app.draft.lighting.indicatorEffect = $0.isEmpty ? nil : $0
                            Task { await pushIndicators() }
                        }
                    )) {
                        Text(L("lighting.indicatorEffect.none")).tag("")
                        ForEach(IndicatorEffects.all) { effect in
                            Label(L(effect.titleKey), systemImage: effect.icon).tag(effect.id)
                        }
                    }
                    .labelsHidden()
                    .frame(maxWidth: 260)
                }

                if let effect = IndicatorEffects.effect(id: app.draft.lighting.indicatorEffect) {
                    Label(L("lighting.indicatorEffect.hostOnly"), systemImage: "bolt.horizontal.circle")
                        .font(.system(size: 10))
                        .foregroundStyle(.orange)
                        .fixedSize(horizontal: false, vertical: true)

                    // Sei effetti sui diciassette si fanno i colori da soli:
                    // dirlo evita che i quattro selettori sembrino guasti.
                    if effect.ignoresColors {
                        Label(L("lighting.indicatorEffect.ownColors"), systemImage: "paintpalette")
                            .font(.system(size: 10))
                            .foregroundStyle(.secondary)
                            .fixedSize(horizontal: false, vertical: true)
                    }
                }

                Spacer(minLength: 0)
            }
        }
    }

    private func colorWell(_ title: String, _ binding: Binding<Color>) -> some View {
        VStack(alignment: .leading, spacing: 5) {
            Text(title)
                .font(.caption2)
                .foregroundStyle(.secondary)
                .lineLimit(1)
            ColorPicker("", selection: binding, supportsOpacity: false)
                .labelsHidden()
        }
        .fixedSize(horizontal: true, vertical: false)
    }

    private func labelled<Content: View>(_ title: String,
                                          @ViewBuilder _ content: () -> Content) -> some View {
        VStack(alignment: .leading, spacing: 5) {
            Text(title).font(.caption2).foregroundStyle(.secondary)
            content()
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }

    private func push() async {
        errorMessage = nil
        do {
            try await app.applyLighting(app.draft.lighting)
        } catch {
            errorMessage = error.localizedDescription
        }
    }

    private func pushIndicators() async {
        errorMessage = nil
        do {
            try await app.applyIndicators(app.draft.lighting)
        } catch {
            errorMessage = error.localizedDescription
        }
    }
}
