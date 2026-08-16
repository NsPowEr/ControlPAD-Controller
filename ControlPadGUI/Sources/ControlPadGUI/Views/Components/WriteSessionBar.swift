import SwiftUI

/// Pulsante di scrittura permanente condiviso da Mappatura e Macro: entrambe
/// le schede modificano lo stesso app.draft, e il dispositivo lo riscrive
/// sempre per intero (PROTOCOL.md: "l'app riscrive l'intero stato a ogni
/// applicazione"), quindi un solo comando — e una sola validazione — serve
/// a tutte e due. Il blocco è reale: non solo testo rosso nell'editor, il
/// bottone si disabilita finché ogni macro non è valida.
struct WriteSessionBar: View {
    @Environment(AppModel.self) private var app
    @State private var isWriting = false
    @State private var errorMessage: String?
    @State private var didSucceed = false

    private var blockingReason: String? {
        guard let bad = app.draft.invalidMacros.first else { return nil }
        let name = bad.name.isEmpty ? L("macro.unnamed") : bad.name
        return String(format: L("session.blockedByMacro"), name)
    }

    private var conflictWarning: String? {
        let count = app.draft.keysWithMacroAndRemapConflict.count
        guard count > 0 else { return nil }
        return String(format: L("session.macroRemapConflict"), count)
    }

    var body: some View {
        VStack(alignment: .trailing, spacing: 4) {
            if let conflictWarning, blockingReason == nil {
                Label(conflictWarning, systemImage: "exclamationmark.triangle")
                    .font(.caption2)
                    .foregroundStyle(.orange)
            }
            HStack(spacing: 10) {
                if let blockingReason {
                    Label(blockingReason, systemImage: "xmark.octagon.fill")
                        .font(.caption)
                        .foregroundStyle(.red)
                } else if let errorMessage {
                    Label(errorMessage, systemImage: "exclamationmark.triangle.fill")
                        .font(.caption)
                        .foregroundStyle(.red)
                } else if didSucceed {
                    Label(L("session.written"), systemImage: "checkmark.circle.fill")
                        .font(.caption)
                        .foregroundStyle(.green)
                }

                Spacer()

                Button {
                    Task { await write() }
                } label: {
                    if isWriting {
                        ProgressView().controlSize(.small)
                    } else {
                        Text(L("session.write"))
                    }
                }
                .buttonStyle(.borderedProminent)
                .disabled(isWriting || !app.isConnected || blockingReason != nil)
            }
        }
    }

    private func write() async {
        isWriting = true
        errorMessage = nil
        didSucceed = false
        do {
            // writeDraft, non bridge.writeSession: la scrittura di sessione da
            // sola riporta l'illuminazione a quella della cattura originale.
            try await app.writeDraft()
            didSucceed = true
        } catch {
            errorMessage = error.localizedDescription
        }
        isWriting = false
    }
}
