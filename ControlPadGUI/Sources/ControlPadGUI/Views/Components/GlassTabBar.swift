import SwiftUI

/// Barra flottante Liquid Glass con le 4 schede più l'ingresso Impostazioni,
/// al posto della barra piatta viola dell'app originale.
struct GlassTabBar: View {
    @Binding var selection: AppTab
    @Binding var showSettings: Bool
    @Namespace private var namespace

    var body: some View {
        GlassEffectContainer(spacing: 4) {
            HStack(spacing: 4) {
                ForEach(AppTab.allCases) { tab in
                    tabButton(tab)
                }

                Divider().frame(height: 20).padding(.horizontal, 4)

                Button {
                    showSettings = true
                } label: {
                    Image(systemName: "gearshape.fill")
                        .font(.system(size: 14, weight: .semibold))
                        .frame(width: 32, height: 32)
                }
                .buttonStyle(.plain)
                .glassEffect(.regular.interactive(), in: .circle)
            }
            .padding(6)
        }
        .glassEffect(.regular, in: .capsule)
    }

    private func tabButton(_ tab: AppTab) -> some View {
        Button {
            selection = tab
        } label: {
            Label(L(tab.titleKey), systemImage: tab.icon)
                .labelStyle(.titleAndIcon)
                .font(.system(size: 13, weight: .semibold))
                .padding(.horizontal, 14)
                .padding(.vertical, 8)
        }
        .buttonStyle(.plain)
        .foregroundStyle(selection == tab ? Color.accentColor : .primary)
        .background {
            if selection == tab {
                Capsule()
                    .fill(Color.accentColor.opacity(0.16))
                    .matchedGeometryEffect(id: "tabSelection", in: namespace)
            }
        }
        .clipShape(Capsule())
    }
}
