import Testing
import Foundation
@testable import ControlPadGUI

@Suite("Preset")
struct PresetTests {
    @Test("Un preset nuovo e vuoto")
    func emptyPreset() {
        let preset = Preset(name: "Test")
        #expect(preset.macros.isEmpty)
        #expect(preset.remaps.isEmpty)
        #expect(preset.profileSelectors.isEmpty)
        #expect(preset.invalidMacros.isEmpty)
    }

    @Test("Codifica e decodifica JSON")
    func jsonRoundTrip() throws {
        var preset = Preset(name: "Roundtrip")
        preset.lighting.color = RGBColor(r: 128, g: 64, b: 32)
        preset.lighting.speed = 5
        preset.lighting.modeID = "blink"

        let data = try JSONEncoder().encode(preset)
        let decoded = try JSONDecoder().decode(Preset.self, from: data)

        #expect(decoded.name == "Roundtrip")
        #expect(decoded.lighting.color == RGBColor(r: 128, g: 64, b: 32))
        #expect(decoded.lighting.speed == 5)
        #expect(decoded.lighting.modeID == "blink")
    }

    @Test("Decodifica resiliente senza secondColor")
    func decodingWithoutSecondColor() throws {
        // Simula un profilo salvato prima che esistesse il secondo colore
        let json = """
        {"id":"00000000-0000-0000-0000-000000000001","name":"Old",
         "lighting":{"modeID":"static","color":{"r":255,"g":0,"b":0},
         "speed":8,"brightness":255,"perKeyColors":[]},
         "remaps":[],"macros":[],"profileSelectors":{}}
        """
        let preset = try JSONDecoder().decode(Preset.self, from: Data(json.utf8))
        #expect(preset.lighting.secondColor == .white)
    }
}

@Suite("MacroAssignment Validation")
struct MacroValidationTests {
    @Test("Macro valida non ha errori")
    func validMacro() {
        let macro = MacroAssignment(
            slot: 0, key: 0x04, name: "test",
            kind: .raw([MacroEvent(usage: 0x04, isPress: true, delayMs: 30)])
        )
        #expect(macro.validationError == nil)
    }

    @Test("Nome troppo lungo")
    func nameTooLong() {
        let macro = MacroAssignment(
            slot: 0, key: 0x04, name: "NomeMoltoLungoCheSfora",
            kind: .raw([MacroEvent(usage: 0x04, isPress: true, delayMs: 30)])
        )
        #expect(macro.validationError != nil)
        if case .nameTooLong = macro.validationError {} else {
            Issue.record("Atteso .nameTooLong")
        }
    }

    @Test("Macro vuota")
    func emptyMacro() {
        let macro = MacroAssignment(slot: 0, key: 0x04, name: "m", kind: .raw([]))
        #expect(macro.validationError == .empty)
    }

    @Test("Soglia di eventi verificati")
    func verifiedCeiling() {
        #expect(MacroAssignment.verifiedEventCeiling == 49)
        #expect(MacroAssignment.maxNameBytes == 12)
    }

    @Test("Oltre 49 eventi non e un errore ma viene segnalato")
    func beyondVerified() {
        let events = (0..<50).map { _ in MacroEvent(usage: 0x04, isPress: true, delayMs: 30) }
        let macro = MacroAssignment(slot: 0, key: 0x04, name: "big", kind: .raw(events))
        #expect(macro.validationError == nil)
        #expect(macro.isBeyondVerifiedLength)
    }

    @Test("Testo con caratteri non mappabili")
    func unmappableText() {
        let macro = MacroAssignment(slot: 0, key: 0x04, name: "m", kind: .text("cioè"))
        if case .unmappableCharacters(let chars) = macro.validationError {
            #expect(chars == ["è"])
        } else {
            Issue.record("Atteso .unmappableCharacters")
        }
    }
}
