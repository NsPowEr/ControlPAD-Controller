import SwiftUI

struct KeyMappingView: View {
    @Environment(AppModel.self) private var app
    @State private var target: MapTarget = .pad(KeyLayout.allPositions.first!)
    @State private var source: Source = .keyboard

    /// Cosa si sta rimappando: uno dei 24 tasti oppure uno dei quattro versi
    /// delle due rotelle. Nella keymap sono la stessa cosa — pseudo-tasti con
    /// un codice come gli altri, stesso comando `51 20` — ma sulla griglia
    /// non hanno una posizione, quindi vanno tenuti distinti qui.
    private enum MapTarget: Hashable {
        case pad(GridPosition)
        case wheel(UInt8)
    }

    private enum Source: String, CaseIterable, Identifiable {
        case keyboard, function
        var id: String { rawValue }
        var titleKey: String {
            self == .keyboard ? "mapping.source.keyboard" : "mapping.source.function"
        }
        var icon: String { self == .keyboard ? "keyboard.fill" : "bolt.circle.fill" }
    }

    private var selectedKey: UInt8? {
        switch target {
        case .pad(let position): KeyLayout.key(at: position)
        case .wheel(let code): code
        }
    }

    private var currentAction: RemapAction? { selectedKey.flatMap { app.draft.remaps[$0] } }

    var body: some View {
        VStack(spacing: Metrics.gap) {
            ResponsiveRow {
                padCard
                selectionCard.sidebarColumn()
            }

            sourceCard

            WriteSessionBar()
        }
        .padding(Metrics.page)
        .frame(maxWidth: .infinity, alignment: .top)
    }

    // MARK: - Pad e rotelle

    private var padCard: some View {
        GlassCard(titleKey: "mapping.pad", subtitleKey: "mapping.padHint") {
            VStack(spacing: 14) {
                wheelStrip
                Divider().opacity(0.4)
                PadGridView(
                    fill: { tileColor($0) },
                    assignment: { assignmentLabel($0) },
                    selection: {
                        if case .pad(let position) = target { return position }
                        return nil
                    }(),
                    onTap: { target = .pad($0) },
                    maxKeySize: 84
                )
            }
        }
    }

    /// Le due rotelle in alto al pad. Sono quattro pseudo-tasti (`c6`/`c7` a
    /// sinistra, `f5`/`f6` a destra) e accettano qualunque tasto o funzione,
    /// esattamente come i 24 della griglia.
    ///
    /// Rileggendo le catture si vedono già assegnate di fabbrica con lo stesso
    /// `51 20` dei tasti — LED più/meno luminoso a sinistra, Volume −/+ a
    /// destra — quindi il formato non è dedotto, è osservato. Resta da provare
    /// solo la riassegnazione fatta da qui.
    private var wheelStrip: some View {
        HStack(spacing: Metrics.gap) {
            ForEach(KeyLayout.wheels) { wheel in
                VStack(spacing: 5) {
                    Text(L(wheel.titleKey))
                        .font(.system(size: 9, weight: .semibold))
                        .foregroundStyle(.secondary)
                        .lineLimit(1)
                    HStack(spacing: 5) {
                        wheelButton(wheel.counterClockwise, icon: "arrow.counterclockwise")
                        wheelButton(wheel.clockwise, icon: "arrow.clockwise")
                    }
                }
                .frame(maxWidth: .infinity)
            }
        }
    }

    private func wheelButton(_ code: UInt8, icon: String) -> some View {
        let isSelected = target == .wheel(code)
        let assigned = app.draft.remaps[code]
        return Button {
            target = .wheel(code)
        } label: {
            VStack(spacing: 1) {
                Image(systemName: icon).font(.system(size: 12, weight: .semibold))
                Text(label(for: assigned) ?? factoryLabel(code))
                    .font(.system(size: 8, weight: .medium))
                    .lineLimit(1)
                    .minimumScaleFactor(0.7)
                    .opacity(assigned == nil ? 0.55 : 0.9)
            }
            .frame(maxWidth: .infinity)
            .frame(height: 44)
            .background(
                assigned == nil ? Color.gray.opacity(0.22) : Color.green.opacity(0.45),
                in: RoundedRectangle(cornerRadius: 10)
            )
            .overlay {
                RoundedRectangle(cornerRadius: 10)
                    .strokeBorder(isSelected ? Color.accentColor : .white.opacity(0.12),
                                  lineWidth: isSelected ? 2 : 1)
            }
        }
        .buttonStyle(.plain)
    }

    /// Cosa fa il verso di rotella se non gli si assegna niente: le catture
    /// lo mostrano già impostato dalla fabbrica, quindi si può dire invece di
    /// lasciare un trattino.
    private func factoryLabel(_ code: UInt8) -> String {
        guard let action = KeyLayout.factoryAction(forWheelKey: code),
              let function = SpecialFunctions.function(for: action)
        else { return "—" }
        return function.shortLabel
    }

