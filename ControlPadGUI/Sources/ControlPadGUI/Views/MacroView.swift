import SwiftUI

struct MacroView: View {
    @Environment(AppModel.self) private var app
    @State private var selectedID: MacroAssignment.ID?
    @State private var recorder = MacroRecorder()
    @State private var addMacroError: String?
    @State private var pendingSwap: KeySwap?

    private struct KeySwap: Identifiable {
        let macroIndex: Int
        let conflictIndex: Int
        let newKey: UInt8
        var id: UInt8 { newKey }
    }

    private var selectedIndex: Int? {
        app.draft.macros.firstIndex { $0.id == selectedID }
    }

    /// Durante la registrazione tutto il resto è bloccato: era possibile
    /// cambiare macro a registrazione avviata, e allora la sequenza appena
    /// battuta finiva nella macro appena selezionata, cancellandone gli
    /// eventi. Il blocco toglie il problema alla radice invece di rincorrerlo.
    private var isRecording: Bool { recorder.isRecording }

    var body: some View {
        VStack(spacing: Metrics.gap) {
            ResponsiveRow {
                listCard
                    .sidebarColumn()
                    .disabled(isRecording)
                editorCard
                assignCard
                    .sidebarColumn(400)
                    .disabled(isRecording)
            }

            WriteSessionBar()
                .disabled(isRecording)
        }
        .padding(Metrics.page)
        .frame(maxWidth: .infinity, alignment: .top)
        .onAppear {
            if selectedID == nil { selectedID = app.draft.macros.first?.id }
        }
        .onChange(of: recorder.isRecording) { _, recording in
            // La barra in alto e le altre schede stanno fuori di qui: si
            // bloccano leggendo questo, non recorder.isRecording.
            app.isRecordingMacro = recording
        }
        .onDisappear {
            // Uscire dalla scheda con la registrazione attiva lascerebbe i
            // monitor installati a mangiarsi i tasti del resto dell'app.
            if recorder.isRecording { recorder.stop() }
            app.isRecordingMacro = false
        }
        .alert(L("macro.confirmSwap.title"), isPresented: Binding(
            get: { pendingSwap != nil }, set: { if !$0 { pendingSwap = nil } }
        ), presenting: pendingSwap) { swap in
            Button(L("macro.confirmSwap.confirm")) { performSwap(swap) }
            Button(L("common.cancel"), role: .cancel) { pendingSwap = nil }
        } message: { swap in
            Text(String(format: L("macro.confirmSwap.message"),
                        displayName(app.draft.macros[swap.conflictIndex])))
        }
    }

    private func displayName(_ macro: MacroAssignment) -> String {
        macro.name.isEmpty ? L("macro.unnamed") : macro.name
    }

    private func performSwap(_ swap: KeySwap) {
        let oldKey = app.draft.macros[swap.macroIndex].key
        app.draft.macros[swap.conflictIndex].key = oldKey
        app.draft.macros[swap.macroIndex].key = swap.newKey
        pendingSwap = nil
    }

    // MARK: - Colonna 1: elenco

    private var listCard: some View {
        GlassCard(titleKey: "macro.list") {
            VStack(spacing: Metrics.stack) {
                if app.draft.macros.isEmpty {
                    Text(L("macro.noneYet"))
                        .font(.caption)
                        .foregroundStyle(.secondary)
                        .multilineTextAlignment(.center)
                        .fixedSize(horizontal: false, vertical: true)
                        .frame(maxWidth: .infinity, minHeight: 100)
                } else {
                    ScrollView {
                        VStack(spacing: 4) {
                            ForEach(app.draft.macros) { macro in
                                macroRow(macro)
                            }
                        }
                    }
                    .frame(maxHeight: .infinity)
                }

                Button {
                    addMacro()
                } label: {
                    Label(L("macro.new"), systemImage: "plus").frame(maxWidth: .infinity)
                }
                .buttonStyle(.bordered)

                if let addMacroError {
                    Text(addMacroError)
                        .font(.caption2)
                        .foregroundStyle(.red)
                        .fixedSize(horizontal: false, vertical: true)
                }
            }
        }
    }

