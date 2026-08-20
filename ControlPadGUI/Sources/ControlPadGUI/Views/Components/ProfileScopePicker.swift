import SwiftUI

/// Su quali profili vale l'assegnazione appena fatta.
///
/// La keymap del dispositivo è **per banco**: un tasto rimappato su un profilo
/// non esiste sugli altri. Per le rimappature normali si nota poco — si cambia
/// profilo e si cambia mestiere al tasto, che è il punto dei profili — ma per
/// "Profilo +/−" salta agli occhi, perché premuto su un profilo dove non è
/// assegnato non fa niente e sembra rotto.
///
/// Da qui si sceglie una volta sola fra i tre casi utili: questo profilo,
/// alcuni, tutti.
struct ProfileScopePicker: View {
    /// Il profilo su cui si sta lavorando: è già scritto, quindi negli altri
    /// due modi compare selezionato e non si toglie.
    let currentBank: Int
    /// Chiamata con i banchi da scrivere, il corrente escluso.
    let onApply: ([Int]) -> Void
    /// (fatti, totale) mentre la scrittura è in corso, altrimenti nil.
    var progress: (fatti: Int, totale: Int)?

    @State private var scope: Scope = .thisOne
    @State private var chosen: Set<Int> = []

    enum Scope: String, CaseIterable, Identifiable {
        case thisOne, some, all
        var id: String { rawValue }
        var titleKey: String {
            switch self {
            case .thisOne: "mapping.scope.thisProfile"
            case .some: "mapping.scope.someProfiles"
            case .all: "mapping.scope.allProfiles"
            }
        }
    }

    /// I banchi da scrivere adesso: il corrente è già a posto e resta fuori.
    private var targets: [Int] {
        switch scope {
        case .thisOne: []
        case .all: (0..<24).filter { $0 != currentBank }
        case .some: chosen.filter { $0 != currentBank }.sorted()
        }
    }

    var body: some View {
        VStack(alignment: .leading, spacing: Metrics.stack) {
            Picker("", selection: $scope) {
                ForEach(Scope.allCases) { s in Text(L(s.titleKey)).tag(s) }
            }
            .pickerStyle(.segmented)
            .labelsHidden()
            .frame(maxWidth: 420)

            if scope == .some {
                profileGrid
            }

            HStack(spacing: 10) {
                if let progress {
                    ProgressView(value: Double(progress.fatti),
                                 total: Double(progress.totale))
                        .frame(width: 140)
                    Text(String(format: L("mapping.scope.writing"),
                                progress.fatti, progress.totale))
                        .font(.system(size: 11))
                        .foregroundStyle(.secondary)
                } else {
                    Button {
                        onApply(targets)
                    } label: {
                        Label(String(format: L("mapping.scope.apply"), targets.count),
                              systemImage: "square.on.square")
                    }
                    .disabled(targets.isEmpty)

                    Text(L(scope == .thisOne ? "mapping.scope.thisProfileHint"
                                             : "mapping.scope.otherHint"))
                        .font(.system(size: 11))
                        .foregroundStyle(.secondary)
                        .fixedSize(horizontal: false, vertical: true)
                }
            }
        }
    }

    private var profileGrid: some View {
        VStack(alignment: .leading, spacing: 6) {
            ForEach([Array(0..<12), Array(12..<24)], id: \.self) { riga in
                HStack(spacing: 6) {
                    ForEach(riga, id: \.self) { index in
                        profileChip(index)
                    }
                }
            }
            HStack(spacing: 12) {
                Button(L("mapping.scope.selectAll")) { chosen = Set(0..<24) }
                Button(L("mapping.scope.selectNone")) { chosen = [] }
            }
            .font(.system(size: 11))
            .buttonStyle(.link)
        }
    }

    private func profileChip(_ index: Int) -> some View {
        // Il profilo corrente è sempre acceso e non si spegne: l'assegnazione
        // lì c'è già, e mostrarlo spegnibile prometterebbe di toglierla.
        let isCurrent = index == currentBank
        let isOn = isCurrent || chosen.contains(index)
        return Button {
            guard !isCurrent else { return }
            if chosen.contains(index) { chosen.remove(index) } else { chosen.insert(index) }
        } label: {
            Text("P\(index + 1)")
                .font(.system(size: 10, weight: .semibold))
                .frame(minWidth: 24)
                .padding(.horizontal, 5)
                .padding(.vertical, 4)
                .background(isOn ? Color.accentColor.opacity(isCurrent ? 0.45 : 0.85)
                                 : Color.primary.opacity(0.08),
                            in: Capsule())
                .foregroundStyle(isOn ? Color.white : Color.primary)
        }
        .buttonStyle(.plain)
        .help(isCurrent ? L("mapping.scope.currentProfile") : "")
    }
}
