import SwiftUI

/// Le funzioni interne del pad in griglia, ognuna con la sua icona: a colpo
/// d'occhio si riconosce "volume giù" dal simbolo, non leggendo tre parole in
/// un elenco.
struct FunctionGridView: View {
    var selected: UInt16?
    var onPick: (SpecialFunction) -> Void

    private let columns = [GridItem(.adaptive(minimum: 96, maximum: 130), spacing: 8)]

    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            ForEach(SpecialFunction.Group.allCases, id: \.self) { group in
                let functions = SpecialFunctions.inGroup(group)
                if !functions.isEmpty {
                    VStack(alignment: .leading, spacing: 6) {
                        Text(L(group.titleKey))
                            .font(.system(size: 10, weight: .semibold))
                            .foregroundStyle(.secondary)
                            .textCase(.uppercase)
                        LazyVGrid(columns: columns, spacing: 8) {
                            ForEach(functions) { function in
                                tile(function)
                            }
                        }
                    }
                }
            }
        }
    }

    private func tile(_ function: SpecialFunction) -> some View {
        let isSelected = selected == function.code
        return Button {
            onPick(function)
        } label: {
            VStack(spacing: 6) {
                Image(systemName: function.icon)
                    .font(.system(size: 18))
                    .symbolRenderingMode(.hierarchical)
                    .frame(height: 22)
                Text(L(function.titleKey))
                    .font(.system(size: 10, weight: .medium))
                    .multilineTextAlignment(.center)
                    .lineLimit(2)
                    .minimumScaleFactor(0.8)
            }
            .frame(maxWidth: .infinity)
            .padding(.vertical, 10)
            .padding(.horizontal, 6)
            .background(
                isSelected ? AnyShapeStyle(Color.accentColor.opacity(0.22))
                           : AnyShapeStyle(.quaternary.opacity(0.4)),
                in: RoundedRectangle(cornerRadius: 10)
            )
            .overlay {
                RoundedRectangle(cornerRadius: 10)
                    .strokeBorder(isSelected ? Color.accentColor : .clear, lineWidth: 1.5)
            }
            .foregroundStyle(isSelected ? Color.accentColor : .primary)
            .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
    }
}