    private func macroRow(_ macro: MacroAssignment) -> some View {
        HStack(spacing: 4) {
            Button {
                selectedID = macro.id
            } label: {
                VStack(alignment: .leading, spacing: 2) {
                    HStack(spacing: 4) {
                        Text(displayName(macro))
                            .font(.system(size: 12, weight: .semibold))
                            .lineLimit(1)
                        if macro.validationError != nil {
                            Image(systemName: "exclamationmark.triangle.fill")
                                .font(.system(size: 9)).foregroundStyle(.red)
                        }
                    }
                    Text(subtitle(macro))
                        .font(.system(size: 10))
                        .foregroundStyle(.secondary)
                        .lineLimit(1)
                }
                .frame(maxWidth: .infinity, alignment: .leading)
                .padding(.horizontal, 10)
                .padding(.vertical, 7)
                .background(
                    selectedID == macro.id ? Color.accentColor.opacity(0.22) : .clear,
                    in: RoundedRectangle(cornerRadius: 8)
                )
                .contentShape(Rectangle())
            }
            .buttonStyle(.plain)

            Button {
                deleteMacro(macro)
            } label: {
                Image(systemName: "trash").font(.system(size: 11)).foregroundStyle(.secondary)
            }
            .buttonStyle(.plain)
            .padding(.trailing, 4)
        }
    }

    private func subtitle(_ macro: MacroAssignment) -> String {
        let number = KeyLayout.number(forKey: macro.key).map(String.init) ?? "?"
        return String(format: L("macro.subtitle"), number, macro.estimatedEventCount)
    }

    private func deleteMacro(_ macro: MacroAssignment) {
        app.draft.macros.removeAll { $0.id == macro.id }
        if selectedID == macro.id { selectedID = app.draft.macros.first?.id }
    }

    private func addMacro() {
        addMacroError = nil
        let usedSlots = Set(app.draft.macros.map(\.slot))
        guard let nextSlot = (0...23).first(where: { !usedSlots.contains($0) }) else {
            addMacroError = L("macro.noFreeSlot"); return
        }
        let usedKeys = Set(app.draft.macros.map(\.key))
        guard let key = KeyLayout.allKeys.first(where: { !usedKeys.contains($0) }) else {
            addMacroError = L("macro.noFreeKey"); return
        }
        let macro = MacroAssignment(slot: nextSlot, key: key, name: "", kind: .raw([]))
        app.draft.macros.append(macro)
        selectedID = macro.id
    }

    // MARK: - Colonna 2: editor con registrazione

    @ViewBuilder
    private var editorCard: some View {
        @Bindable var app = app
        if let index = selectedIndex {
            GlassCard(titleKey: "macro.edit") {
                MacroEditor(macro: $app.draft.macros[index], recorder: recorder)
            }
        } else {
            GlassCard(titleKey: "macro.edit") {
                Text(L("macro.selectHint"))
                    .font(.caption).foregroundStyle(.secondary)
                    .frame(maxWidth: .infinity, minHeight: 240)
            }
        }
    }

    // MARK: - Colonna 3: tasto del pad

    @ViewBuilder
    private var assignCard: some View {
        if let index = selectedIndex {
            GlassCard(titleKey: "macro.assign", subtitleKey: "macro.assignHint") {
                PadGridView(
                    fill: { position in
                        guard let hid = KeyLayout.key(at: position) else { return .gray.opacity(0.2) }
                        if hid == app.draft.macros[index].key { return .accentColor.opacity(0.8) }
                        if app.draft.macros.contains(where: { $0.key == hid }) {
                            return .orange.opacity(0.45)
                        }
                        return .gray.opacity(0.28)
                    },
                    assignment: { position in
                        guard let hid = KeyLayout.key(at: position),
                              let other = app.draft.macros.first(where: { $0.key == hid })
                        else { return nil }
                        return displayName(other)
                    },
                    onTap: { position in
                        guard let hid = KeyLayout.key(at: position) else { return }
                        let current = app.draft.macros[index]
                        if let conflict = app.draft.macros.firstIndex(where: {
                            $0.key == hid && $0.id != current.id
                        }) {
                            pendingSwap = KeySwap(macroIndex: index, conflictIndex: conflict, newKey: hid)
                        } else {
                            app.draft.macros[index].key = hid
                        }
                    },
                    maxKeySize: 78
                )
            }
        } else {
            GlassCard(titleKey: "macro.assign") {
                Text(L("macro.selectHint"))
                    .font(.caption).foregroundStyle(.secondary)
                    .frame(maxWidth: .infinity, minHeight: 240)
            }
        }
    }
}