    private func label(for action: RemapAction?) -> String? {
        switch action {
        case .key(let k): KeyboardLayout.label(for: k)
        case .function(let f): f.shortLabel
        case .disabled: L("mapping.disabled.short")
        case .factoryDefault, nil: nil
        }
    }

    // MARK: - Riquadro del bersaglio selezionato

    /// Dice sempre su cosa si sta lavorando: dopo qualche clic non è più
    /// ovvio quale dei ventotto bersagli si stia modificando.
    private var selectionCard: some View {
        GlassCard(titleKey: "mapping.selected") {
            VStack(alignment: .leading, spacing: Metrics.stack) {
                HStack(alignment: .center, spacing: 10) {
                    switch target {
                    case .pad(let position):
                        Text("\(KeyLayout.number(at: position))")
                            .font(.system(size: 34, weight: .bold, design: .rounded))
                            .monospacedDigit()
                            .fixedSize()
                    case .wheel:
                        Image(systemName: "dial.medium.fill")
                            .font(.system(size: 28, weight: .semibold))
                            .fixedSize()
                    }

                    VStack(alignment: .leading, spacing: 3) {
                        Text(L(targetTitleKey))
                            .font(.system(size: 9))
                            .foregroundStyle(.secondary)
                        Text(targetSubtitle)
                            .font(.system(size: 10, weight: .medium))
                            .foregroundStyle(.secondary)
                            .fixedSize(horizontal: false, vertical: true)
                    }
                }

                Divider().opacity(0.4)

                VStack(alignment: .leading, spacing: 3) {
                    Text(L("mapping.currentAction"))
                        .font(.system(size: 9))
                        .foregroundStyle(.secondary)
                    Text(currentActionText)
                        .font(.system(size: 13, weight: .semibold))
                        .lineLimit(2)
                        .fixedSize(horizontal: false, vertical: true)
                }

                if macroOnSelectedKey != nil {
                    Label(L("mapping.hasMacro"), systemImage: "record.circle")
                        .font(.system(size: 9))
                        .foregroundStyle(.orange)
                        .fixedSize(horizontal: false, vertical: true)
                }

                if case .wheel = target {
                    Label(L("mapping.wheelUnverified"), systemImage: "questionmark.circle")
                        .font(.system(size: 9))
                        .foregroundStyle(.orange)
                        .fixedSize(horizontal: false, vertical: true)
                }

                if isProfileSelector { profileSelectorControl }

                Spacer(minLength: 0)

                // Tasto muto: nelle catture è l'azione 0x0000, quella che
                // l'app ufficiale scrive sui tasti con una macro perché non
                // battano anche il loro carattere.
                Button {
                    assign(.disabled)
                } label: {
                    Label(L("mapping.disable"), systemImage: "nosign")
                        .frame(maxWidth: .infinity)
                }
                .buttonStyle(.bordered)
                .disabled(currentAction == .disabled)

                Button(role: .destructive) {
                    if let key = selectedKey { app.draft.remaps.removeValue(forKey: key) }
                    if let index = selectedColumnIndex {
                        app.draft.profileSelectors.removeValue(forKey: index)
                    }
                } label: {
                    Text(L("mapping.reset")).frame(maxWidth: .infinity)
                }
                .buttonStyle(.bordered)
                .disabled(currentAction == nil)
            }
        }
    }

    private var targetTitleKey: String {
        if case .wheel = target { return "mapping.wheelDirection" }
        return "mapping.keyNumber"
    }

    private var targetSubtitle: String {
        switch target {
        case .pad(let position):
            guard let key = KeyLayout.key(at: position) else { return "—" }
            return String(format: L("mapping.defaultIs"), KeyLayout.defaultLabels[key] ?? "?")
        case .wheel(let code):
            guard let wheel = KeyLayout.wheels.first(where: {
                $0.counterClockwise == code || $0.clockwise == code
            }) else { return "—" }
            let direction = L(code == wheel.clockwise ? "mapping.wheel.cw" : "mapping.wheel.ccw")
            return "\(L(wheel.titleKey)) · \(direction)"
        }
    }

    // MARK: - Sorgente da assegnare

    private var sourceCard: some View {
        GlassCard(titleKey: "mapping.assignTo") {
            VStack(alignment: .leading, spacing: Metrics.stack) {
                Picker("", selection: $source) {
                    ForEach(Source.allCases) { s in
                        Label(L(s.titleKey), systemImage: s.icon).tag(s)
                    }
                }
                .pickerStyle(.segmented)
                .labelsHidden()
                .frame(maxWidth: 340)

                ScrollView {
                    switch source {
                    case .keyboard:
                        // Si allarga da sola con il riquadro: vedi
                        // KeyboardPickerView, che si misura il contenitore.
                        KeyboardPickerView(
                            selected: pickedKeyUsage,
                            onPick: { assign(.key($0)) }
                        )
                    case .function:
                        FunctionGridView(
                            selected: pickedFunctionCode,
                            onPick: { assign(.function($0)) }
                        )
                        .frame(maxWidth: .infinity)
                    }
                }
                .frame(minHeight: 300)
            }
        }
    }

