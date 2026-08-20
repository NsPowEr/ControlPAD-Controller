import SwiftUI

struct HardwareBankPicker: View {
    @Environment(AppModel.self) private var app

    var body: some View {
        HStack(spacing: 16) {
            Label(L("bank.hardwareLabel"), systemImage: "square.stack.3d.up.fill")
                .font(.system(size: 11, weight: .bold))
                .foregroundStyle(.secondary)
                .padding(.leading, 6)
                .frame(width: 80, alignment: .leading)

            VStack(alignment: .leading, spacing: 6) {
                HStack(spacing: 6) {
                    ForEach(0..<12, id: \.self) { index in
                        HardwareProfileButton(index: index, isSelected: app.activeBankIndex == index) {
                            Task { await app.selectHardwareBank(index) }
                        }
                    }
                }
                HStack(spacing: 6) {
                    ForEach(12..<24, id: \.self) { index in
                        HardwareProfileButton(index: index, isSelected: app.activeBankIndex == index) {
                            Task { await app.selectHardwareBank(index) }
                        }
                    }
                }
            }
        }
        .padding(.horizontal, 12)
        .padding(.vertical, 8)
        .glassEffect(.regular, in: RoundedRectangle(cornerRadius: 12))
        .frame(maxWidth: 680)
    }
}

struct HardwareProfileButton: View {
    let index: Int
    let isSelected: Bool
    let action: () -> Void
    
    var body: some View {
        Button(action: action) {
            Text("P\(index + 1)")
                .font(.system(size: 10, weight: .semibold))
                .frame(minWidth: 22)
                .padding(.horizontal, 6)
                .padding(.vertical, 4)
                .background(
                    isSelected
                        ? Color.accentColor.opacity(0.85)
                        : Color.primary.opacity(0.08),
                    in: Capsule()
                )
                .foregroundStyle(isSelected ? Color.white : Color.primary)
        }
        .buttonStyle(.plain)
    }
}