// MARK: - Editor

/// Editor di una macro: si registra battendo davvero i tasti, poi si aggiusta.
/// Il vecchio modo (scrivi una stringa, oppure scegli dei tasti da tenere
/// premuti insieme) non poteva riprodurre una sequenza reale — nessuna pausa
/// vera, nessun ordine di pressione e rilascio scelto dall'utente.
private struct MacroEditor: View {
    @Binding var macro: MacroAssignment
    let recorder: MacroRecorder

    @State private var pendingReplace = false

    private var events: [MacroEvent] {
        if case .raw(let e) = macro.kind { return e }
        return []
    }

    private var totalDuration: Int {
        events.dropLast().reduce(0) { $0 + Int($1.delayMs) }
    }

    var body: some View {
        VStack(alignment: .leading, spacing: Metrics.stack) {
            TextField(L("macro.name"), text: $macro.name)
                .textFieldStyle(.roundedBorder)
                .disabled(recorder.isRecording)

            recordBar

            if recorder.isRecording {
                liveList
            } else if events.isEmpty {
                Text(L("macro.recordHint"))
                    .font(.caption)
                    .foregroundStyle(.secondary)
                    .fixedSize(horizontal: false, vertical: true)
                    .frame(maxWidth: .infinity, minHeight: 170, alignment: .top)
            } else {
                eventList
            }

            footer
        }
        .alert(L("macro.confirmReplace.title"), isPresented: $pendingReplace) {
            Button(L("macro.confirmReplace.confirm"), role: .destructive) { recorder.start() }
            Button(L("common.cancel"), role: .cancel) {}
        } message: {
            Text(L("macro.confirmReplace.message"))
        }
    }

    private var recordBar: some View {
        HStack(spacing: 10) {
            Button {
                if recorder.isRecording {
                    recorder.stop()
                    macro.kind = .raw(recorder.events)
                } else if events.isEmpty {
                    recorder.start()
                } else {
                    pendingReplace = true
                }
            } label: {
                Label(
                    recorder.isRecording ? L("macro.stopRecording") : L("macro.record"),
                    systemImage: recorder.isRecording ? "stop.circle.fill" : "record.circle"
                )
                .frame(maxWidth: .infinity)
            }
            .buttonStyle(.borderedProminent)
            .tint(recorder.isRecording ? .red : .accentColor)

            if recorder.isRecording {
                Text("\(recorder.events.count)")
                    .font(.system(size: 13, weight: .bold))
                    .monospacedDigit()
                    .foregroundStyle(.red)
                    .frame(minWidth: 22)
            }
        }
    }

    /// Durante la registrazione la lista scorre da sola: serve un riscontro
    /// immediato che i tasti stiano davvero entrando.
    ///
    /// L'intestazione è una riga vera sopra la lista, non più un overlay: un
    /// testo sovrapposto non riceve una larghezza da nessuno e finiva
    /// incolonnato una lettera per riga.
    private var liveList: some View {
        VStack(alignment: .leading, spacing: 6) {
            HStack(spacing: 6) {
                Image(systemName: "record.circle")
                    .font(.system(size: 10))
                    .symbolEffect(.pulse)
                Text(L("macro.recordingNow"))
                    .font(.system(size: 10, weight: .semibold))
                    .lineLimit(1)
                    .minimumScaleFactor(0.8)
                Spacer(minLength: 0)
            }
            .foregroundStyle(.red)
            .frame(maxWidth: .infinity, alignment: .leading)

            Text(L("macro.recordingLock"))
                .font(.system(size: 9))
                .foregroundStyle(.secondary)
                .fixedSize(horizontal: false, vertical: true)

            ScrollView {
                VStack(alignment: .leading, spacing: 2) {
                    ForEach(recorder.events) { event in
                        HStack(spacing: 6) {
                            Image(systemName: event.isPress ? "arrow.down" : "arrow.up")
                                .font(.system(size: 8))
                                .foregroundStyle(event.isPress ? .green : .orange)
                            Text(KeyboardLayout.label(for: event.usage))
                                .font(.system(size: 11, weight: .medium))
                            Spacer(minLength: 0)
                        }
                    }
                }
                .frame(maxWidth: .infinity, alignment: .leading)
            }
            .frame(height: 140)
        }
        .padding(10)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(.red.opacity(0.10), in: RoundedRectangle(cornerRadius: 10))
        .overlay {
            RoundedRectangle(cornerRadius: 10)
                .strokeBorder(.red.opacity(0.35), lineWidth: 1)
        }
    }