    private var macroOnSelectedKey: MacroAssignment? {
        selectedKey.flatMap { key in app.draft.macros.first { $0.key == key } }
    }

    private var currentActionText: String {
        switch currentAction {
        case .key(let k): return KeyboardLayout.label(for: k)
        case .function(let f): return L(f.titleKey)
        case .disabled: return L("mapping.disabled")
        case .factoryDefault, nil:
            if case .wheel(let code) = target,
               let action = KeyLayout.factoryAction(forWheelKey: code),
               let function = SpecialFunctions.function(for: action) {
                return String(format: L("mapping.factoryAction"), L(function.titleKey))
            }
            return L("mapping.noneAssigned")
        }
    }

    private var pickedKeyUsage: UInt8? {
        if case .key(let k) = currentAction { return k }
        return nil
    }

    private var pickedFunctionCode: UInt16? {
        if case .function(let f) = currentAction { return f.code }
        return nil
    }

    // MARK: - Tasto selettore di profilo

    /// `0x0110` dice soltanto "questo tasto cambia profilo". *Quale* profilo
    /// sta in una tabella a parte (`51 90`), un byte per tasto, indicizzata per
    /// colonne. Servono entrambe le scritture: con la sola funzione nella
    /// keymap il tasto conserva il numero di profilo che aveva prima, che è il
    /// tipo di sorpresa che fa sembrare rotto un programma che funziona.
    private var isProfileSelector: Bool {
        if case .function(let f) = currentAction { return f.code == SpecialFunctions.selectProfile }
        return false
    }

    /// L'indice per colonne del tasto selezionato — la numerazione della
    /// tabella dei profili, che non è quella per righe della keymap. Le
    /// rotelle non ne hanno uno: nella tabella entrano solo i 24 tasti.
    private var selectedColumnIndex: Int? {
        if case .pad(let position) = target { return KeyLayout.columnIndex(position) }
        return nil
    }

    @ViewBuilder
    private var profileSelectorControl: some View {
        if let index = selectedColumnIndex {
            let profile = app.draft.profileSelectors[index] ?? 0
            VStack(alignment: .leading, spacing: 4) {
                Divider().opacity(0.4)
                Stepper(value: Binding(
                    get: { profile },
                    set: { app.draft.profileSelectors[index] = $0 }
                ), in: 0...(SpecialFunctions.profileCount - 1)) {
                    Text(String(format: L("mapping.profileNumber"), profile + 1))
                        .font(.system(size: 12, weight: .semibold))
                        .monospacedDigit()
                }
                Text(L("mapping.profileNumberHint"))
                    .font(.system(size: 9))
                    .foregroundStyle(.secondary)
                    .fixedSize(horizontal: false, vertical: true)
            }
        } else {
            // Una rotella può prendere la funzione, ma la tabella `51 90` ha
            // una voce per tasto e nessuna per le rotelle: non c'è modo di
            // dire quale profilo, e prometterlo sarebbe prometterlo a vuoto.
            Label(L("mapping.profileWheelUnsupported"), systemImage: "exclamationmark.triangle")
                .font(.system(size: 9))
                .foregroundStyle(.orange)
                .fixedSize(horizontal: false, vertical: true)
        }
    }

    private func assign(_ action: RemapAction) {
        guard let key = selectedKey else { return }
        app.draft.remaps[key] = action

        // La voce nella tabella dei profili segue la funzione: compare quando
        // il tasto diventa un selettore, sparisce quando smette di esserlo —
        // altrimenti resterebbe a dire "profilo N" per un tasto che ormai fa
        // altro, e verrebbe scritta lo stesso.
        guard let index = selectedColumnIndex else { return }
        if case .function(let f) = action, f.code == SpecialFunctions.selectProfile {
            if app.draft.profileSelectors[index] == nil {
                app.draft.profileSelectors[index] = 0
            }
        } else {
            app.draft.profileSelectors.removeValue(forKey: index)
        }
    }

    /// L'etichetta piccola sotto al numero: prima la macro, che è la cosa più
    /// "forte" che può esserci su un tasto, poi la rimappatura.
    private func assignmentLabel(_ position: GridPosition) -> String? {
        guard let key = KeyLayout.key(at: position) else { return nil }
        if let macro = app.draft.macros.first(where: { $0.key == key }) {
            return macro.name.isEmpty ? L("macro.unnamed") : macro.name
        }
        return label(for: app.draft.remaps[key])
    }

    private func tileColor(_ position: GridPosition) -> Color {
        guard let key = KeyLayout.key(at: position) else { return .gray.opacity(0.25) }
        if app.draft.macros.contains(where: { $0.key == key }) {
            return .orange.opacity(0.55)
        }
        switch app.draft.remaps[key] {
        case .key: return .blue.opacity(0.55)
        case .function: return .green.opacity(0.55)
        case .disabled: return .black.opacity(0.55)
        case .factoryDefault, nil: return .gray.opacity(0.28)
        }
    }
}
