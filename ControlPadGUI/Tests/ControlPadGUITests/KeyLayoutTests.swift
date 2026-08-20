import Testing
@testable import ControlPadGUI

@Suite("KeyLayout")
struct KeyLayoutTests {
    @Test("24 tasti su 25 posizioni")
    func totalKeys() {
        #expect(KeyLayout.allKeys.count == 24)
    }

    @Test("La griglia ha 5 righe e 5 colonne")
    func gridDimensions() {
        #expect(KeyLayout.grid.count == KeyLayout.rows)
        for row in KeyLayout.grid {
            #expect(row.count == KeyLayout.cols)
        }
    }

    @Test("Una sola posizione nil (il secondo slot dello spazio)")
    func singleNilPosition() {
        let nilCount = KeyLayout.grid.flatMap { $0 }.filter { $0 == nil }.count
        #expect(nilCount == 1)
    }

    @Test("Ogni codice HID ha una posizione")
    func allKeysHavePosition() {
        for key in KeyLayout.allKeys {
            #expect(KeyLayout.position(of: key) != nil, "Codice 0x\(String(key, radix: 16)) senza posizione")
        }
    }

    @Test("Indice per colonne di andata e ritorno")
    func columnIndexRoundTrip() {
        for position in KeyLayout.allPositions {
            let index = KeyLayout.columnIndex(position)
            let key = KeyLayout.key(atColumnIndex: index)
            let originalKey = KeyLayout.key(at: position)
            #expect(key == originalKey)
        }
    }

    @Test("Numero tasto 1-24")
    func numberRange() {
        for position in KeyLayout.allPositions {
            let number = KeyLayout.number(at: position)
            #expect(number >= 1 && number <= 25)
        }
    }

    @Test("Tasto effetti e 0xC0")
    func effectCycleKey() {
        #expect(KeyLayout.effectCycleKey == 0xC0)
    }

    @Test("Rotelle hanno 4 pseudo-tasti")
    func wheelKeys() {
        #expect(KeyLayout.wheelKeys.count == 4)
    }

    @Test("Azione predefinita di un tasto normale e il tasto stesso")
    func defaultActionNormalKey() {
        // Il tasto 'a' (0x04) deve battere se stesso
        #expect(KeyLayout.defaultAction(forKey: 0x04) == 0x04)
    }

    @Test("Azione predefinita del tasto effetti e effetto avanti")
    func defaultActionEffectKey() {
        #expect(KeyLayout.defaultAction(forKey: 0xC0) == SpecialFunctions.effectCycleForward)
    }
}
