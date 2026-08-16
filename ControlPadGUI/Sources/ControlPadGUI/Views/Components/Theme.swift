import SwiftUI

/// Le misure dell'interfaccia, in un posto solo.
///
/// Prima ogni scheda sceglieva le sue: larghezze fisse diverse (220, 210, 250,
/// 560), altezze fisse diverse (340, 560, 420, 290), padding a occhio. Il
/// risultato erano riquadri di taglie tutte differenti sulla stessa riga, e
/// niente che si adattasse quando la finestra cambiava dimensione. Da qui in
/// poi le misure si scelgono qui e valgono per tutte e quattro le schede.
enum Metrics {
    /// Margine della pagina, uguale in tutte le schede.
    static let page: CGFloat = 22
    /// Distanza fra due riquadri, orizzontale o verticale che sia.
    static let gap: CGFloat = 16
    /// Dentro un riquadro, fra il titolo e il contenuto e fra i controlli.
    static let stack: CGFloat = 12
    static let cardPadding: CGFloat = 16
    static let cardRadius: CGFloat = 18
    /// Colonna di supporto (elenchi, riepiloghi): stessa larghezza ovunque,
    /// così le schede sembrano la stessa app e non quattro app diverse.
    static let sidebar: CGFloat = 260
    /// Larghezza sotto la quale le colonne si impilano invece di schiacciarsi.
    static let breakpoint: CGFloat = 1080
    /// Minimo della finestra: sotto, anche impilato, il pad non ci sta.
    static let windowMinWidth: CGFloat = 720
    static let windowMinHeight: CGFloat = 620
}

/// Riquadro di vetro, unico per tutta l'app.
///
/// Angoli concentrici rispetto al contenitore esterno, non un riquadro scuro
/// fisso come nell'app originale. Si allunga sempre fino all'altezza della sua
/// riga: due riquadri affiancati finiscono alla stessa quota, che è la cosa
/// che più si notava quando non c'era.
struct GlassCard<Content: View>: View {
    /// Chiave in Localizable.strings, non il testo già tradotto. nil per un
    /// riquadro senza intestazione.
    var titleKey: String? = nil
    /// Riga di spiegazione sotto il titolo, sempre in chiave.
    var subtitleKey: String? = nil
    @ViewBuilder var content: Content

    var body: some View {
        VStack(alignment: .leading, spacing: Metrics.stack) {
            if titleKey != nil || subtitleKey != nil {
                VStack(alignment: .leading, spacing: 3) {
                    if let titleKey {
                        Text(L(titleKey))
                            .font(.system(size: 11, weight: .semibold))
                            .textCase(.uppercase)
                            .kerning(0.6)
                            .foregroundStyle(.secondary)
                    }
                    if let subtitleKey {
                        Text(L(subtitleKey))
                            .font(.system(size: 10))
                            .foregroundStyle(.tertiary)
                            .fixedSize(horizontal: false, vertical: true)
                    }
                }
                .frame(maxWidth: .infinity, alignment: .leading)
            }
            content
            Spacer(minLength: 0)
        }
        .padding(Metrics.cardPadding)
        .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .topLeading)
        .glassEffect(.regular, in: .rect(cornerRadius: Metrics.cardRadius))
    }
}

/// Colonne finché c'è spazio, righe quando la finestra si stringe.
///
/// Serve perché le schede avevano larghezze fisse: allargando la finestra
/// restava spazio vuoto, restringendola i riquadri si schiacciavano l'uno
/// sull'altro invece di riorganizzarsi.
struct ResponsiveRow<Content: View>: View {
    var breakpoint: CGFloat = Metrics.breakpoint
    var spacing: CGFloat = Metrics.gap
    @ViewBuilder var content: Content

    @State private var isWide = true

    var body: some View {
        Group {
            if isWide {
                HStack(alignment: .top, spacing: spacing) { content }
            } else {
                VStack(spacing: spacing) { content }
            }
        }
        .frame(maxWidth: .infinity, alignment: .topLeading)
        .environment(\.isStackedLayout, !isWide)
        .background {
            GeometryReader { proxy in
                Color.clear
                    .onChange(of: proxy.size.width, initial: true) { _, width in
                        // Isteresi: senza, alla larghezza esatta di soglia il
                        // layout sfarfalla fra le due disposizioni.
                        if isWide && width < breakpoint - 20 { isWide = false }
                        if !isWide && width > breakpoint + 20 { isWide = true }
                    }
            }
        }
    }
}

extension EnvironmentValues {
    /// true quando ResponsiveRow ha impilato le colonne: chi dentro aveva una
    /// larghezza da colonna deve prendersi tutta la riga.
    @Entry var isStackedLayout: Bool = false
}

private struct SidebarColumn: ViewModifier {
    let width: CGFloat
    @Environment(\.isStackedLayout) private var isStacked

    func body(content: Content) -> some View {
        content.frame(maxWidth: isStacked ? .infinity : width)
    }
}

extension View {
    /// Colonna di supporto: larghezza uniforme quando c'è spazio, riga intera
    /// quando le colonne si sono impilate.
    func sidebarColumn(_ width: CGFloat = Metrics.sidebar) -> some View {
        modifier(SidebarColumn(width: width))
    }
}
