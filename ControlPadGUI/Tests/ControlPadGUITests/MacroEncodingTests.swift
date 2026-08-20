import Testing
@testable import ControlPadGUI

@Suite("MacroEncoding")
struct MacroEncodingTests {
    @Test("Carattere mappabile")
    func mappableCharacters() {
        #expect(MacroEncoding.isMappable("a"))
        #expect(MacroEncoding.isMappable("A"))
        #expect(MacroEncoding.isMappable("1"))
        #expect(MacroEncoding.isMappable(" "))
    }

    @Test("Carattere non mappabile")
    func unmappableCharacters() {
        #expect(!MacroEncoding.isMappable("è"))
        #expect(!MacroEncoding.isMappable("@"))
    }

    @Test("Conteggio eventi per testo semplice")
    func eventCountSimple() {
        // "a" = press + release = 2
        #expect(MacroEncoding.eventCount(forText: "a") == 2)
    }

    @Test("Conteggio eventi con maiuscole")
    func eventCountWithShift() {
        // "A" = shift down + press a + release a + shift up = 4
        #expect(MacroEncoding.eventCount(forText: "A") == 4)
    }

    @Test("Shift resta giu per gruppo maiuscole")
    func shiftGrouping() {
        // "CIA" = shift down + 3×(press+release) + shift up = 1 + 6 + 1 = 8
        #expect(MacroEncoding.eventCount(forText: "CIA") == 8)
    }

    @Test("Testo misto")
    func mixedCase() {
        // "CIAo" = shift down + 3×2 + shift up + 1×2 = 1+6+1+2 = 10
        #expect(MacroEncoding.eventCount(forText: "CIAo") == 10)
    }

    @Test("Testo vuoto")
    func emptyText() {
        #expect(MacroEncoding.eventCount(forText: "") == 0)
    }

    @Test("Rilevamento caratteri non mappabili")
    func unmappableDetection() {
        let bad = MacroEncoding.unmappableCharacters(in: "cioè")
        #expect(bad == ["è"])
    }

    @Test("Nessun carattere non mappabile nel testo valido")
    func allMappable() {
        let bad = MacroEncoding.unmappableCharacters(in: "abc 123")
        #expect(bad.isEmpty)
    }
}
