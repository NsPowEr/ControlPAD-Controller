import SwiftUI

/// Tastiera disegnata per intero, invece di un elenco di tasti per categoria.
/// Su una tastiera l'occhio trova "P" o "F7" senza leggere: in una lista
/// alfabetica va cercato. È anche il motivo per cui l'app ufficiale ne
/// disegna una sotto al pad.
struct KeyboardPickerView: View {
    var selected: UInt8?
    var onPick: (UInt8) -> Void

    /// Misura di un tasto singolo alla scala 1. La tastiera cresce con la
    /// finestra fino a `maxScale`: prima restava di dimensione fissa mentre il
    /// pad qui sopra si allargava, e i due disegni finivano fuori proporzione.
    private let baseUnit: CGFloat = 29
    private let baseGap: CGFloat = 3.5
    private let maxScale: CGFloat = 1.9

    @State private var available: CGFloat = 0

    private var scale: CGFloat {
        let natural = Self.naturalWidth(unit: baseUnit, gap: baseGap)
        guard available > 0, natural > 0 else { return 1 }
        return min(maxScale, max(0.75, available / natural))
    }

    private var unit: CGFloat { baseUnit * scale }
    private var gap: CGFloat { baseGap * scale }
    private var blockSpacing: CGFloat { 16 * scale }

    /// Larghezza della tastiera intera a una data misura del tasto: serve per
    /// sapere di quanto ingrandirla senza mandarla fuori dal riquadro.
    private static func naturalWidth(unit: CGFloat, gap: CGFloat) -> CGFloat {
        func blockWidth(_ rows: [[KeyboardKey]]) -> CGFloat {
            var widest: CGFloat = 0
            for row in rows {
                var total: CGFloat = 0
                for key in row {
                    let keyWidth: CGFloat = key.width
                    total += unit * keyWidth + gap * (keyWidth - 1)
                }
                total += gap * CGFloat(max(0, row.count - 1))
                widest = max(widest, total)
            }
            return widest
        }
        return blockWidth(KeyboardLayout.mainRows) + 16
            + blockWidth(KeyboardLayout.navigationRows)
    }

    var body: some View {
        // La misura arriva dal contenitore, non dalla tastiera stessa: se si
        // misurasse il proprio disegno la scala si inseguirebbe da sola.
        HStack(spacing: 0) {
            Spacer(minLength: 0)
            keyboard
            Spacer(minLength: 0)
        }
        .frame(maxWidth: .infinity)
        .background {
            GeometryReader { proxy in
                Color.clear
                    .onChange(of: proxy.size.width, initial: true) { _, width in
                        available = width
                    }
            }
        }
    }

    private var keyboard: some View {
        HStack(alignment: .top, spacing: blockSpacing) {
            VStack(spacing: gap) {
                ForEach(Array(KeyboardLayout.mainRows.enumerated()), id: \.offset) { _, row in
                    HStack(spacing: gap) {
                        ForEach(Array(row.enumerated()), id: \.offset) { _, key in
                            keyView(key)
                        }
                    }
                }
            }
            VStack(spacing: gap) {
                ForEach(Array(KeyboardLayout.navigationRows.enumerated()), id: \.offset) { _, row in
                    HStack(spacing: gap) {
                        ForEach(Array(row.enumerated()), id: \.offset) { _, key in
                            keyView(key)
                        }
                    }
                    .frame(height: row.isEmpty ? unit / 2 : nil)
                }
            }
        }
    }

    @ViewBuilder
    private func keyView(_ key: KeyboardKey) -> some View {
        let width = unit * key.width + gap * (key.width - 1)

        if key.usage == 0 {
            // Spaziatore fra i gruppi: tiene l'allineamento senza essere un tasto.
            Color.clear.frame(width: width, height: unit)
        } else {
            let isSelected = selected == key.usage
            Button {
                onPick(key.usage)
            } label: {
                VStack(spacing: 0) {
                    if let shifted = key.shifted {
                        Text(shifted)
                            .font(.system(size: 8))
                            .opacity(0.5)
                    }
                    Text(key.label)
                        .font(.system(size: key.label.count > 2 ? 9 : 12, weight: .medium))
                        .lineLimit(1)
                        .minimumScaleFactor(0.6)
                }
                .frame(width: width, height: unit)
                .background(
                    isSelected ? AnyShapeStyle(Color.accentColor) : AnyShapeStyle(.quaternary),
                    in: RoundedRectangle(cornerRadius: 6)
                )
                .foregroundStyle(isSelected ? .white : .primary)
                .overlay {
                    RoundedRectangle(cornerRadius: 6)
                        .strokeBorder(.white.opacity(0.08), lineWidth: 1)
                }
            }
            .buttonStyle(.plain)
            .help(key.label)
        }
    }
}
