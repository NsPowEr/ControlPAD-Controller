import SwiftUI

/// Banner flottante mostrato quando il pad non è collegato — l'app deve
/// restare chiara su questo anche prima di toccare qualunque scheda.
struct ConnectionBanner: View {
    var body: some View {
        Label(L("connection.notFound"), systemImage: "cable.connector.slash")
            .font(.system(size: 12, weight: .medium))
            .padding(.horizontal, 14)
            .padding(.vertical, 8)
            .foregroundStyle(.orange)
            .glassEffect(.regular.tint(.orange.opacity(0.15)), in: .capsule)
    }
}
