import SwiftUI

/// Griglia 5×5 del pad, riusata da Illuminazione/Mappatura/Macro.
///
/// Ogni tasto mostra prima il **numero serigrafato** (1–24) e sotto, in
/// piccolo, cosa gli è assegnato. È l'ordine giusto perché sul ControlPad
/// vero sono stampati i numeri: i codici di default (`, Tab, Q…) sono quello
/// che il pad batte, non quello che l'utente legge sui tasti.
///
/// Lo spazio occupa due posizioni nell'ultima riga (KeyLayout.grid ha nil
/// lì), quindi diventa un tasto largo invece di un buco.
struct PadGridView: View {
    var fill: (GridPosition) -> Color
    /// Cosa c'è assegnato: macro, rimappatura, funzione. nil = niente.
    var assignment: (GridPosition) -> String?
    var selection: GridPosition?
    var onTap: ((GridPosition) -> Void)?

    var showIndicatorLEDs = false
    var indicatorColors: [Color] = Array(repeating: .white, count: 4)
    /// Quanto può diventare grande un tasto. La misura vera si ricava dalla
    /// larghezza disponibile: la griglia riempie il riquadro invece di restare
    /// un francobollo in mezzo al vuoto, e segue la finestra quando la si
    /// ridimensiona.
    var maxKeySize: CGFloat = 96

    private let spacing: CGFloat = 8
    private let minKeySize: CGFloat = 40

    @State private var availableWidth: CGFloat = 0

    private var keySize: CGFloat {
        guard availableWidth > 0 else { return minKeySize }
        let columns = CGFloat(KeyLayout.cols)
        let fitted = (availableWidth - spacing * (columns - 1)) / columns
        return min(maxKeySize, max(minKeySize, fitted.rounded(.down)))
    }

    /// Niente vetro qui: la griglia sta sempre dentro una GlassCard, e due
    /// pannelli di vetro annidati erano una delle cose che facevano sembrare
    /// le schede fatte da persone diverse.
    var body: some View {
        VStack(spacing: 14) {
            if showIndicatorLEDs {
                HStack(spacing: 14) {
                    ForEach(0..<4, id: \.self) { i in
                        Capsule()
                            .fill(indicatorColors[i])
                            .frame(width: 26, height: 6)
                            .overlay(Capsule().strokeBorder(.white.opacity(0.28), lineWidth: 0.5))
                    }
                }
            }

            VStack(spacing: spacing) {
                ForEach(0..<KeyLayout.rows, id: \.self) { row in
                    rowView(row)
                }
            }
        }
        .frame(maxWidth: .infinity)
        .background {
            GeometryReader { proxy in
                Color.clear
                    .onChange(of: proxy.size.width, initial: true) { _, width in
                        availableWidth = width
                    }
            }
        }
    }

    @ViewBuilder
    private func rowView(_ row: Int) -> some View {
        HStack(spacing: spacing) {
            ForEach(0..<KeyLayout.cols, id: \.self) { col in
                if KeyLayout.grid[row][col] != nil {
                    keyButton(GridPosition(col: col, row: row), wide: row == 4 && col == 3)
                } else if !(row == 4 && col == 4) {
                    Color.clear.frame(width: keySize, height: keySize)
                }
            }
        }
    }

    private func keyButton(_ position: GridPosition, wide: Bool) -> some View {
        let width = wide ? keySize * 2 + spacing : keySize
        let isSelected = selection == position
        let background = fill(position)
        let ink: Color = background.isDark ? .white : .black

        return Button {
            onTap?(position)
        } label: {
            VStack(spacing: 1) {
                Text("\(KeyLayout.number(at: position))")
                    .font(.system(size: 17, weight: .semibold, design: .rounded))
                    .monospacedDigit()
                if let assignment = assignment(position) {
                    Text(assignment)
                        .font(.system(size: 8, weight: .medium))
                        .lineLimit(1)
                        .minimumScaleFactor(0.7)
                        .opacity(0.75)
                } else {
                    // Segnaposto: senza, i tasti assegnati sarebbero più alti
                    // degli altri e la griglia ballerebbe.
                    Text(" ").font(.system(size: 8))
                }
            }
            .foregroundStyle(ink)
            .frame(width: width, height: keySize)
            .background(background.opacity(0.85), in: RoundedRectangle(cornerRadius: 10))
            .overlay {
                RoundedRectangle(cornerRadius: 10)
                    .strokeBorder(isSelected ? Color.accentColor : .white.opacity(0.12),
                                  lineWidth: isSelected ? 2 : 1)
            }
        }
        .buttonStyle(.plain)
    }
}

extension Color {
    /// Sceglie il colore del testo in base alla luminosità del tasto, così
    /// l'etichetta resta leggibile qualunque colore LED sia impostato.
    var isDark: Bool {
        let ns = NSColor(self).usingColorSpace(.sRGB) ?? NSColor(self)
        let luminance = 0.299 * ns.redComponent + 0.587 * ns.greenComponent + 0.114 * ns.blueComponent
        return luminance < 0.6
    }
}
