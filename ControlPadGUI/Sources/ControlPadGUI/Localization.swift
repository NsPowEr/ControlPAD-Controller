import Foundation

/// Bundle.main non basta: in uno Swift Package eseguibile le risorse
/// localizzate vivono in Bundle.module, e comunque vogliamo poter cambiare
/// lingua a runtime senza riavviare — cosa che la risoluzione automatica di
/// SwiftUI (Text(LocalizedStringKey), sempre legata a Bundle.main) non
/// permette. L() è quindi l'unico punto da cui le view leggono le stringhe.
enum AppLanguage: String, CaseIterable, Identifiable, Sendable {
    case system, italian = "it", english = "en"
    var id: String { rawValue }

    var titleKey: String {
        switch self {
        case .system: "language.system"
        case .italian: "language.italian"
        case .english: "language.english"
        }
    }
}

/// Le stringhe si leggono dal disco **una volta sola**, all'avvio e a ogni
/// cambio di lingua, e poi vivono in un dizionario in memoria.
///
/// Prima ogni singola `L()` finiva in `NSBundle.localizedString`, cioè in una
/// lettura di file — decine di volte per ogni disegno di una schermata. Su
/// questo Mac il progetto sta in `~/Desktop`, che è sincronizzato con iCloud:
/// una di quelle letture si è bloccata dentro `open()` mentre SwiftUI stava
/// costruendo la prima finestra, e l'app è rimasta appesa senza finestra, senza
/// motore Python e senza un errore da nessuna parte. Il disegno di
/// un'interfaccia non deve dipendere dal filesystem.
@MainActor
enum L10n {
    private static var table: [String: String] = [:]
    /// L'italiano fa da rete: una chiave aggiunta e non ancora tradotta esce
    /// leggibile invece che come nome di chiave.
    private static var fallback: [String: String] = [:]
    private static var loaded = false

    static func apply(_ language: AppLanguage) {
        table = load(code(for: language))
        if fallback.isEmpty { fallback = load("it") }
        loaded = true
    }

    static func string(_ key: String) -> String {
        if !loaded { apply(.system) }
        return table[key] ?? fallback[key] ?? key
    }

    private static func code(for language: AppLanguage) -> String {
        switch language {
        case .italian: return "it"
        case .english: return "en"
        case .system:
            // Solo due lingue tradotte: qualunque altra impostazione di
            // sistema cade sull'italiano, che è la lingua del progetto.
            let preferred = Locale.preferredLanguages.first ?? "it"
            return preferred.hasPrefix("en") ? "en" : "it"
        }
    }

    /// Il file delle stringhe si cerca a mano dentro l'app, **senza passare da
    /// `Bundle.module`**.
    ///
    /// `Bundle.module` è generato da SwiftPM e, prima di trovare le risorse
    /// impacchettate, prova anche il percorso della cartella di build fissato
    /// a compilazione — qui `~/Desktop/…/.build/…`, cioè dentro iCloud. Su
    /// quel percorso `CFBundleCreate` si è bloccato in `open()` mentre SwiftUI
    /// costruiva la prima finestra: app appesa, nessuna finestra, nessun
    /// motore Python, nessun errore. Cercando noi il file, l'unica cosa che si
    /// tocca è la copia dentro l'app.
    private static func load(_ code: String) -> [String: String] {
        for url in candidates(code) where FileManager.default.fileExists(atPath: url.path) {
            if let strings = NSDictionary(contentsOfFile: url.path) as? [String: String] {
                return strings
            }
        }
        return [:]
    }

    private static func candidates(_ code: String) -> [URL] {
        let leaf = "\(code).lproj/Localizable.strings"
        var urls: [URL] = []
        if let resources = Bundle.main.resourceURL {
            urls.append(resources
                .appendingPathComponent("ControlPadGUI_ControlPadGUI.bundle")
                .appendingPathComponent(leaf))
            urls.append(resources.appendingPathComponent(leaf))
        }
        // Sviluppo con `swift run`: il bundle di risorse sta accanto
        // all'eseguibile invece che dentro un'app.
        let executableDir = Bundle.main.bundleURL.deletingLastPathComponent()
        urls.append(executableDir
            .appendingPathComponent("ControlPadGUI_ControlPadGUI.bundle")
            .appendingPathComponent(leaf))
        return urls
    }
}

@MainActor
func L(_ key: String) -> String { L10n.string(key) }