    private var eventList: some View {
        ScrollView {
            VStack(spacing: 3) {
                ForEach(Array(events.enumerated()), id: \.element.id) { i, event in
                    eventRow(i, event)
                }
            }
        }
        .frame(height: 190)
    }

    private func eventRow(_ index: Int, _ event: MacroEvent) -> some View {
        HStack(spacing: 6) {
            Text("\(index + 1)")
                .font(.system(size: 9))
                .foregroundStyle(.secondary)
                .frame(width: 18, alignment: .trailing)

            Image(systemName: event.isPress ? "arrow.down.circle.fill" : "arrow.up.circle")
                .font(.system(size: 11))
                .foregroundStyle(event.isPress ? .green : .orange)

            Menu {
                ForEach(HIDKeycodes.groups, id: \.titleKey) { group in
                    Section(L(group.titleKey)) {
                        ForEach(group.keys) { key in
                            Button(key.label) { update(index) { $0.usage = key.code } }
                        }
                    }
                }
            } label: {
                Text(KeyboardLayout.label(for: event.usage))
                    .font(.system(size: 11, weight: .medium))
                    .lineLimit(1)
            }
            .frame(width: 64, alignment: .leading)

            TextField("", value: Binding(
                get: { Int(event.delayMs) },
                set: { newValue in
                    update(index) { $0.delayMs = UInt16(clamping: max(0, newValue)) }
                }
            ), format: .number)
            .textFieldStyle(.roundedBorder)
            .frame(width: 58)
            .font(.system(size: 10))
            .monospacedDigit()

            Text("ms").font(.system(size: 9)).foregroundStyle(.secondary)

            Spacer(minLength: 0)

            Button {
                var e = events; e.remove(at: index); macro.kind = .raw(e)
            } label: {
                Image(systemName: "minus.circle").font(.system(size: 11))
            }
            .buttonStyle(.plain)
            .foregroundStyle(.secondary)
        }
    }

    private func update(_ index: Int, _ change: (inout MacroEvent) -> Void) {
        var e = events
        guard index < e.count else { return }
        change(&e[index])
        macro.kind = .raw(e)
    }

    private var footer: some View {
        VStack(alignment: .leading, spacing: 5) {
            HStack {
                Label("\(events.count) \(L("macro.events"))", systemImage: "list.number")
                Spacer()
                Label(String(format: L("macro.duration"), Double(totalDuration) / 1000),
                      systemImage: "clock")
            }
            .font(.caption2)
            .foregroundStyle(.secondary)

            if let error = macro.validationError {
                Text(message(for: error))
                    .font(.caption2).foregroundStyle(.red)
                    .fixedSize(horizontal: false, vertical: true)
            } else if macro.isBeyondVerifiedLength {
                Text(String(format: L("macro.beyondVerified"),
                            MacroAssignment.verifiedEventCeiling))
                    .font(.caption2).foregroundStyle(.orange)
                    .fixedSize(horizontal: false, vertical: true)
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }

    private func message(for error: MacroValidationError) -> String {
        switch error {
        case .unmappableCharacters(let chars):
            return String(format: L("macro.unmappableChars"),
                          chars.map(String.init).joined(separator: " "))
        case .nameTooLong(let bytes):
            return String(format: L("macro.nameTooLong"), bytes, MacroAssignment.maxNameBytes)
        case .empty:
            return L("macro.emptyContent")
        }
    }
}
