import AppKit
import SwiftUI

/// Registra quello che l'utente batte davvero, con i tempi reali, e lo
/// trasforma nella sequenza di eventi che il pad riprodurrà.
///
/// Usa `NSEvent.addLocalMonitorForEvents`, che vede solo gli eventi diretti a
/// questa app: basta, perché si registra con la finestra in primo piano, e in
/// cambio **non serve il permesso Accessibilità** che invece pretenderebbe un
/// tap globale. Il monitor consuma gli eventi (ritorna nil) così i tasti
/// premuti durante la registrazione non finiscono anche nei campi di testo.
///
/// Il ritardo di un evento è il tempo che passa **fino al successivo**, non
/// dal precedente: è la convenzione del protocollo (macro.py attacca `hold`
/// alla pressione e `gap` al rilascio), e si vede nelle catture, dove il primo
/// evento porta l'attesa che lo separa dal secondo.
@MainActor
@Observable
final class MacroRecorder {
    private(set) var isRecording = false
    private(set) var events: [MacroEvent] = []

    private var monitors: [Any] = []
    private var timestamps: [TimeInterval] = []
    private var lastFlags = NSEvent.ModifierFlags()

    /// Un tasto tenuto premuto genera una raffica di keyDown ripetuti: sono
    /// artefatti del sistema, non pressioni vere, e vanno scartati o una
    /// pausa di due secondi diventerebbe cinquanta eventi.
    private func record(usage: UInt8, isPress: Bool, at time: TimeInterval) {
        events.append(MacroEvent(usage: usage, isPress: isPress, delayMs: 0))
        timestamps.append(time)
    }

    func start() {
        guard !isRecording else { return }
        events = []
        timestamps = []
        lastFlags = NSEvent.modifierFlags
        isRecording = true

        let keys = NSEvent.addLocalMonitorForEvents(matching: [.keyDown, .keyUp]) { [weak self] event in
            guard let self, self.isRecording else { return event }
            if event.type == .keyDown && event.isARepeat { return nil }
            if let usage = MacKeyCodes.hidUsage(for: event.keyCode) {
                self.record(usage: usage, isPress: event.type == .keyDown,
                            at: event.timestamp)
            }
            return nil
        }

        let flags = NSEvent.addLocalMonitorForEvents(matching: [.flagsChanged]) { [weak self] event in
            guard let self, self.isRecording else { return event }
            if let usage = MacKeyCodes.modifiers[event.keyCode] {
                // Quale flag rappresenta questo tasto dice se è sceso o
                // risalito: flagsChanged non lo distingue da solo.
                let mask = Self.mask(for: event.keyCode)
                let isPress = event.modifierFlags.contains(mask)
                    && !self.lastFlags.contains(mask)
                let isRelease = !event.modifierFlags.contains(mask)
                    && self.lastFlags.contains(mask)
                if isPress || isRelease {
                    self.record(usage: usage, isPress: isPress, at: event.timestamp)
                }
            }
            self.lastFlags = event.modifierFlags
            return nil
        }

        monitors = [keys, flags].compactMap { $0 }
    }

    func stop() {
        guard isRecording else { return }
        isRecording = false
        monitors.forEach(NSEvent.removeMonitor)
        monitors = []
        closeHeldKeys()
        computeDelays()
    }

    /// Se l'utente ferma la registrazione tenendo ancora giù un tasto, il
    /// rilascio non arriverà mai: senza chiuderlo il pad resterebbe con quel
    /// tasto premuto per sempre.
    private func closeHeldKeys() {
        var held: [UInt8] = []
        for event in events {
            if event.isPress {
                held.append(event.usage)
            } else if let index = held.lastIndex(of: event.usage) {
                held.remove(at: index)
            }
        }
        let now = timestamps.last ?? 0
        for usage in held.reversed() {
            events.append(MacroEvent(usage: usage, isPress: false, delayMs: 0))
            timestamps.append(now)
        }
    }

    private func computeDelays() {
        guard events.count > 1 else { return }
        for i in 0..<(events.count - 1) {
            let gap = (timestamps[i + 1] - timestamps[i]) * 1000
            events[i].delayMs = UInt16(clamping: Int(gap.rounded()))
        }
        events[events.count - 1].delayMs = 0
    }

    private static func mask(for keyCode: UInt16) -> NSEvent.ModifierFlags {
        switch keyCode {
        case 0x38, 0x3C: .shift
        case 0x3B, 0x3E: .control
        case 0x3A, 0x3D: .option
        default: .command
        }
    }
}
