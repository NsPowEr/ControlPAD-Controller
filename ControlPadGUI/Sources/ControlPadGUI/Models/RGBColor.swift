import SwiftUI

/// Colore a 8 bit per canale, così come lo vuole il protocollo — niente
/// Double/CGFloat qui, la conversione avviene solo al confine con SwiftUI.
struct RGBColor: Codable, Hashable, Sendable {
    var r: UInt8
    var g: UInt8
    var b: UInt8

    static let black = RGBColor(r: 0, g: 0, b: 0)
    static let white = RGBColor(r: 255, g: 255, b: 255)

    var color: Color {
        Color(red: Double(r) / 255, green: Double(g) / 255, blue: Double(b) / 255)
    }

    init(r: UInt8, g: UInt8, b: UInt8) {
        self.r = r
        self.g = g
        self.b = b
    }

    init(color: Color) {
        // NSColor è la via più affidabile per leggere le componenti sRGB su macOS.
        let ns = NSColor(color).usingColorSpace(.sRGB) ?? NSColor(color)
        r = UInt8(clamping: Int((ns.redComponent * 255).rounded()))
        g = UInt8(clamping: Int((ns.greenComponent * 255).rounded()))
        b = UInt8(clamping: Int((ns.blueComponent * 255).rounded()))
    }
}
